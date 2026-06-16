"""Judge the web-search verifier's verdicts against the golden reviewer comments
(GPT-5.5). CORRECT verdicts are auto-labelled disagree/missed; INCORRECT verdicts
are judged. Writes a `judge` field into websearch_verify_results.json.
"""
import asyncio
import json
import os
from pathlib import Path
from openai import AsyncOpenAI
import judge_verdicts as J

HERE = Path(__file__).resolve().parent
P = HERE / "websearch_verify_results.json"
WS = json.loads(P.read_text())


async def one(client, sem, gold, out):
    async with sem:
        prompt = J.USER.format(gold=gold, verifier=out.strip())
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
        if r["verdict"] == "CORRECT":
            r["judge"] = {"agreement": "disagree", "verifier_found_same_error": False,
                          "explanation": "Returned CORRECT — did not flag the reviewer's error."}
        else:
            tasks.append((r, one(client, sem, J.gold_text(r["known_errors"]), r["llm_output"])))
    res = await asyncio.gather(*[t[1] for t in tasks])
    for (r, _), v in zip(tasks, res):
        r["judge"] = v
    P.write_text(json.dumps(WS, indent=2, ensure_ascii=False))
    from collections import Counter
    c = Counter(r["judge"]["agreement"] for r in WS)
    matched = [f'{r["sid"]} {r["label"]}' for r in WS if r["judge"]["agreement"] == "agree"]
    print("web-search judge agreement:", dict(c))
    print(f"web-search MATCHED (agree): {len(matched)}/{len(WS)}")
    print("  ", matched)


if __name__ == "__main__":
    asyncio.run(main())
