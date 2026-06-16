"""Build STRICTER PF prompts for the proofs whose first PF pass added/dropped
content (05B, 09D, 10B). Same arxiv PF prompt + a strictness addendum that forbids
adding any reasoning and forbids dropping any content (examples, remarks,
disclaimers, "what is missing" prose).

Outputs prompts to pf_prompts_strict/<id>.prompt.txt
"""

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))
from src.verifier.arxiv_complex_prompts import ARXIV_COMPLEX_REWRITE_PROMPT

IDS = ["05B", "09D", "10B"]
BY_ID = {c["id"]: c for c in json.loads((HERE / "corpus.json").read_text())}

PDF_LINE = ("Now rewrite the following paper in this format. The PDF is attached "
            "as a separate file; the raw LaTeX source is below.")
NO_PDF_LINE = ("Now rewrite the following proof in this format. No PDF is attached; "
               "the raw LaTeX source below is the complete and authoritative source. "
               "This is a single self-contained theorem with its proof, so expect "
               "exactly one THEOREM_STATEMENT.")

STRICT_ADDENDUM = """

============================== STRICTNESS REQUIREMENTS (OVERRIDING) ==============================
This rewrite is used to audit a flawed proof, so faithfulness is paramount. Obey ALL of the following; they override any temptation to clean up the argument:

1. ADD NOTHING. Do not insert any reasoning, justification, connective phrase, algebraic step, or intermediate result that is not literally present in the original. In particular, never write sentences like "Thus X is counted by Y", "equating gives ...", or "since p<1, p^2<p" unless that exact justification appears in the original. If the original merely ASSERTS a step with no justification, your corresponding *_PROOF must also merely assert it (or be exactly "None"). Do NOT paper over gaps.

2. DROP NOTHING. Every sentence of the original must be represented somewhere in the output. This includes material that is not a formal proof step:
   - worked EXAMPLES (render each as its own leaf block, e.g. a FACT or CLAIM whose statement is the example and whose proof is the example's verification, verbatim);
   - REMARKS and side comments;
   - any "what is missing", "open issues", "limitations", "final conclusion", or self-critical/disclaimer prose;
   - any statement that the proof is partial, conditional, heuristic, or proves a different/relaxed result than asked.
   Preserve such disclaimers verbatim in the most relevant block's statement or as a dedicated remark/fact block. Do NOT silently omit them.

3. DO NOT REFRAME. Keep the original's own stance. If the original asserts a (false or gappy) claim affirmatively, state it affirmatively; do not soften it to "this is not established" and do not strengthen a hedge into a claim.

4. If faithfully preserving a piece of prose conflicts with the structural rules above, prefer FAITHFULNESS: attach the prose to the nearest block rather than dropping it.
================================================================================================
"""


def main():
    out = HERE / "pf_prompts_strict"
    out.mkdir(exist_ok=True)
    base = ARXIV_COMPLEX_REWRITE_PROMPT.replace(PDF_LINE, NO_PDF_LINE)
    # Insert the addendum right before the "Now rewrite ..." instruction.
    base = base.replace(NO_PDF_LINE, STRICT_ADDENDUM + "\n" + NO_PDF_LINE)
    for cid in IDS:
        prompt = base.format(paper_tex=BY_ID[cid]["proof_tex"])
        (out / f"{cid}.prompt.txt").write_text(prompt, encoding="utf-8")
    print(f"Wrote strict prompts for {IDS} -> {out}")


if __name__ == "__main__":
    main()
