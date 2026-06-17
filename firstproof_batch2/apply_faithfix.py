"""Apply the faithfulness corrections (faithcheck/<SID>/out/*.json with faithful=="no")
back into pf_outputs/<SID>.pf.txt, replacing the flagged block's STATEMENT and PROOF
inner text with the Codex-corrected versions. Backs up the original to
pf_outputs_prefaithfix/<SID>.pf.txt.
"""
import json
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SID = os.environ.get("FAITH_SID", "10D")
PF_PATH = HERE / "pf_outputs" / f"{SID}.pf.txt"
OUTDIR = HERE / "faithcheck" / SID / "out"
BK = HERE / "pf_outputs_prefaithfix"
BK.mkdir(exist_ok=True)

TAGSPLIT = re.compile(r"^(THEOREM|PROPOSITION|LEMMA|CLAIM|FACT)_(.+)$")


def replace_block(pf, tag, bid, kind, new_inner):
    pat = re.compile(rf'(<{tag}_{kind} id="{re.escape(bid)}">)(.*?)(</{tag}_{kind}>)', re.DOTALL)
    if not pat.search(pf):
        raise SystemExit(f"!! block {tag}_{kind} id={bid} not found")
    return pat.sub(lambda m: m.group(1) + "\n" + new_inner.strip() + "\n" + m.group(3), pf, count=1)


def main():
    pf = PF_PATH.read_text()
    (BK / f"{SID}.pf.txt").write_text(pf)
    applied = []
    for f in sorted(OUTDIR.glob("*.json")):
        if not f.stat().st_size:
            continue
        v = json.loads(f.read_text())
        if v.get("faithful") != "no":
            continue
        m = TAGSPLIT.match(f.stem)            # e.g. CLAIM_3_3_1 -> CLAIM, 3_3_1
        tag, rest = m.group(1), m.group(2)
        bid = rest.replace("_", ".")
        if v.get("corrected_statement", "").strip():
            pf = replace_block(pf, tag, bid, "STATEMENT", v["corrected_statement"])
        if v.get("corrected_proof", "").strip():
            pf = replace_block(pf, tag, bid, "PROOF", v["corrected_proof"])
        applied.append(f"{tag} {bid}")
    PF_PATH.write_text(pf)
    print(f"Applied faithfulness fixes to {SID}: {applied}")
    print(f"Backup -> {BK / (SID + '.pf.txt')}")


if __name__ == "__main__":
    main()
