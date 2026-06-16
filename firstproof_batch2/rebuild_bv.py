"""Rebuild block_verify_results.json so it holds the verification of the TRUE
critical block of each error (from the audit), combining:
  - block_verify_results_deepest.json : original leaf/deepest runs (36)
  - block_verify_corrected.json       : re-verified corrected blocks (the changed ones)
keyed to corrected_targets.json (the critical block per error, deduped).
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
old = json.loads((HERE / "block_verify_results_deepest.json").read_text())
new = json.loads((HERE / "block_verify_corrected.json").read_text())
targets = json.loads((HERE / "corrected_targets.json").read_text())

idx = {}
for b in old + new:        # new overrides old on key collision
    idx[(b["sid"], b["tag"], b["id"])] = b

final, missing = [], []
for t in targets:
    k = (t["sid"], t["tag"], t["id"])
    if k in idx:
        b = {**idx[k], "known_errors": t["known_errors"]}  # attach this target's errors
        final.append(b)
    else:
        missing.append(k)

final.sort(key=lambda b: (b["sid"], b["id"]))
(HERE / "block_verify_results.json").write_text(json.dumps(final, indent=2, ensure_ascii=False))
inc = sum(1 for b in final if b["verdict"] == "INCORRECT")
print(f"rebuilt block_verify_results.json: {len(final)} critical blocks "
      f"(INCORRECT={inc}, CORRECT={len(final)-inc})")
if missing:
    print(f"  !! {len(missing)} targets missing a verification result: {missing}")
