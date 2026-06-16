"""Rebuild pf_review_map_checked.json from the (re-mapped) pf_review_map.json,
carrying the PF-independent fields (reviewer_quotes, codex_xcheck) from the previous
_checked by (id, title). critical_block/audit are dropped here and refilled by the
subsequent full root-audit re-run.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
new = json.loads((HERE / "pf_review_map.json").read_text())
oldc = {(r["id"], r["title"]): r for r in json.loads((HERE / "pf_review_map_checked.json").read_text())}
out = []
for r in new:
    o = oldc.get((r["id"], r["title"]), {})
    r = dict(r)
    r["reviewer_quotes"] = o.get("reviewer_quotes", [])
    r["codex_xcheck"] = o.get("codex_xcheck")
    out.append(r)
(HERE / "pf_review_map_checked.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
carried = sum(1 for r in out if r["reviewer_quotes"])
print(f"rebuilt pf_review_map_checked.json: {len(out)} rows, {carried} with reviewer_quotes carried")
