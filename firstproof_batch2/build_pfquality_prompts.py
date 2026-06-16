"""Build one Codex prompt per PF file to find MALFORMED blocks — bad statement/proof
hygiene introduced by the pseudo-formalization rewrite, e.g.:
  - proof/derivation/commentary placed inside the STATEMENT,
  - PROOF that merely restates the statement (circular / trivial),
  - leftover scaffolding ("Original proof label: ...", duplicated
    "Assumptions / Conditions / Definitions" headers),
  - a STATEMENT beginning with a dangling connective (Then/Therefore) with no antecedent,
  - content placed in the wrong field.

Prompts -> pfquality/prompts/<id>.txt
"""

from pathlib import Path

HERE = Path(__file__).resolve().parent
PF_DIR = HERE / "pf_outputs"
OUT = HERE / "pfquality" / "prompts"
OUT.mkdir(parents=True, exist_ok=True)

TMPL = """You are auditing the HYGIENE of a pseudo-formalized proof. The proof is decomposed into blocks (THEOREM/PROPOSITION/LEMMA/CLAIM/FACT), each with a _STATEMENT (the precise claim and its assumptions ONLY) and a _PROOF (the justification ONLY). A well-formed block keeps the claim in the statement and the argument in the proof.

Find every MALFORMED block and classify its problem(s):
- proof_content_in_statement: the STATEMENT contains derivation/argument/commentary that belongs in the proof (e.g. "No commutativity was used ... because X = Y", chains of equalities proving the claim).
- circular_or_trivial_proof: the PROOF merely restates the statement (e.g. just "Therefore <the statement>") and contains no actual justification, because the real argument was misplaced into the statement.
- leftover_scaffolding: stray rewriter artifacts such as "Original proof label: ...", a DUPLICATED "Assumptions / Conditions / Definitions" header, or document preamble (\\title, \\maketitle, Disclaimer) embedded in a block.
- dangling_statement: the STATEMENT begins with a connective like "Then"/"Therefore"/"Hence"/"Thus" with no antecedent inside the block, so it does not stand alone.
- wrong_field: assumptions/statement/proof content placed in the wrong field generally.
- other: any other malformation; describe in the note.

Only report genuinely malformed blocks (not mere terseness). For each, give the block id (e.g. "Proposition 2"), the issue tag(s), and a short note quoting the offending text.

Respond ONLY with the JSON object required by the output schema (a "malformed" array; empty if the file is clean).

=== PSEUDO-FORMALIZED PROOF ===
{pf}
"""


def main():
    n = 0
    for f in sorted(PF_DIR.glob("*.pf.txt")):
        sid = f.name.split(".")[0]
        (OUT / f"{sid}.txt").write_text(TMPL.format(pf=f.read_text()), encoding="utf-8")
        n += 1
    print(f"Wrote {n} PF-quality prompts -> {OUT}")


if __name__ == "__main__":
    main()
