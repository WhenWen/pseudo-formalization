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

SYSTEM = """You are adjudicating whether an automated block verifier's verdict on a \
piece of a mathematical proof matches the human referee's assessment.

The REVIEWER COMMENT is GOLDEN ground truth: the referee is correct that the stated \
error is real and is located as described. Your job is NOT to re-judge the math — \
assume the reviewer is right.

You are given the verifier's full output (its CORRECT/INCORRECT verdict plus its \
reasoning) and the golden reviewer comment(s) about the same block. Decide whether \
the verifier's verdict AGREES with the reviewer:
- "agree": the verifier returned INCORRECT and its reasoning identifies essentially \
the SAME defect the reviewer describes.
- "partial": the verifier returned INCORRECT but for a DIFFERENT or only partially \
overlapping reason (it flagged something, but not the reviewer's actual defect), OR \
it hedged.
- "disagree": the verifier returned CORRECT (i.e. it missed the golden error), or its \
reasoning contradicts the reviewer.

Also set verifier_found_same_error = true only when the verifier specifically \
identifies the reviewer's defect (not merely any issue)."""

USER = """GOLDEN REVIEWER COMMENT(S) (ground truth — the real, correctly-located error):
{gold}

BLOCK VERIFIER OUTPUT (verdict + reasoning to be judged):
{verifier}

Does the verifier's verdict match the golden reviewer comment?"""

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
