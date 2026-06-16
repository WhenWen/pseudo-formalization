"""Prepare clean proofs + pseudo-formalisation (PF) prompts for every First-Proof
submission that has at least one FATAL error.

Clean proof = the AI-solution LaTeX (batch-2-AI-solutions/...), which carries NO
reviewer annotations -- the \\review{} boxes live only in the batch-2-reviews
files. We assert that here so the PF input is the proof alone.

Outputs:
  pf_clean_proofs/<id>.tex      clean proof, no annotations
  pf_prompts/<id>.prompt.txt    full PF rewrite prompt (arxiv prompt + proof)
  pf_fatal_ids.txt              the list of ids, one per line
"""

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent  # pseudo-formalization repo root
sys.path.insert(0, str(REPO))

from src.verifier.arxiv_complex_prompts import ARXIV_COMPLEX_REWRITE_PROMPT

CORPUS = json.loads((HERE / "corpus.json").read_text())
ERRORS = json.loads((HERE / "errors.json").read_text())
BY_ID = {c["id"]: c for c in CORPUS}

CLEAN_DIR = HERE / "pf_clean_proofs"
PROMPT_DIR = HERE / "pf_prompts"
CLEAN_DIR.mkdir(exist_ok=True)
PROMPT_DIR.mkdir(exist_ok=True)

# Banned tokens that would indicate reviewer annotation leaked into the proof.
ANNOT_PATTERNS = [r"\\review\b", r"reviewbox", r"REVIEWER COMMENT", r"\\reviewernum",
                  r"Submission with inline comments", r"\\section\{Recommendation\}"]

# The arxiv prompt mentions an attached PDF; we have none, so swap that line.
PDF_LINE = ("Now rewrite the following paper in this format. The PDF is attached "
            "as a separate file; the raw LaTeX source is below.")
NO_PDF_LINE = ("Now rewrite the following proof in this format. No PDF is attached; "
               "the raw LaTeX source below is the complete and authoritative source. "
               "This is a single self-contained theorem with its proof (a competition/"
               "research problem solution), so expect exactly one THEOREM_STATEMENT.")


def assert_clean(cid: str, tex: str):
    for pat in ANNOT_PATTERNS:
        if re.search(pat, tex):
            raise SystemExit(f"!! {cid}: clean-proof check FAILED — found {pat!r}")


def main():
    fatal = sorted(
        [r["id"] for r in ERRORS
         if any(e.get("severity") == "fatal" for e in r.get("errors", []))]
    )
    (HERE / "pf_fatal_ids.txt").write_text("\n".join(fatal) + "\n")
    base = ARXIV_COMPLEX_REWRITE_PROMPT.replace(PDF_LINE, NO_PDF_LINE)

    for cid in fatal:
        proof = BY_ID[cid]["proof_tex"]
        assert_clean(cid, proof)
        (CLEAN_DIR / f"{cid}.tex").write_text(proof, encoding="utf-8")
        prompt = base.format(paper_tex=proof)
        (PROMPT_DIR / f"{cid}.prompt.txt").write_text(prompt, encoding="utf-8")

    print(f"Prepared {len(fatal)} fatal-error proofs (all clean, no annotations):")
    print("  " + " ".join(fatal))
    print(f"  clean proofs -> {CLEAN_DIR}")
    print(f"  PF prompts   -> {PROMPT_DIR}")


if __name__ == "__main__":
    main()
