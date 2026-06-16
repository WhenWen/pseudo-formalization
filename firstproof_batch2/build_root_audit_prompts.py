"""Build Codex prompts to audit, for each mapped error, WHERE the flaw truly lives:
in the attributed (deepest) block, or in a shallower/parent block (like 06D, where
the leap is in Proposition 5's proof, not the correctly-proven Lemma 5.3).

For each error we give Codex the golden reviewer comment + the full block chain
(theorem → ... → deepest), each with its statement and proof, and ask which block's
OWN statement/proof contains the flawed step.

Prompts -> root_audit/prompts/<NNN>__<id>.txt
"""

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROWS = json.loads((HERE / "pf_review_map_checked.json").read_text())
PF_DIR = HERE / "pf_outputs"
OUT = HERE / "root_audit" / "prompts"
OUT.mkdir(parents=True, exist_ok=True)

TAG_BY_DEPTH = {1: "PROPOSITION", 2: "LEMMA", 3: "CLAIM", 4: "FACT"}
SHORT = {"THEOREM": "Theorem", "PROPOSITION": "Proposition", "LEMMA": "Lemma", "CLAIM": "Claim", "FACT": "Fact"}
BLOCK_RE = re.compile(r'<(THEOREM|PROPOSITION|LEMMA|CLAIM|FACT)_(STATEMENT|PROOF) id="([^"]+)">(.*?)</\1_\2>', re.DOTALL)


def parse(pf):
    b = {}
    for m in BLOCK_RE.finditer(pf):
        b.setdefault((m.group(1), m.group(3)), {})[m.group(2).lower()] = m.group(4).strip()
    return b


def chain_of(tag, bid, theorem_ids):
    """theorem(s) -> ... -> (tag,bid), shallow to deep."""
    out = [("THEOREM", t) for t in theorem_ids]
    if tag != "THEOREM":
        parts = bid.split(".")
        out += [(TAG_BY_DEPTH[k], ".".join(parts[:k])) for k in range(1, len(parts) + 1)]
    return out


TMPL = """An automated tool found an error in a mathematical proof and attributed it to ONE block of the proof's pseudo-formalised decomposition (Theorem → Proposition → Lemma → Claim → Fact). It used a "deepest cited block" heuristic, which can be WRONG: sometimes the deepest block is a correctly-proven sub-lemma, and the actual flawed step is an unjustified inference in a PARENT block's proof that combines its sub-results.

Your job: read the golden reviewer comment (ground truth — the error is real) and the block chain below, and decide which single block's OWN statement or proof actually contains the flawed step.

== GOLDEN REVIEWER COMMENT (ground truth) ==
{gold}
Error summary: {desc}

== ATTRIBUTED BLOCK (the tool's guess for where the error is) ==
{attributed}

== BLOCK CHAIN (shallowest to deepest; each with its statement and proof) ==
{chain}

Decide:
- true_error_block: the lowest block whose OWN statement/proof contains the flawed step. If a block correctly proves its stated claim and the flaw is in how a PARENT proof uses it, the parent is the true error block.
- matches_attributed: does true_error_block equal the attributed block?
- explanation: 1-2 sentences pinpointing the flawed step.

Respond ONLY with the JSON object required by the output schema."""


def main():
    n = 0
    for i, r in enumerate(ROWS):
        pf = (PF_DIR / f"{r['id']}.pf.txt").read_text()
        blocks = parse(pf)
        tids = [k[1] for k in blocks if k[0] == "THEOREM"]
        deepest = max(r["pf_blocks"], key=lambda p: 0 if p["tag"] == "THEOREM" else len(p["id"].split(".")))
        attributed = f'{SHORT[deepest["tag"]]} {deepest["id"]}'
        chain = chain_of(deepest["tag"], deepest["id"], tids)
        parts = []
        for (tag, bid) in chain:
            b = blocks.get((tag, bid), {})
            parts.append(f'--- {SHORT[tag]} {bid} ---\nSTATEMENT: {b.get("statement","(none)")}\n'
                         f'PROOF: {b.get("proof","None")}')
        gold = "\n".join(f'(Reviewer {q["reviewer"]}) "{q["quote"]}"' for q in r.get("reviewer_quotes", [])) or "(none)"
        prompt = TMPL.format(gold=gold, desc=r["error_description"], attributed=attributed,
                             chain="\n\n".join(parts))
        (OUT / f"{i:03d}__{r['id']}.txt").write_text(prompt, encoding="utf-8")
        n += 1
    print(f"Wrote {n} root-audit prompts -> {OUT}")


if __name__ == "__main__":
    main()
