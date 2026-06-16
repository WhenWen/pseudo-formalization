"""Map referee error messages to concrete errored blocks in each AI proof.

For every reviewed submission we send the proof plus all referee reviews
(summary + recommendation + inline-annotated submission) to an OpenAI model and
ask it to return, as strict JSON:

  - an overall verdict (correct / minor_issues_only / flawed)
  - a list of mathematical `errors`, each pinned to a VERBATIM block of the proof
    with a paragraph of error description synthesised from the referee comments
  - a list of `secondary_issues` (citation / exposition) kept separate so the
    report can focus on genuine mathematical defects

After the model returns, each `errored_block` is checked against the proof text
(exact, then whitespace-insensitive fuzzy) so the HTML report can highlight it
in context. Results are written to errors.json.
"""

import argparse
import asyncio
import json
import os
import re
import time
from pathlib import Path

from openai import AsyncOpenAI

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "corpus.json"
OUT = HERE / "errors.json"

DEFAULT_MODEL = "gpt-5.5"
DEFAULT_EFFORT = "high"
CONCURRENCY = 6

SYSTEM = """You are a meticulous mathematics editor assembling an error-annotation \
dataset. You are given (1) an AI-generated proof for a research-level math \
problem and (2) the referee reports for it. The referees have already inserted \
inline comments at the exact spots they are critiquing, marked in the text as \
[[REVIEWER COMMENT: ...]].

Your job: identify the genuine MATHEMATICAL defects of the proof and pin each one \
to the concrete block of the proof it lives in.

Definitions:
- A "mathematical error" is an incorrect step, an unjustified or false claim, a \
logical gap that is not filled, or a proof that is incomplete / proves the wrong \
statement. These go in `errors`.
- Pure citation/attribution problems and pure exposition/wording complaints, when \
the underlying mathematics is sound, are NOT mathematical errors. These go in \
`secondary_issues`.

Rules:
- Ground every error in the referees' findings; do not invent defects the \
referees did not raise. If referees disagree, prefer the substantive correctness \
critique and note the disagreement in the description.
- `errored_block` MUST be copied VERBATIM (character for character) from the \
proof text I provide under "PROOF" — copy a contiguous span (one or a few \
sentences / one display) that contains the defect. Do not paraphrase, do not add \
ellipses, do not fix typos. If the defect is a global omission with no single \
block, copy the most relevant span (e.g. the claim that is left unproven) and say \
so in the description.
- `error_description` is one self-contained paragraph: what is claimed, why it is \
wrong or unjustified, and the consequence for the proof. Write it so a \
mathematician can understand the defect without reading the referee report.
- If the proof has no mathematical defect, return an empty `errors` list and set \
the verdict accordingly."""

USER_TMPL = """PROBLEM: {problem}  SUBMISSION: {sub}
Published editorial decision (for your context only, do not just copy it): {editorial}

================ PROOF (verbatim; copy errored_block spans from here) ================
{proof}

================ REFEREE REVIEWS ================
{reviews}
"""

REVIEW_TMPL = """----- Reviewer {reviewer} -----
[Summary]
{summary}

[Recommendation]
{recommendation}

[Submission with this reviewer's inline comments]
{inline}
"""

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "verdict": {"type": "string", "enum": ["correct", "minor_issues_only", "flawed"]},
        "verdict_rationale": {"type": "string"},
        "errors": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "errored_block": {"type": "string"},
                    "block_location": {"type": "string"},
                    "error_description": {"type": "string"},
                    "severity": {"type": "string", "enum": ["fatal", "major", "minor"]},
                    "error_type": {
                        "type": "string",
                        "enum": ["incorrect_step", "unjustified_gap", "false_claim", "incomplete"],
                    },
                    "source_reviewers": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["title", "errored_block", "block_location", "error_description",
                             "severity", "error_type", "source_reviewers"],
            },
        },
        "secondary_issues": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "kind": {"type": "string", "enum": ["citation", "exposition", "other"]},
                    "description": {"type": "string"},
                },
                "required": ["kind", "description"],
            },
        },
    },
    "required": ["verdict", "verdict_rationale", "errors", "secondary_issues"],
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def locate_block(proof: str, block: str):
    """Return (status, start, end) of block within proof.
    status in {exact, fuzzy, not_found}. Offsets refer to the ORIGINAL proof."""
    if not block:
        return ("not_found", -1, -1)
    idx = proof.find(block)
    if idx != -1:
        return ("exact", idx, idx + len(block))
    # whitespace-insensitive: map normalized proof back to original offsets
    orig_idx = []
    norm_chars = []
    prev_space = False
    for i, ch in enumerate(proof):
        if ch.isspace():
            if prev_space:
                continue
            norm_chars.append(" ")
            orig_idx.append(i)
            prev_space = True
        else:
            norm_chars.append(ch)
            orig_idx.append(i)
            prev_space = False
    norm_proof = "".join(norm_chars).strip()
    # account for leading-space trim: rebuild orig_idx aligned to stripped string
    # simpler: redo without leading/trailing handling
    nb = _norm(block)
    j = norm_proof.find(nb)
    if j == -1:
        return ("not_found", -1, -1)
    # find original offsets: recompute mapping without the strip offset issue
    # Rebuild a clean mapping of normalized(non-strip) -> original
    norm2, idx2 = [], []
    prev_space = False
    for i, ch in enumerate(proof):
        if ch.isspace():
            if prev_space:
                continue
            norm2.append(" ")
            idx2.append(i)
            prev_space = True
        else:
            norm2.append(ch)
            idx2.append(i)
            prev_space = False
    s = "".join(norm2)
    lead = len(s) - len(s.lstrip())
    j2 = s.find(nb)
    if j2 == -1:
        return ("not_found", -1, -1)
    start = idx2[j2]
    end_norm = j2 + len(nb) - 1
    end = idx2[min(end_norm, len(idx2) - 1)] + 1
    return ("fuzzy", start, end)


def build_prompt(entry: dict) -> str:
    reviews = []
    for r in entry["reviews"]:
        reviews.append(REVIEW_TMPL.format(
            reviewer=r["reviewer"],
            summary=r["review_summary"] or "(none)",
            recommendation=r["recommendation"] or "(none)",
            inline=r["inline_annotated_tex"] or "(none)",
        ))
    return USER_TMPL.format(
        problem=entry["problem"], sub=entry["submission"],
        editorial=entry["editorial_decision"],
        proof=entry["proof_tex"],
        reviews="\n\n".join(reviews),
    )


async def process(client, sem, entry, model, effort):
    async with sem:
        prompt = build_prompt(entry)
        last_err = None
        for attempt in range(5):
            try:
                resp = await client.responses.create(
                    model=model,
                    instructions=SYSTEM,
                    input=[{"role": "user", "content": prompt}],
                    text={"format": {"type": "json_schema", "name": "error_map",
                                     "schema": SCHEMA, "strict": True}},
                    reasoning={"effort": effort},
                    max_output_tokens=12000,
                )
                data = json.loads(resp.output_text)
                break
            except Exception as e:
                last_err = e
                await asyncio.sleep(2 * (attempt + 1))
        else:
            print(f"  !! {entry['id']} FAILED: {str(last_err)[:120]}")
            return {**_meta(entry), "status": "error", "error": str(last_err)[:300]}

        # Localize each errored block in the proof
        for err in data["errors"]:
            status, start, end = locate_block(entry["proof_tex"], err["errored_block"])
            err["match"] = status
            err["start"] = start
            err["end"] = end
        usage = getattr(resp, "usage", None)
        tok = {"in": getattr(usage, "input_tokens", 0), "out": getattr(usage, "output_tokens", 0)} if usage else {}
        print(f"  ok {entry['id']:>4}  verdict={data['verdict']:<18} errors={len(data['errors'])} "
              f"(matches: {[e['match'] for e in data['errors']]})")
        return {**_meta(entry), "status": "ok", "tokens": tok, **data}


def _meta(entry):
    return {
        "id": entry["id"], "problem": entry["problem"], "submission": entry["submission"],
        "editorial_decision": entry["editorial_decision"], "n_reviews": entry["n_reviews"],
    }


async def main(model, effort, only):
    corpus = json.loads(CORPUS.read_text())
    todo = [c for c in corpus if c["n_reviews"] > 0]
    if only:
        todo = [c for c in todo if c["id"] in set(only)]
    print(f"Mapping errors for {len(todo)} reviewed submissions "
          f"(model={model}, effort={effort})")
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    sem = asyncio.Semaphore(CONCURRENCY)
    t0 = time.perf_counter()
    results = await asyncio.gather(*[process(client, sem, c, model, effort) for c in todo])

    # include unreviewed submissions for completeness
    reviewed_ids = {c["id"] for c in todo}
    for c in corpus:
        if c["n_reviews"] == 0 and (not only or c["id"] in set(only)):
            results.append({**_meta(c), "status": "no_reviews",
                            "verdict": "not_reviewed", "errors": [], "secondary_issues": []})

    results.sort(key=lambda r: r["id"])
    OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    dt = time.perf_counter() - t0
    n_err = sum(len(r.get("errors", [])) for r in results)
    bad = [r for r in results if r.get("match_bad")]
    nf = sum(1 for r in results for e in r.get("errors", []) if e.get("match") == "not_found")
    print(f"\nDone in {dt:.0f}s. {len(results)} submissions, {n_err} mathematical errors. "
          f"{nf} blocks not located. Wrote {OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--effort", default=DEFAULT_EFFORT)
    ap.add_argument("--only", nargs="*", default=None, help="restrict to these ids e.g. 01D 04A")
    a = ap.parse_args()
    asyncio.run(main(a.model, a.effort, a.only))
