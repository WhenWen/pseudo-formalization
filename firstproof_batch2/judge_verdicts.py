"""For every verified block, ask GPT-5.5 (high) to judge whether the BLOCK
VERIFIER's verdict agrees with the GOLDEN reviewer comment.

The reviewer's verbatim comment is presented as ground truth. The judge compares
the verifier's full output (verdict + error_description + gap_filling/audits)
against it and decides agree / partial / disagree, plus whether the verifier
identified the SAME error the reviewer did.

Inputs:  block_verify_results.json  (verifier output per block)
         pf_review_map_checked.json (verbatim reviewer_quotes per error)
Output:  verdict_judgements.json
"""

import asyncio
import json
import os
import time
from pathlib import Path

from openai import AsyncOpenAI

HERE = Path(__file__).resolve().parent
BV = json.loads((HERE / "block_verify_results.json").read_text())
MAP = json.loads((HERE / "pf_review_map_checked.json").read_text())
OUT = HERE / "verdict_judgements.json"
MODEL = os.environ.get("JUDGE_MODEL", "gpt-5.5")
EFFORT = os.environ.get("JUDGE_EFFORT", "high")
CONCURRENCY = 6

# (sid, error title) -> {reviewer_quotes, error_description}
GOLD = {}
for r in MAP:
    GOLD[(r["id"], r["title"])] = {
        "reviewer_quotes": r.get("reviewer_quotes", []),
        "error_description": r.get("error_description", ""),
    }

SYSTEM = """You are adjudicating whether an automated block verifier caught the SAME \
concrete error a human referee flagged in a piece of a mathematical proof.

The REVIEWER COMMENT is GOLDEN ground truth: the referee is correct that the stated \
error is real and is located as described. Your job is NOT to re-judge the math — \
assume the reviewer is right.

FIRST, distil the CONCRETE ESSENCE of the reviewer's error: the single specific, \
load-bearing defect — e.g. the exact false statement, the specific hypothesis / \
side-condition that is missing or violated, the specific object that is undefined / \
nonexistent / misdefined, the specific quantifier that is overstated (e.g. "a.e." \
used as "everywhere"), the specific cited result that does not exist or is misapplied, \
or the concrete counterexample. State this essence in one sentence.

THEN judge the verifier's output against THAT essence. The bar for "agree" is that the \
verifier independently puts its finger on the SAME concrete essence — the same specific \
mechanism, object, condition, quantifier, or citation — so that an expert reading the \
verifier's reasoning would conclude it found the very same defect, not merely that it \
was suspicious of the right region.

- "agree": the verifier returned INCORRECT AND its reasoning explicitly identifies the \
concrete essence of the reviewer's error (the same specific defect, by substance — not \
necessarily the same words).
- "partial": the verifier returned INCORRECT but does NOT pin the concrete essence — \
e.g. it flags the right block/step only with a generic complaint ("unjustified", \
"insufficient detail", "needs proof"), or it identifies a DIFFERENT or merely adjacent \
defect, or it gestures at the right area without naming the specific failing \
condition/object/quantifier/citation, or it hedges.
- "disagree": the verifier returned CORRECT (missed the error entirely), or its reasoning \
contradicts or mislocates the reviewer's defect.

Be strict: catching the right BLOCK with the wrong (or vague) reason is "partial", not \
"agree". Set verifier_found_same_error = true ONLY for "agree" (the concrete essence is \
explicitly identified).

REASON-PRESENTATION RULE (decisive). When the reviewer's error is that a specific \
hypothesis of a cited/used lemma does NOT hold, or that a claim is provably wrong, the \
reviewer's comment carries a CONCRETE REASON for it — the particular hypothesis that \
fails and why, or the specific mechanism / counterexample / condition that makes the \
claim false (e.g. "fails because the map is not isometric", "false because A∗B can have \
a one-dimensional summand", "holds only μ-a.e., not for every x", "the cited theorem \
requires compactness, absent here"). In that situation, output "agree" ONLY IF the \
verifier presents that same concrete reason. It is NOT enough for the verifier to assert \
the lemma is misapplied / the hypothesis is unmet / the claim is unjustified or false in \
the abstract: if it does not state the SPECIFIC reason the reviewer gives (the actual \
failing hypothesis or the actual mechanism of falsity), the verdict is "partial". Only \
when the reviewer gives no concrete reason (just locates the gap) does identifying the \
gap itself suffice for "agree".

CITATION-vs-CONTENT distinction. A verifier reason of the form "the cited source / named \
result cannot be found or verified", "this citation does not state the claim", or "the \
named construction is nonstandard / not in the literature / cannot be pinned" is a \
CITATION/EXISTENCE complaint. When the reviewer's concrete reason is instead that \
specific MATHEMATICAL CONTENT is unestablished or false — particular relations, \
identities, hypotheses, or properties the reviewer names (e.g. "the valuated Plücker \
relations are not proved", "the adjacent quotient relations are not shown", "this \
inequality is false by scaling") — a citation/existence complaint does NOT match it. \
Output "agree" only if the verifier actually engages with and names that same specific \
mathematical content; merely being unable to verify the citation or the name, while the \
reviewer's point is that a specific property is unproved/false, is "partial".

EPISTEMIC-ACCESS rule (decisive, overrides surface overlap). If the verifier's STATED \
BASIS for INCORRECT is its OWN inability to retrieve / access / pin / locate / confirm a \
citation, theorem statement, or named construction (signalled by language like "not \
found", "could not be pinned", "no verbatim statement available", "cannot perform the \
audit", "UNPINNED", "unable to verify"), then it has NOT presented the reviewer's reason \
when the reviewer's reason is a substantive mathematical claim (that a property is \
unproved, that no proof exists, that a construction is nonstandard/nonexistent, or that a \
statement is false). Such a verifier is reporting a verification/access failure, not \
affirmatively establishing the defect — judge it "partial", EVEN IF it also names the \
relevant objects/relations (e.g. lists what the citation "would need to imply"). For \
"agree", the verifier must affirmatively assert the substantive defect on the merits — \
e.g. "the submission gives no proof that these are valuated matroids", "this construction \
is not a known/standard result", "this property is false" — as its own finding, not as a \
gap it merely could not check."""

USER = """GOLDEN REVIEWER COMMENT(S) (ground truth — the real, correctly-located error):
{gold}

BLOCK VERIFIER OUTPUT (verdict + reasoning to be judged):
{verifier}

First state, in one sentence, the concrete essence of the reviewer's error. Then decide \
whether the verifier's reasoning explicitly identifies that same concrete essence \
(agree), flags the block but misses or only vaguely approaches that essence (partial), \
or missed/contradicted it (disagree). Put your essence statement and the comparison in \
the explanation."""

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "agreement": {"type": "string", "enum": ["agree", "partial", "disagree"]},
        "verifier_found_same_error": {"type": "boolean"},
        "explanation": {"type": "string"},
    },
    "required": ["agreement", "verifier_found_same_error", "explanation"],
}


def gold_text(known):
    parts = []
    for e in known:
        g = GOLD.get(("", "")) if False else GOLD.get(_key(e))
        quotes = (g or {}).get("reviewer_quotes", [])
        qs = "\n".join(f'  - (Reviewer {q["reviewer"]}) "{q["quote"]}"' for q in quotes) or "  (no verbatim quote)"
        parts.append(f'• Error: {e["title"]} [{e["severity"]}/{e["error_type"]}]\n'
                     f'  Reviewer said (GOLDEN):\n{qs}')
    return "\n\n".join(parts)


def _key(e):
    return (e["_sid"], e["title"])


async def judge(client, sem, blk):
    async with sem:
        for e in blk["known_errors"]:
            e["_sid"] = blk["sid"]
        gold = gold_text(blk["known_errors"])
        verifier = (blk.get("llm_output") or blk.get("output") or "").strip()
        prompt = USER.format(gold=gold, verifier=verifier)
        last = None
        for attempt in range(4):
            try:
                resp = await client.responses.create(
                    model=MODEL, instructions=SYSTEM,
                    input=[{"role": "user", "content": prompt}],
                    text={"format": {"type": "json_schema", "name": "judge",
                                     "schema": SCHEMA, "strict": True}},
                    reasoning={"effort": EFFORT}, max_output_tokens=16000,
                )
                data = json.loads(resp.output_text)
                break
            except Exception as e:
                last = e
                await asyncio.sleep(2 * (attempt + 1))
        else:
            print(f"  !! {blk['sid']} {blk['label']} FAILED {str(last)[:80]}")
            return {**_meta(blk), "agreement": "ERROR"}
        print(f"  {blk['sid']} {blk['label']:<16} verifier={blk['verdict']:<9} "
              f"-> judge={data['agreement']:<8} same_error={data['verifier_found_same_error']}")
        return {**_meta(blk), **data}


def _meta(blk):
    return {"sid": blk["sid"], "label": blk["label"], "verifier_verdict": blk["verdict"],
            "known_errors": [{"title": e["title"], "severity": e["severity"]} for e in blk["known_errors"]]}


async def main():
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    sem = asyncio.Semaphore(CONCURRENCY)
    print(f"Judging {len(BV)} block verdicts vs golden reviewer comments (model={MODEL}, effort={EFFORT})")
    t0 = time.perf_counter()
    res = await asyncio.gather(*[judge(client, sem, b) for b in BV])
    res.sort(key=lambda r: (r["sid"], r["label"]))
    OUT.write_text(json.dumps(res, indent=2, ensure_ascii=False))
    from collections import Counter
    c = Counter(r["agreement"] for r in res)
    same = sum(1 for r in res if r.get("verifier_found_same_error"))
    print(f"\nDone in {time.perf_counter()-t0:.0f}s.  agreement: {dict(c)}")
    print(f"  verifier found the SAME error as reviewer: {same}/{len(res)}")
    print(f"Saved {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
