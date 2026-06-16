"""Parse the 1stproof batch-2 AI solutions + referee reviews into a clean,
structured JSON corpus.

For every (problem, submission) pair we collect:
  - the AI proof itself (LaTeX body of batch-2-AI-solutions/problem-NN/submission-X.tex)
  - the referee reviews, each split into:
      * review_summary   -- the \\section{Review} prose (Correctness / Novelty / ...)
      * recommendation   -- the \\section{Recommendation} prose
      * inline_annotated -- the "Submission with inline comments" section with each
                            \\review{...} box turned into a readable
                            [[REVIEWER N COMMENT: ...]] marker, anchored in place
      * inline_comments  -- the list of individual \\review{...} bodies (brace-matched)

The editorial decision per submission (from the published report) is attached so
downstream steps can cross-check the AI mapping against ground truth.

Output: corpus.json
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "batch-2"
SOL_DIR = ROOT / "batch-2-AI-solutions"
REV_DIR = ROOT / "batch-2-reviews"
OUT = Path(__file__).resolve().parent / "corpus.json"

# Editorial decisions transcribed from the published report (Section 5), in
# problem order, submissions A,B,C,D. Problem 6 Submission A is blank (no review).
EDITORIAL = {
    "01": {"A": "Minor Revisions", "B": "Minor Revisions", "C": "Minor Revisions", "D": "Reject"},
    "02": {"A": "Minor Revisions", "B": "Minor Revisions", "C": "Minor Revisions", "D": "Reject"},
    "03": {"A": "Minor Revisions", "B": "Reject", "C": "Reject", "D": "Reject"},
    "04": {"A": "Reject", "B": "Reject", "C": "Reject", "D": "Reject"},
    "05": {"A": "Essentially Flawless", "B": "Reject", "C": "Reject", "D": "Reject"},
    "06": {"A": None, "B": "Essentially Flawless", "C": "Essentially Flawless", "D": "Reject"},
    "07": {"A": "Essentially Flawless", "B": "Minor Revisions", "C": "Essentially Flawless", "D": "Minor Revisions"},
    "08": {"A": "Reject", "B": "Major Revisions", "C": "Reject", "D": "Reject"},
    "09": {"A": "Minor Revisions", "B": "Minor Revisions", "C": "Minor Revisions", "D": "Reject"},
    "10": {"A": "Major Revisions", "B": "Reject", "C": "Major Revisions", "D": "Reject"},
}


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def document_body(tex: str) -> str:
    """Return the text between \\begin{document} and \\end{document}."""
    m = re.search(r"\\begin\{document\}(.*)\\end\{document\}", tex, re.DOTALL)
    return (m.group(1) if m else tex).strip()


def find_brace_group(s: str, open_idx: int):
    """Given index of an opening '{', return (content, index_after_close)."""
    assert s[open_idx] == "{"
    depth = 0
    i = open_idx
    while i < len(s):
        c = s[i]
        if c == "\\":  # skip escaped char
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[open_idx + 1 : i], i + 1
        i += 1
    return s[open_idx + 1 :], len(s)


def extract_reviews_macro(body: str):
    """Find each \\review{...}, returning (list_of_comment_bodies, annotated_text)
    where annotated_text replaces the macro with a [[REVIEWER COMMENT: ...]] marker
    left in place so the anchor position is preserved."""
    comments = []
    out = []
    i = 0
    tag = "\\review"
    while True:
        j = body.find(tag, i)
        if j == -1:
            out.append(body[i:])
            break
        out.append(body[i:j])
        k = j + len(tag)
        # skip optional whitespace then '{'
        while k < len(body) and body[k] in " \t\n":
            k += 1
        if k < len(body) and body[k] == "{":
            content, after = find_brace_group(body, k)
            comments.append(content.strip())
            out.append(f"\n[[REVIEWER COMMENT: {content.strip()}]]\n")
            i = after
        else:
            out.append(body[j:k])
            i = k
    return comments, "".join(out)


def clean_text(s: str) -> str:
    """Light cleanup for human-readable summary fields (keeps inline math)."""
    s = re.sub(r"%.*", "", s)            # strip latex line comments
    s = re.sub(r"\\paragraph\{([^}]*)\}", r"\n\n## \1\n", s)
    s = re.sub(r"\\section\*?\{([^}]*)\}", r"\n\n# \1\n", s)
    s = re.sub(r"\\emph\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\textbf\{([^}]*)\}", r"\1", s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def split_review(body: str):
    """Split a referee .tex document body into (summary, recommendation, inline)."""
    # Section anchors
    rec = re.search(r"\\section\*?\{Recommendation\}", body)
    inl = re.search(r"\\section\*?\{Submission with inline comments\}", body)
    rev = re.search(r"\\section\*?\{Review\}", body)

    summary = recommendation = inline = ""
    if rev:
        end = rec.start() if rec else (inl.start() if inl else len(body))
        summary = body[rev.end():end]
    if rec:
        end = inl.start() if inl else len(body)
        recommendation = body[rec.end():end]
    if inl:
        inline = body[inl.end():]
    return summary, recommendation, inline


def parse_review_file(p: Path) -> dict:
    body = document_body(read(p))
    summary_raw, rec_raw, inline_raw = split_review(body)
    comments, inline_annotated = extract_reviews_macro(inline_raw)
    m = re.search(r"reviewer-(\d+)", p.name)
    return {
        "file": p.name,
        "reviewer": int(m.group(1)) if m else None,
        "review_summary": clean_text(summary_raw),
        "recommendation": clean_text(rec_raw),
        "inline_comments": [clean_text(c) for c in comments],
        "n_inline_comments": len(comments),
        # Keep the annotated submission as LaTeX (math preserved) for the AI step.
        "inline_annotated_tex": inline_annotated.strip(),
    }


def main():
    corpus = []
    problems = sorted(d.name for d in SOL_DIR.iterdir() if d.is_dir() and d.name.startswith("problem-"))
    for prob in problems:
        pnum = prob.split("-")[1]
        for sub in ["A", "B", "C", "D"]:
            sol_path = SOL_DIR / prob / f"submission-{sub}.tex"
            if not sol_path.exists():
                continue
            proof_body = document_body(read(sol_path))
            rev_sub_dir = REV_DIR / prob / f"submission-{sub}"
            reviews = []
            if rev_sub_dir.is_dir():
                for rp in sorted(rev_sub_dir.glob("submission-*-reviewer-*.tex")):
                    reviews.append(parse_review_file(rp))
            corpus.append({
                "problem": prob,
                "submission": sub,
                "id": f"{pnum}{sub}",
                "editorial_decision": EDITORIAL.get(pnum, {}).get(sub),
                "proof_tex": proof_body,
                "n_reviews": len(reviews),
                "reviews": reviews,
            })
    OUT.write_text(json.dumps(corpus, indent=2, ensure_ascii=False), encoding="utf-8")

    # Summary
    total_rev = sum(c["n_reviews"] for c in corpus)
    total_inline = sum(r["n_inline_comments"] for c in corpus for r in c["reviews"])
    print(f"Wrote {OUT}")
    print(f"  {len(corpus)} submissions, {total_rev} reviews, {total_inline} inline comments")
    no_rev = [c["id"] for c in corpus if c["n_reviews"] == 0]
    print(f"  submissions with no reviews: {no_rev}")


if __name__ == "__main__":
    main()
