"""Merge Codex root-audit verdicts (root_audit/out/<NNN>__<id>.json) into the
mapping, report how often the true error block differs from the attributed deepest
block, and emit corrected_targets.json (the lowest block where each error truly
lives, ancestor-collapsed per submission) for re-verification.
"""

import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROWS = json.loads((HERE / "pf_review_map_checked.json").read_text())
OUTDIR = HERE / "root_audit" / "out"
TAGS = {"theorem": "THEOREM", "proposition": "PROPOSITION", "prop": "PROPOSITION",
        "lemma": "LEMMA", "lem": "LEMMA", "claim": "CLAIM", "fact": "FACT"}


def parse_block(s):
    """'Proposition 5' / 'Lemma 5.3' -> ('PROPOSITION','5')."""
    m = re.search(r"(theorem|proposition|prop|lemma|lem|claim|fact)\s*\.?\s*([0-9][0-9.]*)?", (s or "").lower())
    if not m:
        return None
    tag = TAGS[m.group(1)]
    bid = m.group(2) or "1"
    return (tag, bid.rstrip("."))


def depth(t):
    return 0 if t[0] == "THEOREM" else len(t[1].split("."))


def main():
    mc = Counter()
    per_sub_targets = {}
    changed = []
    for i, r in enumerate(ROWS):
        matches = list(OUTDIR.glob(f"{i:03d}__*.json"))
        v = json.loads(matches[0].read_text()) if matches and matches[0].stat().st_size else None
        deepest = max(r["pf_blocks"], key=lambda p: 0 if p["tag"] == "THEOREM" else len(p["id"].split(".")))
        deep_key = (deepest["tag"], deepest["id"])
        true_key = deep_key
        if v:
            mc[v.get("matches_attributed")] += 1
            pb = parse_block(v.get("true_error_block"))
            if v.get("matches_attributed") == "no" and pb:
                true_key = pb
                changed.append((r["id"], f'{deep_key[0]} {deep_key[1]}',
                                f'{true_key[0]} {true_key[1]}', v.get("explanation", "")[:140]))
        r["audit"] = v
        r["critical_block"] = {"tag": true_key[0], "id": true_key[1]}
        per_sub_targets.setdefault(r["id"], {}).setdefault(true_key, []).append(
            {"title": r["title"], "severity": r["severity"], "error_type": r["error_type"]})

    # Dedup by identical block only — do NOT ancestor-collapse: a true error at the
    # theorem level is a distinct critical point from one at a proposition, even
    # within the same submission.
    targets = []
    for sid, bm in per_sub_targets.items():
        for k, known in bm.items():
            targets.append({"sid": sid, "tag": k[0], "id": k[1], "known_errors": known})

    # Only re-verify blocks NOT already verified (skip leaves we already ran).
    already = set()
    bvp = HERE / "block_verify_results.json"
    if bvp.exists():
        already = {(b["sid"], b["tag"], b["id"]) for b in json.loads(bvp.read_text())}
    changed = [t for t in targets if (t["sid"], t["tag"], t["id"]) not in already]

    (HERE / "pf_review_map_checked.json").write_text(json.dumps(ROWS, indent=2, ensure_ascii=False))
    (HERE / "corrected_targets.json").write_text(json.dumps(targets, indent=2, ensure_ascii=False))
    (HERE / "corrected_targets_changed.json").write_text(json.dumps(changed, indent=2, ensure_ascii=False))
    print(f"matches_attributed: {dict(mc)}")
    print(f"blocks to RE-VERIFY (corrected & not already done): {len(changed)} "
          f"-> corrected_targets_changed.json: {[t['sid']+' '+t['tag']+' '+t['id'] for t in changed]}")
    print(f"\n{len(changed)} error(s) where the TRUE block != attributed deepest block:")
    for sid, att, tru, ex in changed:
        print(f"  {sid}: attributed {att}  ->  TRUE {tru}")
        print(f"       {ex}")
    print(f"\ncorrected verification targets (ancestor-collapsed): {len(targets)} blocks "
          f"(was 36) -> corrected_targets.json")


if __name__ == "__main__":
    main()
