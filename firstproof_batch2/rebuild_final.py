"""Assemble the final block_verify_results.json over the (post-re-PF) critical
targets, picking each block's verdict from the freshest available source.
Priority (high -> low): re-PF re-verify > current results > corrected > deepest.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
targets = json.loads((HERE / "corrected_targets.json").read_text())

SOURCES = ["block_verify_repf.json", "block_verify_results.json",
           "block_verify_corrected.json", "block_verify_results_deepest.json"]
idx = {}
for src in reversed(SOURCES):           # low priority first; high priority overwrites
    p = HERE / src
    if not p.exists():
        continue
    for b in json.loads(p.read_text()):
        idx[(b["sid"], b["tag"], b["id"])] = b

final, missing = [], []
for t in targets:
    k = (t["sid"], t["tag"], t["id"])
    if k in idx:
        final.append({**idx[k], "known_errors": t["known_errors"]})
    else:
        missing.append(k)
final.sort(key=lambda b: (b["sid"], b["id"]))
(HERE / "block_verify_results.json").write_text(json.dumps(final, indent=2, ensure_ascii=False))
inc = sum(1 for b in final if b["verdict"] == "INCORRECT")
print(f"final block_verify_results.json: {len(final)} critical blocks, INCORRECT={inc}")
if missing:
    print(f"  !! missing verification for: {missing}")
