"""Render the error map (errors.json) + proofs (corpus.json) into a single
self-contained HTML report for human review.

Each submission becomes a card: editorial decision (ground truth) + AI verdict,
then for every mathematical error a highlighted block with its description, and
finally the full proof with all errored spans highlighted in context. Math is
rendered with MathJax.
"""

import html
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ERRORS = HERE / "errors.json"
CORPUS = HERE / "corpus.json"
OUT = HERE / "report.html"

SEV_COLOR = {"fatal": "#b3261e", "major": "#c77700", "minor": "#7a7a00"}
VERDICT_BADGE = {
    "flawed": ("#b3261e", "FLAWED"),
    "minor_issues_only": ("#1a7f37", "MATH SOUND (minor issues)"),
    "correct": ("#1a7f37", "CORRECT"),
    "not_reviewed": ("#777", "NOT REVIEWED"),
}
DECISION_COLOR = {
    "Reject": "#b3261e", "Major Revisions": "#c77700",
    "Minor Revisions": "#1a73e8", "Essentially Flawless": "#1a7f37", None: "#777",
}

# ---------------------------------------------------------------- latex -> html

MATH_RE = re.compile(r"(\$\$.*?\$\$|\\\[.*?\\\]|\\\(.*?\\\)|\$.*?\$)", re.DOTALL)


def find_math_regions(tex: str):
    return [(m.start(), m.end()) for m in MATH_RE.finditer(tex)]


def snap_outside_math(pos: int, regions, prefer_left: bool) -> int:
    """If pos is strictly inside a math region, move it to that region's edge."""
    for s, e in regions:
        if s < pos < e:
            return s if prefer_left else e
    return pos


import unicodedata

_ACC = {"'": "́", "`": "̀", '"': "̈", "^": "̂",
        "~": "̃", "=": "̄", ".": "̇", "v": "̌", "u": "̆"}


def _accent(m):
    sym = m.group(1)
    if sym in _ACC:
        return unicodedata.normalize("NFC", m.group(2) + _ACC[sym])
    return m.group(0)


# bare math macros that escaped into text (no surrounding $...$) — wrap for MathJax
_MATHMACRO = re.compile(
    r"\\(?:mathcal|mathbb|mathfrak|mathrm|mathsf|mathbf|sqrt|frac|sum|prod|int|"
    r"alpha|beta|gamma|delta|theta|lambda|mu|sigma|pi|phi|epsilon|infty|leq|geq|"
    r"cdot|times|le|ge|ne|approx)\b"
    r"(?:\s*\{[^{}]*\})*"          # any number of braced args, e.g. \frac{a}{b}, \sqrt{x}
    r"(?:\s*[A-Za-z](?![A-Za-z]))?")  # at most ONE isolated bare letter (e.g. \mathcal P)


def _ref_label(label: str) -> str:
    """Make a \\ref label readable: drop the kind prefix and separators.
    'lem:binomial' -> 'binomial'; 'thm-main' -> 'main'."""
    lab = label.split(":", 1)[-1] if ":" in label else label
    return lab.replace("_", " ").replace("-", " ").strip() or label


def latex_segment_to_html(seg: str) -> str:
    """Convert a LaTeX fragment (with balanced math) to HTML, protecting math so
    MathJax can render it and HTML-escaping the surrounding prose. Uses control
    chars \\x01/\\x02 as sentinels that survive html.escape unscathed."""
    parts = []
    last = 0
    for m in MATH_RE.finditer(seg):
        parts.append(("text", seg[last:m.start()]))
        parts.append(("math", m.group(0)))
        last = m.end()
    parts.append(("text", seg[last:]))

    out = []
    for kind, chunk in parts:
        if kind == "math":
            # Escape <, >, & even inside math: a literal "<" (strict inequality)
            # would otherwise be parsed as an HTML tag and swallow the rest of the
            # line. The browser decodes the entities back before MathJax reads the
            # text content, so MathJax still sees the correct LaTeX.
            out.append(chunk.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
            continue
        t = chunk
        # drop preamble-y / no-op commands entirely
        t = re.sub(r"\\(title|author|date|maketitle|documentclass|usepackage|"
                   r"newtheorem|newcommand|makeatletter|makeatother)\b[^\n]*", "", t)
        # structural markup -> control-char sentinels (survive html.escape)
        t = re.sub(r"\\begin\{proof\}", "\x01P\x02", t)
        t = re.sub(r"\\end\{proof\}", "\x01/P\x02", t)
        t = re.sub(r"\\begin\{(theorem|lemma|proposition|corollary|definition|remark|claim)\*?\}",
                   lambda m: f"\x01E:{m.group(1)}\x02", t)
        t = re.sub(r"\\end\{(theorem|lemma|proposition|corollary|definition|remark|claim)\*?\}",
                   "\x01/E\x02", t)
        t = re.sub(r"\\(begin|end)\{(center|abstract|equation\*?|align\*?)\}", "", t)
        t = re.sub(r"\\(section|subsection|paragraph)\*?\{([^{}]*)\}",
                   lambda m: f"\x01H\x02{m.group(2)}\x01/H\x02", t)
        t = re.sub(r"\\(emph|textit|textbf|textsc|textrm)\{([^{}]*)\}",
                   lambda m: f"\x01M\x02{m.group(2)}\x01/M\x02", t)
        # cross-references / citations (text-mode macros MathJax can't resolve):
        # \ref{lem:binomial} -> "binomial"; \cite{Foo1968} -> "[Foo1968]".
        t = re.sub(r"\\(?:eq|c|C|auto|page|name)?ref\*?\{([^{}]*)\}",
                   lambda m: _ref_label(m.group(1)), t)
        t = re.sub(r"\\cite[a-zA-Z]*\*?(?:\[[^\]]*\])?\{([^{}]*)\}",
                   lambda m: "[" + m.group(1) + "]", t)
        t = re.sub(r"\\url\{([^{}]*)\}", lambda m: f"\x01A\x02{m.group(1)}\x01/A\x02", t)
        # LaTeX accents: {\'o} / \'o -> ó  (handle braced then bare)
        t = re.sub(r"\{?\\([^A-Za-z0-9\s])\s*\{?([A-Za-z])\}?\}?", _accent, t)
        t = t.replace("~", " ")  # LaTeX non-breaking space
        # stray math macros left in text (author/GPT forgot $...$): wrap for MathJax
        t = _MATHMACRO.sub(lambda m: r"\(" + m.group(0) + r"\)", t)
        t = t.replace(r"\bf", "").replace("\\\\", " ")
        t = html.escape(t)
        t = re.sub(r"\n[ \t]*\n", "</p><p>", t)
        # restore sentinels
        t = t.replace("\x01P\x02", '<span class="lbl">Proof.</span> ')
        t = t.replace("\x01/P\x02", " &#9633;")
        t = re.sub("\x01E:(\\w+)\x02",
                   lambda m: f'<span class="lbl">{m.group(1).capitalize()}.</span> ', t)
        t = t.replace("\x01/E\x02", "")
        t = re.sub("\x01H\x02(.*?)\x01/H\x02", r'<strong>\1</strong> ', t, flags=re.DOTALL)
        t = re.sub("\x01M\x02(.*?)\x01/M\x02", r'<em>\1</em>', t, flags=re.DOTALL)
        t = re.sub("\x01A\x02(.*?)\x01/A\x02",
                   lambda m: f'<a href="{m.group(1)}" target="_blank">{m.group(1)}</a>', t, flags=re.DOTALL)
        out.append(t)
    return "".join(out)


def render_proof_with_marks(proof: str, errors):
    """Render the full proof, wrapping each located error span in <mark>."""
    regions = find_math_regions(proof)
    spans = []
    for e in errors:
        if e.get("match") in ("exact", "fuzzy") and e.get("start", -1) >= 0:
            s = snap_outside_math(e["start"], regions, prefer_left=True)
            t = snap_outside_math(e["end"], regions, prefer_left=False)
            spans.append((s, t, e))
    spans.sort()
    clean, last_end = [], -1
    for s, t, e in spans:
        if s >= last_end:
            clean.append((s, t, e))
            last_end = t
    parts, pos = [], 0
    for s, t, e in clean:
        parts.append(latex_segment_to_html(proof[pos:s]))
        sev = e.get("severity", "major")
        parts.append(
            f'<mark class="err err-{sev}" id="ctx-{e["_eid"]}" '
            f'title="{html.escape(e.get("title",""))}">'
            f'{latex_segment_to_html(proof[s:t])}</mark>')
        pos = t
    parts.append(latex_segment_to_html(proof[pos:]))
    return "<p>" + "".join(parts) + "</p>"


# ---------------------------------------------------------------- page

def esc(s):
    return html.escape(s or "")


def submission_card(rec, proof):
    cid = rec["id"]
    verdict = rec.get("verdict", "not_reviewed")
    vc, vlabel = VERDICT_BADGE.get(verdict, ("#777", verdict))
    dec = rec.get("editorial_decision")
    dc = DECISION_COLOR.get(dec, "#777")
    errors = rec.get("errors", [])
    for j, e in enumerate(errors):
        e["_eid"] = f"{cid}-{j}"
    secondary = rec.get("secondary_issues", [])

    h = [f'<div class="card verdict-{verdict}" id="sub-{cid}" data-verdict="{verdict}">']
    h.append('<div class="card-head">')
    h.append(f'<h3>Problem {int(rec["problem"].split("-")[1])} &middot; Submission {rec["submission"]}</h3>')
    h.append(f'<span class="badge" style="background:{dc}">Referee: {esc(dec) or "&mdash;"}</span>')
    h.append(f'<span class="badge" style="background:{vc}">AI: {vlabel}</span>')
    h.append(f'<span class="badge ghost">{rec.get("n_reviews",0)} reviews &middot; {len(errors)} errors</span>')
    h.append('</div>')

    if rec.get("verdict_rationale"):
        h.append(f'<p class="rationale">{esc(rec["verdict_rationale"])}</p>')

    if not errors:
        if rec.get("status") == "no_reviews":
            h.append('<p class="none">No referee reviews available for this submission.</p>')
        else:
            h.append('<p class="none">No mathematical errors identified &mdash; referees raised only citation/exposition issues.</p>')

    for e in errors:
        sev = e.get("severity", "major")
        col = SEV_COLOR.get(sev, "#c77700")
        h.append(f'<div class="errbox" style="border-left-color:{col}">')
        h.append('<div class="errhead">')
        h.append(f'<span class="pill" style="background:{col}">{sev.upper()}</span>')
        h.append(f'<span class="pill ghost">{esc(e.get("error_type",""))}</span>')
        h.append(f'<span class="etitle">{esc(e.get("title",""))}</span>')
        srcs = e.get("source_reviewers", [])
        if srcs:
            h.append(f'<span class="src">reviewer(s) {", ".join(map(str,srcs))}</span>')
        h.append('</div>')
        h.append(f'<div class="loc"><b>Where:</b> {esc(e.get("block_location",""))} '
                 f'<a class="jump" href="#ctx-{e["_eid"]}">show in proof &darr;</a> '
                 f'<span class="match match-{e.get("match","")}">{e.get("match","")}</span></div>')
        h.append('<div class="block-label">Errored block</div>')
        h.append(f'<div class="block">{latex_segment_to_html(e.get("errored_block",""))}</div>')
        h.append('<div class="desc-label">Error description</div>')
        h.append(f'<div class="desc">{esc(e.get("error_description",""))}</div>')
        h.append('</div>')

    if secondary:
        h.append('<details class="secondary"><summary>'
                 f'{len(secondary)} secondary issue(s) &mdash; citation / exposition</summary><ul>')
        for s in secondary:
            h.append(f'<li><span class="pill ghost">{esc(s.get("kind",""))}</span> {esc(s.get("description",""))}</li>')
        h.append('</ul></details>')

    if proof:
        h.append('<details class="proof"><summary>Full proof (errored spans highlighted)</summary>'
                 f'<div class="prooftext">{render_proof_with_marks(proof, errors)}</div></details>')

    h.append('</div>')
    return "\n".join(h)


def main():
    results = json.loads(ERRORS.read_text())
    corpus = {c["id"]: c for c in json.loads(CORPUS.read_text())}
    results.sort(key=lambda r: (r["problem"], r["submission"]))

    n_total = len(results)
    n_flawed = sum(1 for r in results if r.get("verdict") == "flawed")
    n_errors = sum(len(r.get("errors", [])) for r in results)
    n_fatal = sum(1 for r in results for e in r.get("errors", []) if e.get("severity") == "fatal")

    cards, cur_prob = [], None
    for r in results:
        if r["problem"] != cur_prob:
            cur_prob = r["problem"]
            pn = int(cur_prob.split("-")[1])
            cards.append(f'<h2 id="p{pn}" class="probhead">Problem {pn}</h2>')
        cards.append(submission_card(r, corpus.get(r["id"], {}).get("proof_tex", "")))

    nav = " ".join(
        f'<a href="#p{int(p.split("-")[1])}">P{int(p.split("-")[1])}</a>'
        for p in sorted({r["problem"] for r in results}))

    page = TEMPLATE.format(
        n_total=n_total, n_flawed=n_flawed, n_errors=n_errors, n_fatal=n_fatal,
        nav=nav, cards="\n".join(cards))
    from mathjax_inline import mathjax_head
    page = page.replace("<!--MATHJAX-->", mathjax_head())  # inline MathJax (self-contained)
    OUT.write_text(page, encoding="utf-8")
    print(f"Wrote {OUT}")
    print(f"  {n_total} submissions | {n_flawed} flawed | {n_errors} errored blocks | {n_fatal} fatal")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>First Proof Batch 2 — Error Map</title>
<!--MATHJAX-->
<style>
:root {{ --ink:#171313; --gray:#69626d; --sand:#f2ece9; }}
* {{ box-sizing:border-box; }}
body {{ font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif; color:var(--ink);
       max-width:1000px; margin:0 auto; padding:24px 18px 80px; line-height:1.5; }}
h1 {{ margin:0 0 4px; }}
.sub {{ color:var(--gray); margin:0 0 18px; }}
.stats {{ display:flex; gap:14px; flex-wrap:wrap; margin:14px 0 8px; }}
.stat {{ background:var(--sand); border-radius:10px; padding:10px 16px; }}
.stat b {{ font-size:1.6em; display:block; }}
.toolbar {{ position:sticky; top:0; background:#fff; padding:10px 0; border-bottom:1px solid #eee;
            z-index:20; display:flex; gap:14px; align-items:center; flex-wrap:wrap; }}
.toolbar .nav a {{ margin-right:6px; text-decoration:none; color:#1a73e8; font-size:.9em; }}
.probhead {{ border-bottom:2px solid var(--ink); padding-bottom:4px; margin-top:36px; }}
.card {{ border:1px solid #e3ddd9; border-radius:12px; padding:16px 18px; margin:16px 0;
         box-shadow:0 1px 3px rgba(0,0,0,.04); }}
.card.verdict-flawed {{ border-left:5px solid #b3261e; }}
.card.verdict-minor_issues_only, .card.verdict-correct {{ border-left:5px solid #1a7f37; }}
.card-head {{ display:flex; gap:10px; align-items:center; flex-wrap:wrap; }}
.card-head h3 {{ margin:0; flex:0 0 auto; }}
.badge {{ color:#fff; font-size:.72em; font-weight:700; padding:3px 9px; border-radius:20px; letter-spacing:.3px; }}
.badge.ghost {{ background:#eee !important; color:var(--gray); }}
.rationale {{ background:var(--sand); padding:10px 12px; border-radius:8px; margin:10px 0; font-size:.95em; }}
.none {{ color:var(--gray); font-style:italic; }}
.errbox {{ border-left:4px solid #c77700; background:#fffdf8; padding:10px 14px; margin:12px 0; border-radius:0 8px 8px 0; }}
.errhead {{ display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-bottom:6px; }}
.pill {{ color:#fff; font-size:.68em; font-weight:700; padding:2px 8px; border-radius:6px; text-transform:uppercase; }}
.pill.ghost {{ background:#e7e1dc !important; color:var(--gray); }}
.etitle {{ font-weight:600; }}
.src {{ color:var(--gray); font-size:.82em; margin-left:auto; }}
.loc {{ font-size:.88em; color:var(--gray); margin:4px 0; }}
.jump {{ text-decoration:none; color:#1a73e8; }}
.match {{ font-size:.75em; padding:1px 6px; border-radius:5px; background:#eee; }}
.match-exact {{ background:#d8f0d8; }} .match-fuzzy {{ background:#fdf0c8; }} .match-not_found {{ background:#f6d6d3; }}
.block-label, .desc-label {{ font-size:.7em; text-transform:uppercase; letter-spacing:.5px; color:var(--gray); margin-top:8px; }}
.block {{ background:#fff3cd; border:1px solid #f0e2a8; padding:8px 12px; border-radius:6px; margin-top:3px; overflow-x:auto; }}
.desc {{ margin-top:3px; }}
.secondary, .proof {{ margin-top:12px; }}
summary {{ cursor:pointer; color:var(--gray); font-weight:600; }}
.secondary li {{ margin:6px 0; }}
.prooftext {{ background:#fafafa; border:1px solid #eee; padding:14px 16px; border-radius:8px; margin-top:8px;
              max-height:520px; overflow:auto; font-size:.93em; }}
.prooftext .lbl {{ font-weight:700; }}
mark.err {{ padding:1px 2px; border-radius:3px; }}
mark.err-fatal {{ background:#f7c5c0; }} mark.err-major {{ background:#fbe1bd; }} mark.err-minor {{ background:#f1f1bd; }}
.hide {{ display:none; }}
label.filter {{ font-size:.9em; color:var(--ink); cursor:pointer; }}
</style></head>
<body>
<h1>First Proof &middot; Second Batch &mdash; Error Map</h1>
<p class="sub">AI-generated proofs mapped to their errored blocks, grounded in the referee reports. Each block of a wrong proof is paired with a paragraph describing the error.</p>
<div class="stats">
  <div class="stat"><b>{n_total}</b>submissions</div>
  <div class="stat"><b>{n_flawed}</b>flawed (math defect)</div>
  <div class="stat"><b>{n_errors}</b>errored blocks</div>
  <div class="stat"><b>{n_fatal}</b>fatal</div>
</div>
<div class="toolbar">
  <span class="nav">{nav}</span>
  <label class="filter"><input type="checkbox" id="onlyflawed"> show only flawed proofs</label>
</div>
{cards}
<script>
document.getElementById('onlyflawed').addEventListener('change', function(e){{
  document.querySelectorAll('.card').forEach(function(c){{
    c.classList.toggle('hide', e.target.checked && c.dataset.verdict !== 'flawed');
  }});
  document.querySelectorAll('.probhead').forEach(function(h){{
    var n=h.nextElementSibling, any=false;
    while(n && !n.classList.contains('probhead')){{ if(n.classList.contains('card') && !n.classList.contains('hide')) any=true; n=n.nextElementSibling; }}
    h.classList.toggle('hide', e.target.checked && !any);
  }});
}});
</script>
</body></html>"""


if __name__ == "__main__":
    main()
