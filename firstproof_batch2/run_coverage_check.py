"""Whole-proof coverage check via GPT-5.5: compare the FULL raw author proof
against the FULL reassembled PF and report anything the PF DROPS / RENAMES /
SANITISES / ADDS / ALTERS. This catches laundering that per-block faithfulness
checks structurally miss (e.g. a definition dropped between blocks).

Validated on 10D (it flagged the dropped 'norm-closed proper proximal ideal'
definition that every per-block check passed).

Outputs -> faithcheck/coverage/<sid>.txt (+ <sid>.meta.json with token usage).
Restrict via CC_SIDS (comma-separated); default = all proofs with raw+PF.
"""
import asyncio
import json
import os
from pathlib import Path
from openai import AsyncOpenAI

HERE = Path(__file__).resolve().parent
RAW_DIR = HERE / "pf_clean_proofs"
PF_DIR = HERE / "pf_outputs"
OUT = HERE / "faithcheck" / "coverage"
OUT.mkdir(parents=True, exist_ok=True)
MODEL = os.environ.get("CC_MODEL", "gpt-5.5")
EFFORT = os.environ.get("CC_EFFORT", "high")
MAX_OUT = int(os.environ.get("CC_MAX_OUT", "16000"))
CONC = int(os.environ.get("CC_CONCURRENCY", "4"))

PROMPT = """You are auditing whether a pseudo-formalisation (PF) of a math proof FAITHFULLY and COMPLETELY preserves the original author proof. This is a WHOLE-PROOF coverage check (not block by block).

Compare the FULL original author proof against the FULL reassembled PF below. Report every place where the PF, taken as a whole, DROPS, RENAMES, SANITISES, ADDS, or ALTERS content relative to the author — paying special attention to:
- definitions the author explicitly stated that are MISSING from the PF (e.g. an object the author defined but the PF only uses as if given);
- objects/notions whose author-given NAME was changed or softened (e.g. a specific possibly-nonstandard/nonexistent name replaced by a generic one);
- citations/attributions the author gave that the PF dropped, or that the PF added;
- hypotheses, quantifiers, or claims altered in strength (e.g. "almost every" vs "every", a dropped side-condition).
For each finding: quote the author's text, quote (or note the absence in) the PF, and explain why it matters. If the PF is a faithful and complete rendering, say so explicitly. End with a one-line VERDICT: FAITHFUL or HAS_DIVERGENCES.

== ORIGINAL AUTHOR PROOF ==
{raw}

== FULL REASSEMBLED PF ==
{pf}
"""


async def one(client, sem, sid):
    raw = (RAW_DIR / f"{sid}.tex").read_text()
    pf = (PF_DIR / f"{sid}.pf.txt").read_text()
    prompt = PROMPT.format(raw=raw, pf=pf)
    async with sem:
        last = None
        for attempt in range(4):
            try:
                r = await client.responses.create(
                    model=MODEL, input=[{"role": "user", "content": prompt}],
                    text={"format": {"type": "text"}}, reasoning={"effort": EFFORT},
                    max_output_tokens=MAX_OUT)
                txt = r.output_text or ""
                (OUT / f"{sid}.txt").write_text(txt)
                rt = getattr(getattr(r.usage, "output_tokens_details", None), "reasoning_tokens", None)
                (OUT / f"{sid}.meta.json").write_text(json.dumps(
                    {"output_tokens": r.usage.output_tokens, "reasoning_tokens": rt}))
                verdict = "HAS_DIVERGENCES" if "HAS_DIVERGENCES" in txt else (
                    "FAITHFUL" if "FAITHFUL" in txt else "?")
                print(f"  {sid}: {verdict:16} (reason={rt}) -> faithcheck/coverage/{sid}.txt", flush=True)
                return
            except Exception as e:
                last = e; await asyncio.sleep(2 * (attempt + 1))
        print(f"  {sid}: ERROR {str(last)[:100]}", flush=True)


async def main():
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"]); sem = asyncio.Semaphore(CONC)
    sids = [s.strip() for s in os.environ.get("CC_SIDS", "").split(",") if s.strip()]
    if not sids:
        sids = sorted(p.stem.replace(".pf", "") for p in PF_DIR.glob("*.pf.txt")
                      if (RAW_DIR / f"{p.stem.replace('.pf','')}.tex").exists())
    print(f"Coverage check ({MODEL}, effort={EFFORT}) on {len(sids)} proof(s): {sids}")
    await asyncio.gather(*[one(client, sem, s) for s in sids])
    print("Done ->", OUT)


if __name__ == "__main__":
    asyncio.run(main())
