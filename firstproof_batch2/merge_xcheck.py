"""Merge Codex cross-check verdicts (codex_xcheck/out/<NNN>__<id>.json) back into
pf_review_map.json by row index, producing pf_review_map_checked.json.
Prints an agreement summary."""

import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROWS = json.loads((HERE / "pf_review_map.json").read_text())
OUTDIR = HERE / "codex_xcheck" / "out"
OUT = HERE / "pf_review_map_checked.json"


def main():
    mc = Counter(); ep = Counter(); missing = 0
    for i, r in enumerate(ROWS):
        # filename starts with the zero-padded index
        matches = list(OUTDIR.glob(f"{i:03d}__*.json"))
        verdict = None
        if matches and matches[0].stat().st_size > 0:
            try:
                verdict = json.loads(matches[0].read_text())
            except Exception:
                verdict = None
        if verdict is None:
            missing += 1
        else:
            mc[verdict.get("mapping_correct")] += 1
            ep[verdict.get("error_present_in_pf")] += 1
        r["codex_xcheck"] = verdict
    OUT.write_text(json.dumps(ROWS, indent=2, ensure_ascii=False))
    print(f"Merged {len(ROWS)} rows ({missing} missing verdicts) -> {OUT}")
    print("  mapping_correct:", dict(mc))
    print("  error_present_in_pf:", dict(ep))
    # flag disagreements for quick review
    flags = [(r["id"], r["title"][:40], r["codex_xcheck"])
             for r in ROWS if r.get("codex_xcheck") and
             (r["codex_xcheck"].get("mapping_correct") != "yes"
              or r["codex_xcheck"].get("error_present_in_pf") != "yes")]
    if flags:
        print(f"\n  {len(flags)} row(s) where Codex did NOT fully agree:")
        for cid, title, v in flags:
            print(f"   - {cid}: {title}  [map={v.get('mapping_correct')}, "
                  f"err={v.get('error_present_in_pf')}] {v.get('suggested_blocks','')}")


if __name__ == "__main__":
    main()
