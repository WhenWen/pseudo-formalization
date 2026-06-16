"""Block verifier WITH web search — fact-checks external citations.

Same blind component-verification as run_block_verifier, but (a) prepends a
directive to fact-check any external reference and (b) enables the OpenAI
web_search tool. Run on the critical blocks; compare against the no-search run,
especially on the hallucinated/wrong-citation misses.

Output: websearch_verify_results.json
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from openai import AsyncOpenAI

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from src.verifier.arxiv_complex_verifier import (
    ArxivComplexPseudoFormalisationVerifier, parse_rewritten_arxiv_complex)
from src.verifier.arxiv_complex_prompts import ARXIV_COMPLEX_COMPONENT_VERIFY_PROMPT
import run_block_verifier as RB

PF_DIR = HERE / "pf_outputs"
BV = json.loads((HERE / "block_verify_results.json").read_text())  # critical blocks + known_errors
OUT = HERE / "websearch_verify_results.json"
MODEL = os.environ.get("WS_MODEL", "gpt-5.5")
EFFORT = os.environ.get("WS_EFFORT", "high")
MAX_OUT = int(os.environ.get("WS_MAX_OUT", "16000"))
CONC = int(os.environ.get("WS_CONCURRENCY", "4"))

DIRECTIVE = """WEB SEARCH IS AVAILABLE — FACT-CHECK EXTERNAL CITATIONS.
If the Proposed Proof (or any Established Result it relies on) invokes an EXTERNAL result — a named theorem/inequality, an attributed result, or a citation such as "[1]" or "Proposition 9.1 of [X]" — you MUST use web search to verify, for each such citation:
  (a) the cited work/result actually exists,
  (b) it states what the proof claims it states, and
  (c) its hypotheses are genuinely satisfied in the current context.
Return INCORRECT if a cited result does not exist, is not contained in the cited source, is misstated, or is misapplied (hypotheses not met) — and name the specific failure in the error description.
If the proof invokes NO external citation, do not search; verify the mathematics normally.
Do NOT consult the "First Proof" project materials (1stproof.org or its GitHub repo) or any page that reproduces these specific competition problems, their solutions, or their referee reviews; rely only on independent mathematical literature (papers, journals, textbooks).
Follow the output-format and gap-filling rules below as usual.

"""

# block the First Proof sources so search can't surface the problems/solutions/reviews
BLOCKED = ["1stproof.org", "github.com", "githubusercontent.com", "github.io"]


def parse_verdict(v, out):
    verdict, _ = v._parse_verdict(out)
    return verdict


async def main(only):
    v = ArxivComplexPseudoFormalisationVerifier(model=MODEL, effort=EFFORT, max_tokens=MAX_OUT, n_verifications=1)
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    targets = [b for b in BV if (not only or b["sid"] in set(only))]
    print(f"Web-search verify {len(targets)} critical blocks (model={MODEL}, effort={EFFORT}, web_search ON, blind)")
    sem = asyncio.Semaphore(CONC)
    # cache block inputs per submission
    cache = {}
    results = []

    async def run(b):
        sid = b["sid"]
        if sid not in cache:
            dec = parse_rewritten_arxiv_complex((PF_DIR / f"{sid}.pf.txt").read_text())
            cache[sid] = {k: (lbl, st, pf, ctx, est) for (k, lbl, st, pf, ctx, est) in v._build_block_inputs(dec)}
        k = RB.block_key(b["tag"], b["id"])
        if k not in cache[sid]:
            print(f"  !! {sid} {k} not in decomposition"); return
        label, stmt, proof, ctx, est = cache[sid][k]
        prompt = DIRECTIVE + ARXIV_COMPLEX_COMPONENT_VERIFY_PROMPT.format(
            contexts="\n\n".join(ctx) if ctx else "None",
            established_results="\n\n".join(est) if est else "None",
            assertion=f"{label}: {stmt}", proof=proof)
        async with sem:
            last = None
            for attempt in range(4):
                try:
                    resp = await client.responses.create(
                        model=MODEL, input=[{"role": "user", "content": prompt}],
                        tools=[{"type": "web_search", "filters": {"blocked_domains": BLOCKED}}],
                        tool_choice="auto",
                        text={"format": {"type": "text"}},
                        reasoning={"effort": EFFORT}, max_output_tokens=MAX_OUT)
                    break
                except Exception as e:
                    last = e; await asyncio.sleep(3 * (attempt + 1))
            else:
                print(f"  !! {sid} {label} FAILED {str(last)[:90]}"); return
        out = resp.output_text or ""
        verdict = parse_verdict(v, out)
        # count web-search citations
        ncit = 0
        try:
            for item in resp.output:
                for c in getattr(item, "content", None) or []:
                    ncit += len(getattr(c, "annotations", None) or [])
        except Exception:
            pass
        kn = ",".join(e["severity"][0] for e in b["known_errors"])
        print(f"  {sid} {label:<16} -> {verdict:<9} (known:{kn}, web_citations={ncit})")
        results.append({"sid": sid, "tag": b["tag"], "id": b["id"], "label": label,
                        "known_errors": b["known_errors"], "verdict": verdict,
                        "web_citations": ncit, "llm_output": out})

    await asyncio.gather(*[run(b) for b in targets])
    results.sort(key=lambda r: (r["sid"], r["id"]))
    OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    inc = sum(1 for r in results if r["verdict"] == "INCORRECT")
    print(f"\nDone. INCORRECT={inc}/{len(results)}. Saved {OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--only", nargs="*", default=None)
    asyncio.run(main(ap.parse_args().only))
