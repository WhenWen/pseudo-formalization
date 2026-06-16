"""Apply Codex local fixes to the PF files and classify each proof:
  - all_local : every malformed block is locally fixable -> apply fixes in place
                (re-verify + re-judge next).
  - needs_repf: >=1 block is impossible_local -> must be re-PFed.

Reads pffix/out/<NNN>__<sid>__<block>.json (NNN = index into pfquality_findings.json).
Backs up originals to pf_outputs_premalformfix/. Writes classification to
pffix_classification.json.
"""

import json
import re
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIND = json.loads((HERE / "pfquality_findings.json").read_text())
PF_DIR = HERE / "pf_outputs"
BACKUP = HERE / "pf_outputs_premalformfix"
BACKUP.mkdir(exist_ok=True)
TAGS = {"theorem": "THEOREM", "proposition": "PROPOSITION", "prop": "PROPOSITION",
        "lemma": "LEMMA", "lem": "LEMMA", "claim": "CLAIM", "fact": "FACT"}


def pk(s):
    m = re.search(r"(theorem|proposition|prop|lemma|lem|claim|fact)\s*\.?\s*([0-9][0-9.]*)?", (s or "").lower())
    return (TAGS[m.group(1)], (m.group(2) or "1").rstrip(".")) if m else None


def replace_block(pf, tag, bid, kind, new):
    pat = re.compile(rf'(<{tag}_{kind} id="{re.escape(bid)}">)(.*?)(</{tag}_{kind}>)', re.DOTALL)
    return pat.sub(lambda m: m.group(1) + "\n" + new.strip() + "\n" + m.group(3), pf, count=1)


def main():
    outdir = HERE / "pffix" / "out"
    fixes_by_sid = defaultdict(list)   # sid -> [(tag,id,status,stmt,proof)]
    for j in sorted(outdir.glob("*.json")):
        idx = int(j.name.split("__")[0])
        f = FIND[idx]
        k = pk(f["block"])
        if not k or not j.stat().st_size:
            continue
        d = json.loads(j.read_text())
        fixes_by_sid[f["sid"]].append((k[0], k[1], d["status"], d.get("fixed_statement", ""), d.get("fixed_proof", "")))

    all_local, needs_repf = [], []
    for sid, fixes in fixes_by_sid.items():
        if any(s == "impossible_local" for (_, _, s, _, _) in fixes):
            needs_repf.append(sid)
        else:
            all_local.append(sid)

    # apply fixes to the all_local proofs
    applied = 0
    for sid in all_local:
        path = PF_DIR / f"{sid}.pf.txt"
        (BACKUP / f"{sid}.pf.txt").write_text(path.read_text())  # backup
        pf = path.read_text()
        for (tag, bid, status, stmt, proof) in fixes_by_sid[sid]:
            if stmt.strip():
                pf = replace_block(pf, tag, bid, "STATEMENT", stmt)
            if proof.strip():
                pf = replace_block(pf, tag, bid, "PROOF", proof)
            applied += 1
        path.write_text(pf)

    cls = {"all_local": sorted(all_local), "needs_repf": sorted(needs_repf),
           "impossible_blocks": [{"sid": sid, "block": f"{t} {i}"}
                                 for sid in needs_repf for (t, i, s, _, _) in fixes_by_sid[sid] if s == "impossible_local"]}
    (HERE / "pffix_classification.json").write_text(json.dumps(cls, indent=2, ensure_ascii=False))
    print(f"all_local proofs ({len(all_local)}): {sorted(all_local)}")
    print(f"  applied {applied} block fixes in place (originals -> pf_outputs_premalformfix/)")
    print(f"needs_repf proofs ({len(needs_repf)}): {sorted(needs_repf)}")
    print(f"  impossible-local blocks: {cls['impossible_blocks']}")


if __name__ == "__main__":
    main()
