"""Build Codex prompts for a MISATTRIBUTION audit of the no-match blocks.

The earlier root audit (build_root_audit_prompts.py) only walked the ANCESTOR
chain (theorem -> prop -> lemma -> claim), so it could never reattribute an error
to a CROSS-DEPENDENCY. Example: 03C Claim 3.2.1 is correct on its own; it just
invokes Proposition 1 (via <DEPS id="3.2.1">1</DEPS>), and the real flaw is in
Proposition 1. Prop 1 is not on Claim 3.2.1's ancestor chain, so the old audit
left it on Claim 3.2.1.

Here we give Codex the FULL proof decomposition (every block's statement, proof
and DEPS), the golden reviewer comment, and the attributed block, and ask which
single block's OWN statement/proof contains the flawed step the reviewer means.

Prompts -> misattr_audit/prompts/<NNN>__<sid>__<tag><id>.txt
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROWS = json.loads((HERE / "pf_review_map_checked.json").read_text())
PF_DIR = HERE / "pf_outputs"
OUT = HERE / "misattr_audit" / "prompts"
OUT.mkdir(parents=True, exist_ok=True)

SHORT = {"THEOREM": "Theorem", "PROPOSITION": "Proposition", "LEMMA": "Lemma",
         "CLAIM": "Claim", "FACT": "Fact"}
BLOCK_RE = re.compile(
    r'<(THEOREM|PROPOSITION|LEMMA|CLAIM|FACT)_(STATEMENT|PROOF) id="([^"]+)">(.*?)</\1_\2>', re.DOTALL)
DEPS_RE = re.compile(r'<DEPS id="([^"]+)">(.*?)</DEPS>', re.DOTALL)

# The 11 no-match blocks (no agreement in any verifier version / run).
TARGETS = {
    ("03C", "CLAIM", "3.2.1"), ("04C", "PROPOSITION", "2"), ("05C", "LEMMA", "5.1"),
    ("05C", "LEMMA", "6.1"), ("05D", "PROPOSITION", "4"), ("08A", "LEMMA", "4.1"),
    ("08C", "CLAIM", "4.3.1"), ("09D", "PROPOSITION", "3"), ("09D", "PROPOSITION", "4"),
    ("10D", "LEMMA", "1.2"), ("10D", "LEMMA", "4.3"),
}


def parse(pf):
    blocks, order = {}, []
    for m in BLOCK_RE.finditer(pf):
        k = (m.group(1), m.group(3))
        if k not in blocks:
            order.append(k)
        blocks.setdefault(k, {})[m.group(2).lower()] = m.group(4).strip()
    deps = {}
    for m in DEPS_RE.finditer(pf):
        did = m.group(1)
        did = did[len("theorem_"):] if did.startswith("theorem_") else did
        deps[did] = [d.strip() for d in m.group(2).split(",") if d.strip()]
    return blocks, order, deps


def render_full(blocks, order, deps):
    parts = []
    for (tag, bid) in order:
        b = blocks[(tag, bid)]
        d = deps.get(bid, [])
        dtxt = (" [DEPENDS ON: " + ", ".join(d) + "]") if d else ""
        parts.append(f'--- {SHORT[tag]} {bid}{dtxt} ---\n'
                      f'STATEMENT: {b.get("statement","(none)")}\n'
                      f'PROOF: {b.get("proof","None — relies on its dependencies / cited results")}')
    return "\n\n".join(parts)


TMPL = """An automated proof checker attributed a known error to ONE block of a proof's pseudo-formalised decomposition (Theorem > Proposition > Lemma > Claim > Fact, where id "3.2.1" means Claim 3.2.1 sits under Lemma 3.2 under Proposition 3). It used a "deepest cited block" heuristic, which is OFTEN WRONG in a specific way:

  A block can be perfectly CORRECT on its own — it merely invokes another block (one of its DEPENDS-ON dependencies, or a sibling/parent result) whose statement or proof is where the real flaw lives. The heuristic then blames the innocent invoking block instead of the genuinely flawed one.

Your job: using the golden reviewer comment as ground truth (the error is real), read the WHOLE decomposition below and decide which single block's OWN statement or proof actually contains the flawed step the reviewer is describing.

== GOLDEN REVIEWER COMMENT (ground truth) ==
{gold}
Error summary: {desc}

== ATTRIBUTED BLOCK (the checker's guess) ==
{attributed}

== FULL PROOF DECOMPOSITION (every block; DEPENDS-ON lists each block's dependencies) ==
{full}

Decide carefully:
- is_attributed_block_correct_on_its_own: "yes" if the attributed block correctly proves its OWN stated claim given its dependencies (so the flaw the reviewer means is really in some OTHER block it relies on); "no" if the flaw is genuinely inside the attributed block's own statement/proof; "unclear" otherwise.
- true_error_block: the tag+id of the single block whose OWN statement/proof contains the reviewer's flawed step (e.g. "Proposition 1", "Lemma 5.3", "Theorem 1"). This may be a dependency, sibling, or parent of the attributed block — NOT necessarily on its ancestor chain.
- matches_attributed: "yes" if true_error_block equals the attributed block, else "no" (or "unclear").
- explanation: 1-2 sentences pinpointing the flawed step and why it lives in true_error_block rather than the attributed block.

Respond ONLY with the JSON object required by the output schema."""


def main():
    n = 0
    for i, r in enumerate(ROWS):
        cb = r.get("critical_block", {})
        key = (r["id"], cb.get("tag"), cb.get("id"))
        if key not in TARGETS:
            continue
        blocks, order, deps = parse((PF_DIR / f"{r['id']}.pf.txt").read_text())
        attributed = f'{SHORT[cb["tag"]]} {cb["id"]}'
        ab = blocks.get((cb["tag"], cb["id"]), {})
        att_txt = (f'{attributed}{(" [DEPENDS ON: " + ", ".join(deps.get(cb["id"], [])) + "]") if deps.get(cb["id"]) else ""}\n'
                   f'STATEMENT: {ab.get("statement","(none)")}\n'
                   f'PROOF: {ab.get("proof","None")}')
        gold = "\n".join(f'(Reviewer {q["reviewer"]}) "{q["quote"]}"'
                         for q in r.get("reviewer_quotes", [])) or "(none)"
        prompt = TMPL.format(gold=gold, desc=r["error_description"], attributed=att_txt,
                             full=render_full(blocks, order, deps))
        name = f'{i:03d}__{r["id"]}__{cb["tag"]}{cb["id"]}'
        (OUT / f"{name}.txt").write_text(prompt, encoding="utf-8")
        n += 1
    print(f"Wrote {n} misattribution-audit prompts -> {OUT}")


if __name__ == "__main__":
    main()
