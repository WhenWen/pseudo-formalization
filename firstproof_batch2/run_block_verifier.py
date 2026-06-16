"""Run the (blind) block verifier on the ancestor-collapsed deepest mapped block
of each error, USING THE CODEBASE'S OWN machinery:

  parse_rewritten_arxiv_complex(pf_text) -> decomposition
  ArxivComplexPseudoFormalisationVerifier._build_block_inputs(decomposition)
  verifier._run_single_verification(label, statement, proof, ctx, est)

This guarantees contexts / established-results assembly, the prompt, and verdict
parsing are EXACTLY the pipeline's. The verifier sees only PF block content —
reviewer/error text is never sent; known errors are attached to results for
post-hoc scoring only.

Model: gpt-5.5, high reasoning, max_output_tokens=16000, N=1 (n_verifications=1).
Output: block_verify_results.json
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))

from src.verifier.arxiv_complex_verifier import (
    ArxivComplexPseudoFormalisationVerifier,
    parse_rewritten_arxiv_complex,
)

MAP = json.loads((HERE / "pf_review_map_checked.json").read_text())
PF_DIR = HERE / "pf_outputs"
OUT = HERE / "block_verify_results.json"

MODEL = os.environ.get("BV_MODEL", "gpt-5.5")
EFFORT = os.environ.get("BV_EFFORT", "high")
MAX_OUT = int(os.environ.get("BV_MAX_OUT", "16000"))
CONCURRENCY = int(os.environ.get("BV_CONCURRENCY", "5"))


def block_key(tag, bid):
    """Map (tag,id) to the codebase _build_block_inputs key."""
    return f"{tag.lower()}_{bid.replace('.', '_')}"


def depth(pb):
    return 0 if pb["tag"] == "THEOREM" else len(pb["id"].split("."))


def is_ancestor(a, b):
    if a == b:
        return False
    if a[0] == "THEOREM" and b[0] != "THEOREM":
        return True
    pa, pb = a[1].split("."), b[1].split(".")
    return len(pa) < len(pb) and pb[:len(pa)] == pa


def collapsed_targets():
    """Per submission: deepest block per error, then drop any block that is an
    ancestor of another target (take the deeper one). Returns
    {sid: {(tag,id): [known_error,...]}}."""
    by_sub = {}
    for r in MAP:
        by_sub.setdefault(r["id"], []).append(r)
    out = {}
    for sid, ers in by_sub.items():
        deep = {}
        for r in ers:
            pb = max(r["pf_blocks"], key=depth)
            deep.setdefault((pb["tag"], pb["id"]), []).append(
                {"title": r["title"], "severity": r["severity"], "error_type": r["error_type"]})
        keys = set(deep)
        keep = {k: deep[k] for k in keys if not any(is_ancestor(k, y) for y in keys)}
        # reassign dropped ancestors' errors to the deeper descendant that absorbed them
        for k in keys - set(keep):
            for desc in keep:
                if is_ancestor(k, desc):
                    keep[desc] = keep[desc] + deep[k]
                    break
        out[sid] = keep
    return out


async def main(limit, only):
    targets = collapsed_targets()
    if only:
        targets = {s: v for s, v in targets.items() if s in set(only)}

    verifier = ArxivComplexPseudoFormalisationVerifier(
        model=MODEL, effort=EFFORT, max_tokens=MAX_OUT, n_verifications=1,
        block_verifier=True, meta_verify=False, faithfulness_check=False,
    )

    # Build the work list using the codebase's own block-input assembly.
    work = []   # (sid, tag, id, known, label, statement, proof, ctx, est)
    missing = []
    for sid, blockmap in targets.items():
        decomp = parse_rewritten_arxiv_complex((PF_DIR / f"{sid}.pf.txt").read_text())
        binputs = {k: (label, stmt, proof, ctx, est)
                   for (k, label, stmt, proof, ctx, est) in verifier._build_block_inputs(decomp)}
        for (tag, bid), known in blockmap.items():
            k = block_key(tag, bid)
            if k not in binputs:
                missing.append(f"{sid}:{k}")
                continue
            label, stmt, proof, ctx, est = binputs[k]
            work.append((sid, tag, bid, known, label, stmt, proof, ctx, est))
    if limit > 0:
        work = work[:limit]
    if missing:
        print(f"!! {len(missing)} target blocks not found in decomposition: {missing}")
    print(f"Block-verify {len(work)} blocks (codebase machinery; model={MODEL}, "
          f"effort={EFFORT}, max_out={MAX_OUT}, N=1) — BLIND")

    sem = asyncio.Semaphore(CONCURRENCY)
    results = []

    async def run(sid, tag, bid, known, label, stmt, proof, ctx, est):
        async with sem:
            r = await verifier._run_single_verification(label, stmt, proof, ctx, est)
        verdict = "CORRECT" if r.get("score") == 7 else "INCORRECT"
        u = r.get("usage") or {}
        kn = ",".join(e["severity"][0] for e in known)
        print(f"  {sid} {label:<14} -> {verdict:<9} (known:{kn}, "
              f"out={u.get('output_tokens','?')})")
        results.append({
            "sid": sid, "tag": tag, "id": bid, "label": label,
            "known_errors": known, "verdict": verdict,
            "score": r.get("score"), "output": r.get("output"),
            "llm_output": r.get("llm_output"),
            "usage": {"input": u.get("input_tokens"), "output": u.get("output_tokens"),
                      "reasoning": (u.get("output_tokens_details") or {}).get("reasoning_tokens")},
        })

    t0 = time.perf_counter()
    await asyncio.gather(*[run(*w) for w in work])
    results.sort(key=lambda r: (r["sid"], r["id"]))
    OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    dt = time.perf_counter() - t0
    inc = sum(1 for r in results if r["verdict"] == "INCORRECT")
    cor = sum(1 for r in results if r["verdict"] == "CORRECT")
    out_tok = sum((r["usage"].get("output") or 0) for r in results)
    print(f"\nDone in {dt:.0f}s. INCORRECT(caught)={inc}  CORRECT(missed)={cor}")
    print(f"output tokens: {out_tok:,} -> ${out_tok/1e6*10:.2f} @ $10/M out. Saved {OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=-1)
    ap.add_argument("--only", nargs="*", default=None)
    asyncio.run(main(*vars(ap.parse_args()).values()))
