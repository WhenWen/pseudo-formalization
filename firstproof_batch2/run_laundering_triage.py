"""Triage the whole-proof coverage reports: for each proof, decide whether any PF
divergence is TIED TO the reviewer's actual error — i.e. the PF dropped/sanitised/
altered content such that a blind verifier would be LESS able to detect the error
(laundering), as opposed to benign omissions (title, bibliography, restructuring).

Inputs: faithcheck/coverage/<sid>.txt (coverage report) + the reviewer errors from
pf_review_map_checked.json. Output: faithcheck/triage/<sid>.json + a printed table.
"""
import asyncio
import json
import os
from pathlib import Path
from collections import defaultdict
from openai import AsyncOpenAI

HERE = Path(__file__).resolve().parent
COV = HERE / "faithcheck" / "coverage"
OUT = HERE / "faithcheck" / "triage"
OUT.mkdir(parents=True, exist_ok=True)
MODEL = os.environ.get("TR_MODEL", "gpt-5.5")
EFFORT = os.environ.get("TR_EFFORT", "high")
CONC = int(os.environ.get("TR_CONCURRENCY", "5"))

MAP = json.loads((HERE / "pf_review_map_checked.json").read_text())
ERRS = defaultdict(list)
for r in MAP:
    ERRS[r["id"]].append(r)

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "laundering_tied_to_error": {"type": "string", "enum": ["yes", "maybe", "no"]},
        "which_findings": {"type": "string", "description": "the coverage finding(s) that touch the reviewer's error, or ''"},
        "explanation": {"type": "string"},
    },
    "required": ["laundering_tied_to_error", "which_findings", "explanation"],
}

PROMPT = """A proof was pseudo-formalised (PF). Human referees found specific FATAL/MAJOR errors in it. A separate faithfulness audit compared the PF to the original author text and listed DIVERGENCES (things the PF dropped, renamed, sanitised, added, or altered).

Your job: decide whether ANY of those divergences is TIED TO the reviewer's actual error — i.e. the PF dropped or sanitised content such that a blind verifier reading ONLY the PF would be LESS able to detect the reviewer's error (this is "laundering"). Benign divergences (missing title/abstract/bibliography, lemma→proposition relabelling, added explanatory scaffolding) are NOT laundering unless they remove/soften the very thing the reviewer objected to.

Concretely, laundering = the PF dropped a definition/quantifier/name/remark/citation that the reviewer's error hinges on, so the error becomes invisible or looks correct in the PF. Example: the author defined a nonexistent "proper proximal ideal" and the PF dropped that definition, using the object as a clean given.

== REVIEWER'S ACTUAL ERROR(S) FOR THIS PROOF ==
{errors}

== FAITHFULNESS AUDIT (divergences of the PF vs author text) ==
{coverage}

Decide:
- laundering_tied_to_error: "yes" if a divergence clearly removes/softens the content the reviewer's error hinges on; "maybe" if plausibly related but unclear; "no" if all divergences are benign / unrelated to the error.
- which_findings: name the specific divergence(s) involved (or "").
- explanation: 1-3 sentences.

Respond ONLY with the JSON object required by the schema."""


def err_text(rows):
    out = []
    for r in rows:
        qs = "\n".join(f'    - (R{q["reviewer"]}) "{q["quote"]}"' for q in r.get("reviewer_quotes", []))
        out.append(f'• {r["title"]} [{r["severity"]}/{r["error_type"]}]\n  {r["error_description"]}\n{qs}')
    return "\n\n".join(out)


async def one(client, sem, sid):
    cf = COV / f"{sid}.txt"
    if not cf.exists():
        alt = HERE / "faithcheck" / "10D_coverage.txt"
        if sid == "10D" and alt.exists():
            cf = alt
        else:
            print(f"  {sid}: no coverage file", flush=True); return
    prompt = PROMPT.format(errors=err_text(ERRS[sid]), coverage=cf.read_text())
    async with sem:
        last = None
        for attempt in range(4):
            try:
                r = await client.responses.create(
                    model=MODEL, input=[{"role": "user", "content": prompt}],
                    text={"format": {"type": "json_schema", "name": "triage", "schema": SCHEMA, "strict": True}},
                    reasoning={"effort": EFFORT}, max_output_tokens=16000)
                v = json.loads(r.output_text)
                (OUT / f"{sid}.json").write_text(json.dumps(v, indent=2, ensure_ascii=False))
                print(f"  {sid}: {v['laundering_tied_to_error']:5} | {v['which_findings'][:70]}", flush=True)
                return
            except Exception as e:
                last = e; await asyncio.sleep(2 * (attempt + 1))
        print(f"  {sid}: ERROR {str(last)[:80]}", flush=True)


async def main():
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"]); sem = asyncio.Semaphore(CONC)
    sids = [s.strip() for s in os.environ.get("TR_SIDS", "").split(",") if s.strip()] or sorted(ERRS)
    print(f"Laundering triage on {len(sids)} proofs")
    await asyncio.gather(*[one(client, sem, s) for s in sids])
    # table
    print("\n=== LAUNDERING TRIAGE ===")
    for sid in sids:
        p = OUT / f"{sid}.json"
        if p.exists():
            v = json.loads(p.read_text())
            print(f"{sid:5} {v['laundering_tied_to_error']:5}  {v['which_findings'][:80]}")


if __name__ == "__main__":
    asyncio.run(main())
