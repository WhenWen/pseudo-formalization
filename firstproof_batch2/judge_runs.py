"""Judge EACH of the 3 block-verifier runs (N=3) against the golden reviewer
comment, so the report can show three separate verdicts and three match-judgements
per block. CORRECT runs are auto-labelled disagree/missed (no API); INCORRECT runs
are judged by GPT-5.5. Writes `run_judges` (list, one per run) into
block_verify_results.json.
"""

import asyncio
import json
import os
import time
from pathlib import Path

from openai import AsyncOpenAI
import judge_verdicts as J  # reuse GOLD, gold_text, SYSTEM, USER, SCHEMA, MODEL, EFFORT

HERE = Path(__file__).resolve().parent
BVPATH = HERE / "block_verify_results.json"
BV = json.loads(BVPATH.read_text())


async def judge_one(client, sem, gold, verifier_output):
    async with sem:
        prompt = J.USER.format(gold=gold, verifier=verifier_output.strip())
        last = None
        for attempt in range(4):
            try:
                resp = await client.responses.create(
                    model=J.MODEL, instructions=J.SYSTEM,
                    input=[{"role": "user", "content": prompt}],
                    text={"format": {"type": "json_schema", "name": "judge",
                                     "schema": J.SCHEMA, "strict": True}},
                    reasoning={"effort": J.EFFORT}, max_output_tokens=16000,
                )
                return json.loads(resp.output_text)
            except Exception as e:
                last = e
                await asyncio.sleep(2 * (attempt + 1))
        return {"agreement": "ERROR", "verifier_found_same_error": False,
                "explanation": str(last)[:120]}


async def main():
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    sem = asyncio.Semaphore(6)
    # build per-run tasks; CORRECT runs auto-labelled
    tasks = []  # (block_idx, run_idx, coro_or_None, auto_result)
    for bi, b in enumerate(BV):
        for e in b["known_errors"]:
            e["_sid"] = b["sid"]
        gold = J.gold_text(b["known_errors"])
        outs = b.get("run_outputs") or [b.get("llm_output")]
        rvs = b.get("run_verdicts") or [b["verdict"]]
        b["run_judges"] = [None] * len(outs)
        for ri, (o, v) in enumerate(zip(outs, rvs)):
            if v == "CORRECT":
                b["run_judges"][ri] = {"verdict": v, "agreement": "disagree",
                                       "verifier_found_same_error": False,
                                       "explanation": "Returned CORRECT — did not flag the reviewer's error."}
            else:
                tasks.append((bi, ri, judge_one(client, sem, gold, o or "")))
    print(f"Judging {len(tasks)} INCORRECT runs across {len(BV)} blocks "
          f"(model={J.MODEL}, effort={J.EFFORT})")
    t0 = time.perf_counter()
    results = await asyncio.gather(*[t[2] for t in tasks])
    for (bi, ri, _), res in zip(tasks, results):
        rv = (BV[bi].get("run_verdicts") or ["INCORRECT"])[ri]
        BV[bi]["run_judges"][ri] = {"verdict": rv, **res}
    BVPATH.write_text(json.dumps(BV, indent=2, ensure_ascii=False))
    # summary
    from collections import Counter
    c = Counter(rj["agreement"] for b in BV for rj in b["run_judges"])
    print(f"Done in {time.perf_counter()-t0:.0f}s. per-run agreement: {dict(c)}")
    # blocks where the 3 runs DISagree among themselves on match
    flips = [b["sid"] + " " + b["label"] for b in BV
             if len({rj["agreement"] for rj in b["run_judges"]}) > 1]
    print(f"blocks where the 3 runs differ in match-verdict: {len(flips)} {flips}")


if __name__ == "__main__":
    asyncio.run(main())
