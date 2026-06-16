"""Render pf_review_map.json into an HTML report pairing, per error:
the error description, what the AUTHOR ORIGINALLY SAID (verbatim original block),
and the GPT EXPANSION (the corresponding PF block statement+proof). MathJax for math.
"""

import html
import json
import re
from pathlib import Path

from make_report import latex_segment_to_html  # reuse the LaTeX->HTML renderer
from mathjax_inline import mathjax_head

HERE = Path(__file__).resolve().parent
_checked = HERE / "pf_review_map_checked.json"
ROWS = json.loads((_checked if _checked.exists() else HERE / "pf_review_map.json").read_text())
OUT = HERE / "pf_review_map.html"

SEV = {"fatal": "#b3261e", "major": "#c77700", "minor": "#7a7a00"}
CONF = {"high": "#1a7f37", "medium": "#c77700", "low": "#b3261e"}
XC = {"yes": "#1a7f37", "partial": "#c77700", "no": "#b3261e", None: "#777"}


PF_DIR = HERE / "pf_outputs"
_pf_cache = {}
TAG_BY_DEPTH = {1: "PROPOSITION", 2: "LEMMA", 3: "CLAIM", 4: "FACT"}


def esc(s):
    return html.escape(s or "")


def load_pf(sid):
    if sid not in _pf_cache:
        _pf_cache[sid] = (PF_DIR / f"{sid}.pf.txt").read_text()
    return _pf_cache[sid]


def _find(pf, tag, kind, bid):
    m = re.search(rf'<{tag}_{kind} id="{re.escape(bid)}">(.*?)</{tag}_{kind}>', pf, re.DOTALL)
    return m.group(1).strip() if m else None


def _deps(pf, tag, bid):
    did = f"theorem_{bid}" if tag == "THEOREM" else bid
    m = re.search(rf'<DEPS id="{re.escape(did)}">(.*?)</DEPS>', pf, re.DOTALL)
    return m.group(1).strip() if m else None


def _theorem_ids(pf):
    return re.findall(r'<THEOREM_STATEMENT id="([^"]+)"', pf)


def _ancestors(tag, bid):
    """Non-theorem ancestor (tag,id) pairs from outermost to the block's parent."""
    if tag == "THEOREM":
        return []
    parts = bid.split(".")
    return [(TAG_BY_DEPTH[k], ".".join(parts[:k])) for k in range(1, len(parts))]


def render_expansion_with_context(row) -> str:
    """Render the mapped PF block(s) with full context: every ancestor statement
    (Theorem -> Proposition -> Lemma -> ...) carrying its assumptions, then each
    mapped block's statement + proof + dependencies. Ancestors are dimmed."""
    pf = load_pf(row["id"])
    named = {(b["tag"], b["id"]) for b in row["pf_blocks"]}
    allset = set(named)
    for b in row["pf_blocks"]:
        allset.update(_ancestors(b["tag"], b["id"]))

    def keyf(x):
        return (len(x[1].split(".")), [int(p) for p in x[1].split(".")])

    # theorem roots first (always shown as top-level context), then by depth/id
    ordered = [("THEOREM", t) for t in _theorem_ids(pf)]
    ordered += sorted([x for x in allset if x[0] != "THEOREM"], key=keyf)

    out = []
    for tag, bid in ordered:
        is_mapped = (tag, bid) in named
        stmt = _find(pf, tag, "STATEMENT", bid)
        if stmt is None:
            continue
        proof = _find(pf, tag, "PROOF", bid)
        deps = _deps(pf, tag, bid)
        cls = "blk mapped" if is_mapped else "blk ctx"
        tagbadge = "mapped" if is_mapped else "context"
        out.append(f'<div class="{cls}">')
        out.append(f'<div class="blkhead">{esc(tag.title())} {esc(bid)}'
                   f'<span class="blktag">{tagbadge}</span></div>')
        out.append(f'<div class="blkstmt">{latex_segment_to_html(stmt)}</div>')
        if is_mapped and proof and proof.strip().lower() != "none":
            out.append('<div class="blkproof"><span class="pl">Proof.</span> '
                       f'{latex_segment_to_html(proof)}</div>')
        if is_mapped and deps:
            out.append(f'<div class="blkdeps">depends on: {esc(deps)}</div>')
        out.append('</div>')
    return "".join(out)


def pf_to_html(txt: str) -> str:
    """Render a PF expansion: keep the [TAG id - kind] labels, render the rest."""
    parts = []
    for line in txt.split("\n"):
        m = re.match(r"\[([A-Z]+ [\d.]+) — (\w+)\]$", line.strip())
        if m:
            parts.append(f'<div class="pflabel">{esc(m.group(1))} · {esc(m.group(2))}</div>')
        else:
            parts.append(line)
    # render the non-label lines as latex
    # (labels were emitted as html divs; rejoin and let latex renderer handle the rest)
    joined = "\n".join(parts)
    # protect our divs from the latex escaper by splitting on them
    chunks = re.split(r'(<div class="pflabel">.*?</div>)', joined)
    out = []
    for c in chunks:
        if c.startswith('<div class="pflabel">'):
            out.append(c)
        else:
            out.append(latex_segment_to_html(c))
    return "".join(out)


def main():
    by_sub = {}
    for r in ROWS:
        by_sub.setdefault(r["id"], []).append(r)

    cards = []
    for sid in sorted(by_sub):
        pn = int(sid[:2]); sub = sid[2:]
        cards.append(f'<h2 id="s{sid}" class="subhead">Problem {pn} · Submission {sub} '
                     f'<span class="cnt">{len(by_sub[sid])} error(s)</span></h2>')
        for r in by_sub[sid]:
            sc = SEV.get(r["severity"], "#777")
            cc = CONF.get(r["match_confidence"], "#777")
            cards.append('<div class="emap">')
            cards.append('<div class="ehead">'
                         f'<span class="pill" style="background:{sc}">{esc(r["severity"])}</span>'
                         f'<span class="pill ghost">{esc(r["error_type"])}</span>'
                         f'<span class="etitle">{esc(r["title"])}</span>'
                         f'<span class="conf" style="color:{cc}">map: {esc(r["match_confidence"])}</span>'
                         '</div>')
            cards.append(f'<div class="desc">{esc(r["error_description"])}</div>')
            cards.append('<div class="cols">')
            # author original
            cards.append('<div class="col"><div class="collabel orig">What the author originally said</div>'
                         f'<div class="orig-body">{latex_segment_to_html(r["author_original"])}</div></div>')
            # gpt expansion (mapped blocks + full ancestor context with assumptions)
            blocks = ", ".join(f'{b["tag"]} {b["id"]}' for b in r["pf_blocks"])
            body = render_expansion_with_context(r) or "<em>(blocks not located)</em>"
            cards.append('<div class="col"><div class="collabel gpt">GPT expansion (PF)</div>'
                         '<div class="gpt-body">'
                         f'<div class="blockids-line">Mapped block(s): {esc(blocks)} '
                         '<span class="ctxnote">— parent blocks shown dimmed for context</span></div>'
                         f'{body}</div></div>')
            cards.append('</div>')  # cols
            cards.append(f'<div class="note"><b>Mapping:</b> {esc(r["mapping_note"])}</div>')
            xc = r.get("codex_xcheck")
            if xc:
                mcol = XC.get(xc.get("mapping_correct"), "#777")
                ecol = XC.get(xc.get("error_present_in_pf"), "#777")
                cards.append(
                    '<div class="xcheck"><span class="xtag">Codex cross-check</span> '
                    f'<span class="pill" style="background:{mcol}">map {esc(xc.get("mapping_correct"))}</span> '
                    f'<span class="pill" style="background:{ecol}">flaw present {esc(xc.get("error_present_in_pf"))}</span> '
                    f'<span class="conf">conf {esc(xc.get("confidence"))}</span>'
                    + (f' <span class="sugg">→ {esc(xc.get("suggested_blocks"))}</span>' if xc.get("suggested_blocks") else "")
                    + f'<div class="xassess">{esc(xc.get("assessment"))}</div></div>')
            cards.append('</div>')  # emap

    nav = " ".join(f'<a href="#s{s}">{s}</a>' for s in sorted(by_sub))
    n_err = len(ROWS)
    n_fatal = sum(1 for r in ROWS if r["severity"] == "fatal")
    page = TEMPLATE.format(nav=nav, cards="\n".join(cards),
                           n_err=n_err, n_sub=len(by_sub), n_fatal=n_fatal)
    page = page.replace("<!--MATHJAX-->", mathjax_head())  # inline MathJax (self-contained)
    OUT.write_text(page, encoding="utf-8")
    print(f"Wrote {OUT} ({n_err} errors across {len(by_sub)} proofs)")


TEMPLATE = r"""<!DOCTYPE html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Review → PF block map</title>
<!--MATHJAX-->
<style>
:root{{--ink:#171313;--gray:#69626d;--sand:#f2ece9;}}
*{{box-sizing:border-box;}}
body{{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:var(--ink);
max-width:1180px;margin:0 auto;padding:24px 18px 80px;line-height:1.5;}}
h1{{margin:0 0 4px;}} .sub{{color:var(--gray);margin:0 0 16px;}}
.stats{{display:flex;gap:14px;margin:10px 0;}}
.stat{{background:var(--sand);border-radius:10px;padding:8px 14px;}} .stat b{{font-size:1.4em;display:block;}}
.toolbar{{position:sticky;top:0;background:#fff;padding:8px 0;border-bottom:1px solid #eee;z-index:50;
  white-space:nowrap;overflow-x:auto;box-shadow:0 2px 4px rgba(0,0,0,.05);}}
.toolbar a{{margin-right:8px;text-decoration:none;color:#1a73e8;font-size:.85em;}}
.subhead,.emap{{scroll-margin-top:46px;}}
.subhead{{border-bottom:2px solid var(--ink);padding-bottom:4px;margin-top:34px;}}
.subhead .cnt{{font-size:.6em;color:var(--gray);font-weight:400;}}
.emap{{border:1px solid #e3ddd9;border-radius:12px;padding:14px 16px;margin:14px 0;box-shadow:0 1px 3px rgba(0,0,0,.04);}}
.ehead{{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:6px;}}
.pill{{color:#fff;font-size:.68em;font-weight:700;padding:2px 8px;border-radius:6px;text-transform:uppercase;}}
.pill.ghost{{background:#e7e1dc!important;color:var(--gray);}}
.etitle{{font-weight:600;}} .conf{{margin-left:auto;font-size:.8em;font-weight:700;}}
.desc{{background:var(--sand);padding:9px 12px;border-radius:8px;margin:6px 0 12px;font-size:.95em;}}
.cols{{display:grid;grid-template-columns:1fr 1fr;gap:14px;}}
@media(max-width:820px){{.cols{{grid-template-columns:1fr;}}}}
.col{{border:1px solid #eee;border-radius:8px;overflow:hidden;}}
.collabel{{display:flex;align-items:center;min-height:34px;font-size:.72em;text-transform:uppercase;letter-spacing:.5px;font-weight:700;padding:6px 10px;color:#fff;}}
.collabel.orig{{background:#69626d;}} .collabel.gpt{{background:#1a73e8;}}
.blockids-line{{font-size:.82em;color:#1a4fa0;background:#eaf2ff;border:1px solid #cdddf5;border-radius:6px;padding:5px 8px;margin-bottom:8px;}}
.blockids-line .ctxnote{{color:#69626d;font-style:italic;}}
.orig-body,.gpt-body{{padding:10px 12px;font-size:.92em;max-height:460px;overflow:auto;}}
.orig-body{{background:#faf8f7;}} .gpt-body{{background:#f6f9ff;}}
.pflabel{{font-size:.7em;font-weight:700;color:#1a73e8;text-transform:uppercase;letter-spacing:.4px;margin:8px 0 2px;border-top:1px dashed #cdddf5;padding-top:6px;}}
.pflabel:first-child{{border-top:0;}}
.blk{{border:1px solid #dce6f7;border-radius:7px;padding:8px 10px;margin:8px 0;}}
.blk.ctx{{background:#f4f6fa;border-style:dashed;opacity:.92;}}
.blk.mapped{{background:#eaf2ff;border-color:#1a73e8;border-width:1.5px;}}
.blkhead{{font-size:.72em;font-weight:700;text-transform:uppercase;letter-spacing:.4px;color:#1a4fa0;margin-bottom:4px;}}
.blktag{{float:right;font-size:.92em;padding:0 6px;border-radius:5px;}}
.blk.mapped .blktag{{background:#1a73e8;color:#fff;}} .blk.ctx .blktag{{background:#d7ddE6;color:#69626d;}}
.blkstmt{{font-size:.95em;}}
.blkproof{{margin-top:5px;font-size:.95em;border-top:1px dotted #c3d3ee;padding-top:5px;}}
.blkproof .pl{{font-weight:700;}}
.blkdeps{{margin-top:5px;font-size:.78em;color:#69626d;}}
.note{{margin-top:10px;font-size:.9em;color:var(--ink);background:#fffdf6;border-left:3px solid #c77700;padding:7px 11px;border-radius:0 6px 6px 0;}}
.xcheck{{margin-top:8px;font-size:.88em;background:#f3f0f7;border-left:3px solid #69626d;padding:7px 11px;border-radius:0 6px 6px 0;}}
.xtag{{font-weight:700;text-transform:uppercase;font-size:.82em;letter-spacing:.4px;color:#69626d;margin-right:6px;}}
.xcheck .conf{{font-size:.85em;color:var(--gray);}} .xcheck .sugg{{font-size:.85em;color:#b3261e;}}
.xassess{{margin-top:5px;color:var(--ink);}}
</style></head><body>
<h1>Review error → PF block map</h1>
<p class="sub">Each error of the pseudo-formalised proofs, pairing what the author originally wrote with its GPT/PF expansion (the corresponding PF blocks).</p>
<div class="stats">
<div class="stat"><b>{n_err}</b>errors mapped</div>
<div class="stat"><b>{n_sub}</b>proofs</div>
<div class="stat"><b>{n_fatal}</b>fatal</div>
</div>
<div class="toolbar">{nav}</div>
{cards}
</body></html>"""


if __name__ == "__main__":
    main()
