"""Block verifier v3 = web search + two upgrades over v2:
  (1) actively SEEK A COUNTEREXAMPLE to the statement (edge/scaling/small-instance),
  (2) first SEARCH & PIN DOWN the precise definition of every math term, and judge
      against those authoritative definitions.

Version map: v1 = run_block_verifier.py (no web) -> block_verify_results.json;
             v2 = run_websearch_verifier.py (web, citation fact-check) -> websearch_verify_results.json;
             v3 = this -> bv_v3_results.json.

Blind (First Proof domains blocked). Multi-run with reuse, pessimistic. N=3.
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
# V3_TARGETS: optional JSON file of blocks [{sid,tag,id,known_errors}] to restrict to
BV = json.loads((HERE / os.environ.get("V3_TARGETS", "block_verify_results.json")).read_text())
OUT = HERE / "bv_v3_results.json"
MODEL = os.environ.get("V3_MODEL", "gpt-5.5")
EFFORT = os.environ.get("V3_EFFORT", "high")
MAX_OUT = int(os.environ.get("V3_MAX_OUT", "16000"))
CONC = int(os.environ.get("V3_CONCURRENCY", "4"))
N_TOTAL = int(os.environ.get("V3_N", "3"))
CALL_TIMEOUT = int(os.environ.get("V3_CALL_TIMEOUT", "420"))  # seconds per web-search call
BLOCKED = ["1stproof.org", "github.com", "githubusercontent.com", "github.io"]

DIRECTIVE = """BLOCK VERIFIER v3 — you have WEB SEARCH. Carry out ALL THREE steps before deciding:

STEP 1 — PIN DOWN DEFINITIONS / WELL-DEFINEDNESS (web search). List every nontrivial term, object, operator, or named notion in the Assertion and its proof. For EACH one, confirm it is WELL-DEFINED in exactly one of two ways: (a) it is explicitly and unambiguously defined in the proof itself, the Contexts, or the Established Results; OR (b) it has a PRECISE standard definition that you locate and confirm via web search in authoritative sources (textbooks, papers, reference works). Judge against that authoritative/explicit definition — never silently assume a meaning. Be very strict: if a term is NEITHER defined in the given material NOR found to have a recognized definition in the literature (i.e. it appears invented, ill-defined, or used in a non-standard way — e.g. an undefined operation on an object it is not defined for, or a named object/ideal/notation that does not exist), then the argument relies on an undefined object and you MUST return INCORRECT, naming the offending term. If the proof's usage conflicts with the standard definition, that is also INCORRECT.

STEP 2 — FACT-CHECK CITATIONS (web search). For any external cited result (a named theorem, an attributed result, "[1]", "Proposition 9.1 of [X]"), verify it exists, states what the proof claims, and that its hypotheses hold in this context. A nonexistent / not-in-source / misstated / misapplied citation => INCORRECT.

STEP 3 — SEEK A COUNTEREXAMPLE. Actively try to REFUTE the Assertion (or a load-bearing claim in its proof): test edge/boundary/degenerate cases, small concrete instances, and scaling / invariance / dimensional-analysis arguments. If you find a valid counterexample, return INCORRECT and state it explicitly.

Then apply the verification and output rules below. Do NOT consult First Proof materials (1stproof.org or its GitHub); rely only on independent literature.

"""


async def main(only):
    v = ArxivComplexPseudoFormalisationVerifier(model=MODEL, effort=EFFORT, max_tokens=MAX_OUT, n_verifications=1)
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    targets = [b for b in BV if (not only or b["sid"] in set(only))]
    prior = {}
    if OUT.exists():
        for r in json.loads(OUT.read_text()):
            prior[(r["sid"], r["tag"], r["id"])] = {"outs": r.get("run_outputs", []),
                                                    "verds": r.get("run_verdicts", []),
                                                    "cits": r.get("web_citation_runs", [])}
    print(f"BV v3 (web + counterexample + definitions) on {len(targets)} blocks -> N={N_TOTAL}, blind")
    sem = asyncio.Semaphore(CONC); cache = {}; results = []

    async def one_call(label, stmt, proof, ctx, est):
        prompt = DIRECTIVE + ARXIV_COMPLEX_COMPONENT_VERIFY_PROMPT.format(
            contexts="\n\n".join(ctx) if ctx else "None",
            established_results="\n\n".join(est) if est else "None",
            assertion=f"{label}: {stmt}", proof=proof)
        async with sem:
            last = None
            for attempt in range(4):
                try:
                    resp = await asyncio.wait_for(client.responses.create(
                        model=MODEL, input=[{"role": "user", "content": prompt}],
                        tools=[{"type": "web_search", "filters": {"blocked_domains": BLOCKED}}],
                        tool_choice="auto", text={"format": {"type": "text"}},
                        reasoning={"effort": EFFORT}, max_output_tokens=MAX_OUT), timeout=CALL_TIMEOUT)
                    break
                except Exception as e:
                    last = e; await asyncio.sleep(3 * (attempt + 1))
            else:
                print(f"  !! call failed/timed out: {str(last)[:80]}")
                return None, "", 0
        out = resp.output_text or ""
        ncit = 0
        try:
            for item in resp.output:
                for c in getattr(item, "content", None) or []:
                    ncit += len(getattr(c, "annotations", None) or [])
        except Exception:
            pass
        verdict, _ = v._parse_verdict(out)
        return verdict, out, ncit

    async def run(b):
        sid = b["sid"]
        if sid not in cache:
            dec = parse_rewritten_arxiv_complex((PF_DIR / f"{sid}.pf.txt").read_text())
            cache[sid] = {k: (lbl, st, pf, ctx, est) for (k, lbl, st, pf, ctx, est) in v._build_block_inputs(dec)}
        k = RB.block_key(b["tag"], b["id"])
        if k not in cache[sid]:
            print(f"  !! {sid} {k} missing"); return
        label, stmt, proof, ctx, est = cache[sid][k]
        pk = (b["sid"], b["tag"], b["id"])
        outs = list(prior.get(pk, {}).get("outs", []))
        verds = list(prior.get(pk, {}).get("verds", []))
        cits = list(prior.get(pk, {}).get("cits", []))
        need = max(0, N_TOTAL - len(outs))
        for vd, out, nc in await asyncio.gather(*[one_call(label, stmt, proof, ctx, est) for _ in range(need)]):
            if vd is not None:
                verds.append(vd); outs.append(out); cits.append(nc)
        verdict = "INCORRECT" if "INCORRECT" in verds else "CORRECT"
        print(f"  {sid} {label:<16} -> {verdict:<9} runs={verds} cits={cits}")
        results.append({"sid": sid, "tag": b["tag"], "id": b["id"], "label": label,
                        "known_errors": b["known_errors"], "verdict": verdict,
                        "n": len(verds), "run_verdicts": verds, "run_outputs": outs,
                        "web_citation_runs": cits, "web_citations": sum(cits),
                        "llm_output": next((o for o, vd in zip(outs, verds) if vd == "INCORRECT"), outs[0] if outs else "")})

    await asyncio.gather(*[run(b) for b in targets])
    results.sort(key=lambda r: (r["sid"], r["id"]))
    OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    inc = sum(1 for r in results if r["verdict"] == "INCORRECT")
    print(f"\nDone. v3 INCORRECT(pessimistic)={inc}/{len(results)}. Saved {OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--only", nargs="*", default=None)
    asyncio.run(main(ap.parse_args().only))
