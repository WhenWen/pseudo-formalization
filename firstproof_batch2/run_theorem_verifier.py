"""Theorem-level verification AGAINST THE ORIGINAL PROBLEM STATEMENT.

The standard block verifier checks a theorem's proof against the submission's OWN
(possibly weakened/conditional) theorem statement, so it accepts proofs that prove
a different/conditional statement. Here we instead give the verifier the ORIGINAL
problem statement (what was actually asked) plus the submission's claimed theorem,
proof, and supporting propositions, and ask whether the proof establishes the
ORIGINAL. This is still blind to the reviewer comments.

Runs blind, N=3 pessimistic, on the theorem-level critical blocks.
Output: theorem_verify_results.json
"""

import asyncio
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from src.verifier.arxiv_complex_verifier import (
    ArxivComplexPseudoFormalisationVerifier, parse_rewritten_arxiv_complex)

PROBLEMS = json.loads((HERE / "problems_original.json").read_text())
MAP = json.loads((HERE / "pf_review_map_checked.json").read_text())
PF_DIR = HERE / "pf_outputs"
OUT = HERE / "theorem_verify_results.json"
MODEL, EFFORT, MAX_OUT, N = "gpt-5.5", "high", 16000, 3

PROMPT = """You are verifying whether a submitted proof actually proves the ORIGINAL problem as posed, or only a weaker / conditional / different statement.

You are given:
1. ORIGINAL PROBLEM — the exact statement that must be proved.
2. SUBMISSION'S CLAIMED THEOREM — what the submission states it proves (may differ from the original).
3. ESTABLISHED RESULTS — supporting propositions; assume these are TRUE (do not re-verify them).
4. PROOF — the submission's proof of its theorem.

Determine whether the PROOF establishes the ORIGINAL PROBLEM. Return INCORRECT if the proof:
- adds an extra hypothesis/assumption not in the original (i.e. proves only a conditional statement),
- proves a weaker conclusion, restricts to a sub-case, or handles only one branch of a required dichotomy,
- proves a different statement than asked, or
- leaves the original's required conclusion unproved.
Return CORRECT only if the proof fully establishes the ORIGINAL PROBLEM as stated. Do not penalise terseness or routine gap-filling within an otherwise-complete argument; focus solely on SCOPE — is the thing proved the thing asked?

End your response with exactly:
<verdict>CORRECT or INCORRECT</verdict>
<error_description>If INCORRECT: state precisely what was proved instead of the original (the extra assumption, the missing case, or the weakened conclusion). If CORRECT: leave empty.</error_description>

=== ORIGINAL PROBLEM ===
{original}

=== SUBMISSION'S CLAIMED THEOREM ===
{claimed}

=== ESTABLISHED RESULTS (assume true) ===
{established}

=== PROOF ===
{proof}
"""


async def main():
    targets = sorted({r["id"] for r in MAP if (r.get("critical_block") or {}).get("tag") == "THEOREM"})
    print(f"Theorem-vs-original verification on {targets} (model={MODEL}, N={N}, blind)")
    v = ArxivComplexPseudoFormalisationVerifier(model=MODEL, effort=EFFORT, max_tokens=MAX_OUT, n_verifications=N)
    sem = asyncio.Semaphore(4)
    results = []

    async def run(sid):
        dec = parse_rewritten_arxiv_complex((PF_DIR / f"{sid}.pf.txt").read_text())
        binputs = {k: (lbl, st, pf, ctx, est) for (k, lbl, st, pf, ctx, est) in v._build_block_inputs(dec)}
        # use the first theorem
        tkey = next(k for k in binputs if k.startswith("theorem_"))
        _, stmt, proof, _, est = binputs[tkey]
        prompt = PROMPT.format(original=PROBLEMS[sid[:2]], claimed=stmt,
                               established="\n\n".join(est) if est else "None", proof=proof)

        async def one():
            async with sem:
                out, _u = await v._completion_text_only(prompt)
            verdict, _ = v._parse_verdict(out)
            return verdict, out
        runs = await asyncio.gather(*[one() for _ in range(N)])
        rvs = [r[0] for r in runs]
        verdict = "INCORRECT" if "INCORRECT" in rvs else "CORRECT"  # pessimistic
        print(f"  {sid} Theorem 1 (vs ORIGINAL) -> {verdict}  runs={rvs}")
        results.append({"sid": sid, "tag": "THEOREM", "id": "1",
                        "verdict": verdict, "run_verdicts": rvs,
                        "run_outputs": [r[1] for r in runs]})

    await asyncio.gather(*[run(s) for s in targets])
    results.sort(key=lambda r: r["sid"])
    OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    inc = sum(1 for r in results if r["verdict"] == "INCORRECT")
    print(f"\nAgainst ORIGINAL statement: {inc}/{len(results)} now flagged INCORRECT "
          f"(standard verifier had flagged 0 of these). Saved {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
