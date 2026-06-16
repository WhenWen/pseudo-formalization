"""Merge the misattribution-audit verdicts (misattr_audit/out/<NNN>__...json):
for every error whose true_error_block differs from the attributed block, move
critical_block to the true block and emit misattr_targets.json (the new blocks,
with their known_errors) for re-verification with v1/v2/v3.
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAPP = HERE / "pf_review_map_checked.json"
ROWS = json.loads(MAPP.read_text())
OUTDIR = HERE / "misattr_audit" / "out"
TAGS = {"theorem": "THEOREM", "proposition": "PROPOSITION", "prop": "PROPOSITION",
        "lemma": "LEMMA", "lem": "LEMMA", "claim": "CLAIM", "fact": "FACT"}


def parse_block(s):
    m = re.search(r"(theorem|proposition|prop|lemma|lem|claim|fact)\s*\.?\s*([0-9][0-9.]*)?", (s or "").lower())
    if not m:
        return None
    return (TAGS[m.group(1)], (m.group(2) or "1").rstrip("."))


def main():
    new_targets = {}   # (sid,tag,id) -> known_errors list
    changed = []
    for i, r in enumerate(ROWS):
        matches = list(OUTDIR.glob(f"{i:03d}__*.json"))
        if not matches or not matches[0].stat().st_size:
            continue
        v = json.loads(matches[0].read_text())
        r["misattr_audit"] = v
        if v.get("matches_attributed") != "no":
            continue
        nb = parse_block(v.get("true_error_block"))
        if not nb:
            continue
        old = r["critical_block"]
        changed.append((r["id"], f'{old["tag"]} {old["id"]}', f'{nb[0]} {nb[1]}',
                        r["title"], v.get("explanation", "")[:160]))
        r["critical_block"] = {"tag": nb[0], "id": nb[1]}
        key = (r["id"], nb[0], nb[1])
        ke = {"title": r["title"], "severity": r["severity"],
              "error_type": r["error_type"], "_sid": r["id"]}
        new_targets.setdefault(key, []).append(ke)

    targets = [{"sid": k[0], "tag": k[1], "id": k[2], "known_errors": ke}
               for k, ke in new_targets.items()]
    MAPP.write_text(json.dumps(ROWS, indent=2, ensure_ascii=False))
    (HERE / "misattr_targets.json").write_text(json.dumps(targets, indent=2, ensure_ascii=False))
    print(f"Reattributed {len(changed)} error(s); {len(targets)} new critical block(s) -> misattr_targets.json\n")
    for sid, old, new, title, ex in changed:
        print(f"  {sid}: {old:18} -> {new:18}  [{title[:50]}]")
        print(f"       {ex}")


if __name__ == "__main__":
    main()
