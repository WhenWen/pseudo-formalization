"""Re-judge specific block(s) in specific result file(s) with the CURRENT judge
prompt (judge_verdicts.SYSTEM/USER/SCHEMA). Updates run_judges + judge in place and
prints old->new per run. Targets via REJUDGE env: "file:SID:TAG:ID;file:SID:TAG:ID".
"""
import asyncio
import json
import os
from pathlib import Path
from openai import AsyncOpenAI
import judge_verdicts as J

HERE = Path(__file__).resolve().parent
rank = {"agree": 0, "partial": 1, "disagree": 2, None: 3}


async def judge_run(client, sem, gold, out):
    async with sem:
        for attempt in range(4):
            try:
                r = await client.responses.create(
                    model=J.MODEL, instructions=J.SYSTEM,
                    input=[{"role": "user", "content": J.USER.format(gold=gold, verifier=(out or "").strip())}],
                    text={"format": {"type": "json_schema", "name": "judge", "schema": J.SCHEMA, "strict": True}},
                    reasoning={"effort": J.EFFORT}, max_output_tokens=16000)
                return json.loads(r.output_text)
            except Exception as e:
                last = e; await asyncio.sleep(2 * (attempt + 1))
        return {"agreement": "ERROR", "verifier_found_same_error": False, "explanation": str(last)[:120]}


async def main():
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"]); sem = asyncio.Semaphore(6)
    targets = [t for t in os.environ["REJUDGE"].split(";") if t.strip()]
    for spec in targets:
        fn, sid, tag, bid = spec.split(":")
        data = json.loads((HERE / fn).read_text())
        rec = next((r for r in data if (r["sid"], r["tag"], r["id"]) == (sid, tag, bid)), None)
        if not rec:
            print(f"{fn}: {sid} {tag} {bid} NOT FOUND"); continue
        for e in rec["known_errors"]:
            e.setdefault("_sid", sid)
        gold = J.gold_text(rec["known_errors"])
        outs = rec.get("run_outputs") or [rec.get("llm_output", "")]
        verds = rec.get("run_verdicts") or [rec.get("verdict")]
        old = [(rj or {}).get("agreement") for rj in (rec.get("run_judges") or [])]
        new = []
        tasks = []
        for o, vd in zip(outs, verds):
            if vd == "CORRECT":
                new.append({"verdict": vd, "agreement": "disagree", "verifier_found_same_error": False,
                            "explanation": "Returned CORRECT — did not flag the reviewer's error."})
            else:
                tasks.append((len(new), o)); new.append(None)
        res = await asyncio.gather(*[judge_run(client, sem, gold, o) for _, o in tasks])
        for (idx, _), v in zip(tasks, res):
            new[idx] = {"verdict": verds[idx], **v}
        rec["run_judges"] = new
        best = min((rj for rj in new if rj), key=lambda j: rank.get(j["agreement"], 3), default=None)
        rec["judge"] = best
        (HERE / fn).write_text(json.dumps(data, indent=2, ensure_ascii=False))
        na = [rj["agreement"] for rj in new]
        print(f"{fn:34} {sid} {tag} {bid:8} verdict={rec.get('verdict')}")
        print(f"   old judges: {old}")
        print(f"   NEW judges: {na}")
        for rj in new:
            if rj.get("agreement") in ("agree", "partial"):
                print(f"     [{rj['agreement']}] {rj.get('explanation','')[:240]}")
                break


if __name__ == "__main__":
    asyncio.run(main())
