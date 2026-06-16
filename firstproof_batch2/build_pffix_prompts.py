"""Build one Codex prompt per malformed block (from pfquality_findings.json) asking
Codex to FIX it LOCALLY — redistribute content within the block so the STATEMENT
holds only the claim+assumptions and the PROOF holds only the justification, and
drop leftover scaffolding. If a clean within-block fix is impossible (e.g. the real
argument lives in other blocks, so the proof would be empty/circular, or the
statement depends on undefined objects), set status=impossible_local.

Prompts -> pffix/prompts/<NNN>__<sid>__<block>.txt
"""

import json
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIND = json.loads((HERE / os.environ.get("PFFIX_FINDINGS", "pfquality_findings.json")).read_text())
PF_DIR = HERE / os.environ.get("PFFIX_PFSRC", "pf_outputs")
OUT = HERE / os.environ.get("PFFIX_PROMPTS", "pffix/prompts")
OUT.mkdir(parents=True, exist_ok=True)
TAGS = {"theorem": "THEOREM", "proposition": "PROPOSITION", "prop": "PROPOSITION",
        "lemma": "LEMMA", "lem": "LEMMA", "claim": "CLAIM", "fact": "FACT"}
BLOCK_RE = re.compile(r'<(THEOREM|PROPOSITION|LEMMA|CLAIM|FACT)_(STATEMENT|PROOF) id="([^"]+)">(.*?)</\1_\2>', re.DOTALL)


def pk(s):
    m = re.search(r"(theorem|proposition|prop|lemma|lem|claim|fact)\s*\.?\s*([0-9][0-9.]*)?", (s or "").lower())
    return (TAGS[m.group(1)], (m.group(2) or "1").rstrip(".")) if m else None


def parse(pf):
    b = {}
    for m in BLOCK_RE.finditer(pf):
        b.setdefault((m.group(1), m.group(3)), {})[m.group(2).lower()] = m.group(4).strip()
    return b


TMPL = """A block of a pseudo-formalized proof is MALFORMED. Fix it LOCALLY — using ONLY the text already in this block — so that:
- STATEMENT contains only the assumptions/conditions/definitions and the precise claim (no derivation, no commentary, no proof steps),
- PROOF contains the justification (the argument that was misplaced into the statement should be moved here),
- leftover scaffolding is removed (e.g. "Original proof label: ...", duplicated "Assumptions / Conditions / Definitions" headers, document preamble/disclaimer).
Preserve the mathematics verbatim — only MOVE text between fields and delete scaffolding; do NOT invent new arguments or change the math.

Set status="impossible_local" if a clean within-block fix is NOT possible using only this block's text — e.g. the PROOF would be empty/circular because the real argument genuinely lives in other blocks, or the STATEMENT relies on objects defined nowhere in this block. In that case still return your best-effort fields and explain in reason.

Flagged issues: {issues}
Auditor note: {note}

=== CURRENT STATEMENT ===
{statement}

=== CURRENT PROOF ===
{proof}

Respond ONLY with the JSON object required by the output schema (fixed_statement, fixed_proof, status, reason)."""


def main():
    n = 0
    for i, f in enumerate(FIND):
        k = pk(f["block"])
        if not k:
            continue
        pf = parse((PF_DIR / f"{f['sid']}.pf.txt").read_text())
        b = pf.get(k, {})
        prompt = TMPL.format(issues=", ".join(f["issues"]), note=f.get("note", ""),
                             statement=b.get("statement", "(none)"), proof=b.get("proof", "None"))
        safe = f["block"].replace(" ", "").replace(".", "")
        (OUT / f"{i:03d}__{f['sid']}__{safe}.txt").write_text(prompt, encoding="utf-8")
        n += 1
    print(f"Wrote {n} fix prompts -> {OUT}")


if __name__ == "__main__":
    main()
