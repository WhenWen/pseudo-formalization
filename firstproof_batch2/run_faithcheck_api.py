"""Re-run the PF-vs-RAW faithfulness check via the GPT-5.5 API directly (NOT the
Codex CLI), to avoid the codex 'superpowers' skill auto-injection that derailed
several sessions into ~3k-token rubber-stamp verdicts.

Reads the already-built prompts in faithcheck/<SID>/prompts/<BLOCK>.txt and writes
faithcheck/<SID>/out_api/<BLOCK>.json. Restrict to specific blocks via FC_ONLY
(comma-separated block names, e.g. LEMMA_4_3,PROPOSITION_4).
"""
import asyncio
import json
import os
from pathlib import Path
from openai import AsyncOpenAI

HERE = Path(__file__).resolve().parent
SID = os.environ.get("FAITH_SID", "10D")
PDIR = HERE / "faithcheck" / SID / "prompts"
ODIR = HERE / "faithcheck" / SID / "out_api"
ODIR.mkdir(parents=True, exist_ok=True)
MODEL = os.environ.get("FC_MODEL", "gpt-5.5")
EFFORT = os.environ.get("FC_EFFORT", "high")
MAX_OUT = int(os.environ.get("FC_MAX_OUT", "16000"))
CONC = int(os.environ.get("FC_CONCURRENCY", "4"))
SCHEMA = json.loads((HERE / "faithcheck_schema.json").read_text())

only = [s.strip() for s in os.environ.get("FC_ONLY", "").split(",") if s.strip()]


async def one(client, sem, name, prompt):
    async with sem:
        last = None
        for attempt in range(4):
            try:
                resp = await client.responses.create(
                    model=MODEL, input=[{"role": "user", "content": prompt}],
                    text={"format": {"type": "json_schema", "name": "faithcheck",
                                     "schema": SCHEMA, "strict": True}},
                    reasoning={"effort": EFFORT}, max_output_tokens=MAX_OUT)
                v = json.loads(resp.output_text)
                (ODIR / f"{name}.json").write_text(json.dumps(v, indent=2, ensure_ascii=False))
                print(f"  {name:16} -> {v['faithful']:8} {v['mismatch_description'][:80]}", flush=True)
                return
            except Exception as e:
                last = e; await asyncio.sleep(2 * (attempt + 1))
        print(f"  {name:16} -> ERROR {str(last)[:80]}", flush=True)


async def main():
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"]); sem = asyncio.Semaphore(CONC)
    names = [p.stem for p in sorted(PDIR.glob("*.txt")) if (not only or p.stem in only)]
    print(f"Faithcheck via {MODEL} (effort={EFFORT}) on {len(names)} block(s): {names}")
    await asyncio.gather(*[one(client, sem, n, (PDIR / f"{n}.txt").read_text()) for n in names])
    print("Done ->", ODIR)


if __name__ == "__main__":
    asyncio.run(main())
