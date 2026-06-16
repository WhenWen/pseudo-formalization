"""Per-run judge for the N=3 web-search verifier: judge each run's output against
the golden reviewer comment (CORRECT runs auto-disagree). Writes run_judges (list)
into websearch_verify_results.json so the report can show 3 web-search symbols.
"""
import asyncio
import json
import os
from pathlib import Path
from openai import AsyncOpenAI
import judge_verdicts as J

HERE = Path(__file__).resolve().parent
P = HERE / os.environ.get("JUDGE_FILE", "websearch_verify_results.json")
WS = json.loads(P.read_text())


async def one(client, sem, gold, out):
    async with sem:
        prompt = J.USER.format(gold=gold, verifier=(out or "").strip())
        for attempt in range(4):
            try:
                resp = await client.responses.create(
                    model=J.MODEL, instructions=J.SYSTEM,
                    input=[{"role": "user", "content": prompt}],
                    text={"format": {"type": "json_schema", "name": "judge", "schema": J.SCHEMA, "strict": True}},
                    reasoning={"effort": J.EFFORT}, max_output_tokens=16000)
                return json.loads(resp.output_text)
            except Exception as e:
                last = e; await asyncio.sleep(2 * (attempt + 1))
        return {"agreement": "ERROR", "verifier_found_same_error": False, "explanation": str(last)[:120]}


async def main():
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"]); sem = asyncio.Semaphore(6)
    tasks = []
    for r in WS:
        for e in r["known_errors"]:
            e["_sid"] = r["sid"]
        gold = J.gold_text(r["known_errors"])
        outs = r.get("run_outputs") or [r.get("llm_output", "")]
        rvs = r.get("run_verdicts") or [r.get("verdict")]
        r["run_judges"] = [None] * len(outs)
        for i, (o, vd) in enumerate(zip(outs, rvs)):
            if vd == "CORRECT":
                r["run_judges"][i] = {"verdict": vd, "agreement": "disagree",
                                      "verifier_found_same_error": False,
                                      "explanation": "Returned CORRECT — did not flag the reviewer's error."}
            else:
                tasks.append((r, i, one(client, sem, gold, o)))
    print(f"Judging {len(tasks)} INCORRECT web-search runs")
    res = await asyncio.gather(*[t[2] for t in tasks])
    for (r, i, _), v in zip(tasks, res):
        r["run_judges"][i] = {"verdict": (r.get("run_verdicts") or [r["verdict"]])[i], **v}
    # block-level aggregate judge = best of its runs (agree>partial>disagree)
    rank = {"agree": 0, "partial": 1, "disagree": 2, None: 3}
    for r in WS:
        best = min((rj for rj in r["run_judges"] if rj), key=lambda j: rank.get(j["agreement"], 3), default=None)
        r["judge"] = best
    P.write_text(json.dumps(WS, indent=2, ensure_ascii=False))
    from collections import Counter
    perrun = Counter(rj["agreement"] for r in WS for rj in r["run_judges"] if rj)
    matched_once = sum(1 for r in WS if any((rj or {}).get("agreement") == "agree" for rj in r["run_judges"]))
    print("per-run agreement:", dict(perrun))
    print(f"blocks matched in >=1 web-search run: {matched_once}/{len(WS)}")


if __name__ == "__main__":
    asyncio.run(main())
