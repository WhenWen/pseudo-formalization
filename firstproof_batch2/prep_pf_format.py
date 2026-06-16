"""Build re-PF prompts for the needs_repf proofs (those with impossible-local
malformed blocks) using the arxiv PF prompt + a FORMAT-strictness addendum that
forbids the malformations we observed (proof content in statements, trivial/circular
proofs, leftover scaffolding, dangling statements).

Prompts -> pf_prompts_format/<id>.prompt.txt
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from src.verifier.arxiv_complex_prompts import ARXIV_COMPLEX_REWRITE_PROMPT

IDS = json.loads((HERE / "pffix_classification.json").read_text())["needs_repf"]
BY_ID = {c["id"]: c for c in json.loads((HERE / "corpus.json").read_text())}

PDF_LINE = ("Now rewrite the following paper in this format. The PDF is attached "
            "as a separate file; the raw LaTeX source is below.")
NO_PDF_LINE = ("Now rewrite the following proof in this format. No PDF is attached; "
               "the raw LaTeX source below is the complete and authoritative source. "
               "This is a single self-contained theorem with its proof, so expect "
               "exactly one THEOREM_STATEMENT.")

FORMAT_ADDENDUM = r"""

============================== FORMAT REQUIREMENTS (OVERRIDING) ==============================
Keep STATEMENT and PROOF strictly separated in EVERY block:
1. A *_STATEMENT contains ONLY the assumptions/conditions/definitions and the precise claim. It MUST NOT contain any derivation, computation chain, justification, or commentary (e.g. "No commutativity was used because X = Y", "perimeter = 2\sqrt3", "Being flat, it self-intersects", "since X is integer-valued ..."). All such content belongs in the *_PROOF.
2. A *_PROOF must contain the ACTUAL justification. It MUST NOT merely restate the claim (e.g. just "Therefore <the statement>"); if the only content would be a restatement, the real argument has been misplaced — put it here instead, or write exactly None.
3. Emit NO leftover scaffolding: no "Original proof label: ...", no duplicated "Assumptions / Conditions / Definitions" header inside a block, no document preamble (\title, \author, \maketitle, Disclaimer, Problem Statement headers) inside any block.
4. A STATEMENT must stand alone: do not begin it with a bare connective ("Then", "Therefore", "Hence", "Thus", "Consequently") that refers to text outside the block; restate the needed antecedent in the assumptions.
Faithfulness still holds: do not add or drop mathematical content; only place each piece in the correct field.
================================================================================================
"""


def main():
    out = HERE / "pf_prompts_format"
    out.mkdir(exist_ok=True)
    base = ARXIV_COMPLEX_REWRITE_PROMPT.replace(PDF_LINE, FORMAT_ADDENDUM + "\n" + NO_PDF_LINE)
    for cid in IDS:
        (out / f"{cid}.prompt.txt").write_text(base.format(paper_tex=BY_ID[cid]["proof_tex"]), encoding="utf-8")
    print(f"Wrote format-strict re-PF prompts for {IDS} -> {out}")


if __name__ == "__main__":
    main()
