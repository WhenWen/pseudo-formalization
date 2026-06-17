"""Block verifier v4 = web search + MAXIMALLY RIGOROUS definition/lemma pinning.

Upgrade over v3: v3's definition step let the model accept a "precise standard
definition" loosely, which invited charitable interpretation (it mapped invented
objects onto similar-sounding standard notions and passed them). v4 demands a
VERBATIM definition from a credible source with an EXACT name match (no casual
renaming), and for every cited lemma it pins the VERBATIM hypotheses+conclusion
and checks each assumption — watching explicitly for quantifier weakening,
overgeneralization, and field-specific failure modes.

Version map: v1 = run_block_verifier.py (no web) -> block_verify_results.json;
             v2 = run_websearch_verifier.py (web, citation fact-check) -> websearch_verify_results.json;
             v3 = run_bv_v3.py (web + definitions + counterexample) -> bv_v3_results.json;
             v4 = this -> bv_v4_results.json.

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
# V4_TARGETS: optional JSON file of blocks [{sid,tag,id,known_errors}] to restrict to
BV = json.loads((HERE / os.environ.get("V4_TARGETS", "block_verify_results.json")).read_text())
OUT = HERE / "bv_v4_results.json"
MODEL = os.environ.get("V4_MODEL", "gpt-5.5")
EFFORT = os.environ.get("V4_EFFORT", "high")
MAX_OUT = int(os.environ.get("V4_MAX_OUT", "16000"))
CONC = int(os.environ.get("V4_CONCURRENCY", "4"))
N_TOTAL = int(os.environ.get("V4_N", "3"))
CALL_TIMEOUT = int(os.environ.get("V4_CALL_TIMEOUT", "420"))  # seconds per web-search call
BLOCKED = ["1stproof.org", "github.com", "githubusercontent.com", "github.io"]

DIRECTIVE = """BLOCK VERIFIER v4 — you have WEB SEARCH. You must be MAXIMALLY RIGOROUS about definitions and cited lemmas. Charitable interpretation is forbidden: where you cannot rigorously confirm something, treat it as a defect. Carry out ALL THREE steps before deciding.

STEP 1 — DEFINITION PINNING (verbatim, exact-name). List every nontrivial term, object, operator, or named notion in the Assertion and its proof. For EACH, it is acceptable ONLY if:
  (a) it is explicitly and unambiguously defined in the proof itself, the Contexts, or the Established Results; OR
  (b) you retrieve a VERBATIM definition from a credible source (textbook, peer-reviewed paper, established reference work) via web search. Quote the definition verbatim and cite the source.
EXACT-NAME RULE: the name of the object/notion must match the source EXACTLY. No casual renaming, no "this is essentially the same as", no mapping a non-standard name onto a similar-sounding standard notion. If the proof uses a name/notation and you can only find a DIFFERENT (even if related) named object, the proof's object is NOT pinned — treat it as undefined. If a term is NEITHER defined in the given material NOR found verbatim under its exact name in a credible source, the argument relies on an undefined object: return INCORRECT and name the offending term. If the proof's usage conflicts with the verbatim definition, that is also INCORRECT.

STEP 2 — LEMMA / CITED-RESULT PINNING (verbatim hypotheses AND conclusion). For every cited or invoked external result, retrieve its VERBATIM statement — BOTH its full hypotheses and its conclusion — from a credible source, and quote it. Then go through the hypotheses ONE ASSUMPTION AT A TIME and decide, for EACH SINGLE assumption, whether it genuinely holds in the current context — list the assumption, state holds/fails, and justify. Only if every single assumption fits may the result be applied. Also confirm that the conclusion the proof uses is exactly the conclusion the source states (not a stronger or broader version). Be especially alert to OVERGENERALIZATION (a result invoked in greater generality than the source actually establishes it) and to DOMAIN / OBJECT MISMATCH (the cited result is about a different class of objects, structure, or setting than the one at hand). A nonexistent, not-in-source, misstated, overgeneralized, mismatched, or otherwise misapplied result => INCORRECT, naming the exact failing assumption or the precise mismatch between what the source states and what the proof uses.

STEP 3 — SEEK A COUNTEREXAMPLE. Actively try to REFUTE the Assertion or a load-bearing claim in its proof, using whatever methods are appropriate. If you find a valid counterexample, return INCORRECT and state it explicitly.

Default-to-INCORRECT rule: if after honest effort you cannot pin a definition verbatim under its exact name, or cannot confirm every hypothesis of a cited result, do NOT give the benefit of the doubt — return INCORRECT and say which check failed. Do not assume the author got a subtle step right just because the prose is fluent. This strict stance applies to definitions and cited/invoked results; continue to allow routine, non-load-bearing intermediate steps (terseness, skipped arithmetic, standard manipulations, minor repairable slips) to be filled as the rules below describe.

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
    print(f"BV v4 (verbatim definition/lemma pinning + counterexample) on {len(targets)} blocks -> N={N_TOTAL}, blind", flush=True)
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
                print(f"  !! call failed/timed out: {str(last)[:80]}", flush=True)
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
        results.append({"sid": sid, "tag": b["tag"], "id": b["id"], "label": label,
                        "known_errors": b["known_errors"], "verdict": verdict,
                        "n": len(verds), "run_verdicts": verds, "run_outputs": outs,
                        "web_citation_runs": cits, "web_citations": sum(cits),
                        "llm_output": next((o for o, vd in zip(outs, verds) if vd == "INCORRECT"), outs[0] if outs else "")})
        # incremental write + flushed progress so a long run is observable
        OUT.write_text(json.dumps(sorted(results, key=lambda r: (r["sid"], r["id"])),
                                  indent=2, ensure_ascii=False))
        print(f"  [{len(results)}/{len(targets)}] {sid} {label:<16} -> {verdict:<9} runs={verds} cits={cits}",
              flush=True)

    await asyncio.gather(*[run(b) for b in targets])
    results.sort(key=lambda r: (r["sid"], r["id"]))
    OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    inc = sum(1 for r in results if r["verdict"] == "INCORRECT")
    print(f"\nDone. v4 INCORRECT(pessimistic)={inc}/{len(results)}. Saved {OUT}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--only", nargs="*", default=None)
    asyncio.run(main(ap.parse_args().only))
