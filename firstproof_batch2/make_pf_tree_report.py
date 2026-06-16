"""Render each PF'd proof as an interactive collapsible PROOF TREE:
Theorem -> Propositions -> Lemmas -> Claims -> Facts, each node expandable and
showing its Assumptions/Conditions/Definitions, Statement, Proof and DEPS. Review
errors (from pf_review_map_checked.json) are attached inline to the blocks they map
to, as a salmon "review / error" box (the analog of a block-verifier response).

Output: pf_tree.html
"""

import html
import json
import re
from pathlib import Path

from make_report import latex_segment_to_html
from mathjax_inline import mathjax_head

HERE = Path(__file__).resolve().parent
PF_DIR = HERE / "pf_outputs"
MAP = HERE / "pf_review_map_checked.json"
if not MAP.exists():
    MAP = HERE / "pf_review_map.json"
ROWS = json.loads(MAP.read_text())
FATAL_IDS = (HERE / "pf_fatal_ids.txt").read_text().split()
OUT = HERE / "pf_tree.html"

# Blind block-verifier results + judge verdicts (optional).
_bv = HERE / "block_verify_results.json"
_jg = HERE / "verdict_judgements.json"
BV = json.loads(_bv.read_text()) if _bv.exists() else []
JUDGE = json.loads(_jg.read_text()) if _jg.exists() else []
_jmap = {(j["sid"], j["label"]): j for j in JUDGE}
# keyed by (sid, tag, id); attach the matching judge verdict
BV_BY_KEY = {}
for b in BV:
    b = {**b, "judge": _jmap.get((b["sid"], b["label"]))}
    BV_BY_KEY[(b["sid"], b["tag"], b["id"])] = b

AGREE_COLOR = {"agree": "#1a7f37", "partial": "#c77700", "disagree": "#b3261e", None: "#777"}

SEV = {"fatal": "#b3261e", "major": "#c77700", "minor": "#7a7a00"}
TAGS = ["THEOREM", "PROPOSITION", "LEMMA", "CLAIM", "FACT"]
SHORT = {"THEOREM": "Thm", "PROPOSITION": "Prop", "LEMMA": "Lem", "CLAIM": "Claim", "FACT": "Fact"}

BLOCK_RE = re.compile(
    r'<(THEOREM|PROPOSITION|LEMMA|CLAIM|FACT)_(STATEMENT|PROOF) id="([^"]+)">(.*?)</\1_\2>',
    re.DOTALL)
DEPS_RE = re.compile(r'<DEPS id="([^"]+)">(.*?)</DEPS>', re.DOTALL)


def esc(s):
    return html.escape(s or "")


def render_items(text):
    """If a block is a dash-bulleted list (e.g. the assumptions), render it as a
    numbered <ol>; otherwise render as normal LaTeX prose."""
    t = (text or "").strip()
    if t.startswith("-") or t.startswith("•"):
        items = re.split(r"(?m)^\s*[-•]\s+", t)
        items = [it.strip() for it in items if it.strip()]
        if len(items) >= 2:
            lis = "".join(f"<li>{latex_segment_to_html(it)}</li>" for it in items)
            return f'<ol class="asm">{lis}</ol>'
    return latex_segment_to_html(text)


def parse_pf(pf):
    blocks = {}  # (tag,id) -> {tag,id,statement,proof}
    order = []
    for m in BLOCK_RE.finditer(pf):
        tag, kind, bid, txt = m.group(1), m.group(2), m.group(3), m.group(4).strip()
        key = (tag, bid)
        if key not in blocks:
            blocks[key] = {"tag": tag, "id": bid, "statement": None, "proof": None}
            order.append(key)
        blocks[key][kind.lower()] = txt
    deps = {}
    for m in DEPS_RE.finditer(pf):
        deps[m.group(1)] = m.group(2).strip()
    for key, b in blocks.items():
        did = f"theorem_{b['id']}" if b["tag"] == "THEOREM" else b["id"]
        b["deps"] = deps.get(did, "")
    return blocks, order


def split_statement(s):
    if not s:
        return "", ""
    m = re.search(r"Statement\s*:?", s)
    if not m:
        return "", s.strip()
    assumptions = s[:m.start()].strip()
    assumptions = re.sub(r"^Assumptions\s*/\s*Conditions\s*/\s*Definitions\.?\s*", "",
                         assumptions, flags=re.IGNORECASE).strip()
    body = s[m.end():].strip()
    return assumptions, body


def _balance_math(t):
    """Drop trailing unmatched math delimiters so MathJax never sees a dangling
    $, \\( or \\[ in a (possibly truncated) title."""
    if t.count("$") % 2:
        t = t[:t.rfind("$")]
    while t.count(r"\(") > t.count(r"\)"):
        t = t[:t.rfind(r"\(")]
    while t.count(r"\[") > t.count(r"\]"):
        t = t[:t.rfind(r"\[")]
    return t.strip().strip("-").strip()


def title_of(body, fallback):
    if not body:
        return fallback
    # Convert display math to INLINE (don't strip it — it is often the grammatical
    # subject, e.g. "\[\sqrt3\] is the infimum ...") so the title stays a single
    # readable line that MathJax can render.
    s = re.sub(r"\\\[(.*?)\\\]",
               lambda m: r"\(" + re.sub(r"\s+", " ", m.group(1).strip()) + r"\)",
               body, flags=re.DOTALL)
    s = re.sub(r"\$\$(.*?)\$\$",
               lambda m: "$" + re.sub(r"\s+", " ", m.group(1).strip()) + "$",
               s, flags=re.DOTALL)
    s = re.sub(r"\s+", " ", s).strip(" -")
    # First sentence end: a period (optionally immediately closing a \) or $ math
    # group) followed by whitespace and a new clause. Consume the closing
    # delimiter so the title stays balanced (e.g. "...\{1/2,1\}.\)").
    msent = re.search(r"\.(\\\)|\$)?\s+(?=[A-Z\\(]|\$)", s)
    if msent and msent.start() < 220:
        end = msent.end(1) if msent.group(1) else msent.start() + 1
        t = s[:end]
    else:
        t = s
    if len(t) > 220:
        t = t[:220].rstrip() + "…"
    return _balance_math(t) or fallback


def build_children(blocks):
    """parent key -> ordered list of child keys."""
    children = {}
    theorem_keys = [k for k in blocks if k[0] == "THEOREM"]
    root_theorem = theorem_keys[0] if theorem_keys else None
    def keyf(k):
        return [int(p) for p in k[1].split(".")]
    nonth = sorted([k for k in blocks if k[0] != "THEOREM"], key=lambda k: (len(k[1].split(".")), keyf(k)))
    for k in nonth:
        parts = k[1].split(".")
        if len(parts) == 1:               # proposition -> theorem
            parent = root_theorem
        else:
            pid = ".".join(parts[:-1])
            ptag = {2: "PROPOSITION", 3: "LEMMA", 4: "CLAIM"}[len(parts)]
            parent = (ptag, pid)
        children.setdefault(parent, []).append(k)
    return children, theorem_keys


def open_set(errs_by_key):
    """Keys to expand by default: every errored block and all its ancestors."""
    s = set()
    for (tag, bid) in errs_by_key:
        s.add((tag, bid))
        parts = bid.split(".")
        for i in range(1, len(parts)):
            pid = ".".join(parts[:i])
            ptag = {1: "PROPOSITION", 2: "LEMMA", 3: "CLAIM"}[i]
            s.add((ptag, pid))
    return s


def render_verifier_reasoning(raw):
    """Turn the verifier's tagged output (<verdict>/<error_description>/<gap_filling>/
    <cited_result_audits>) into clean labeled HTML instead of raw XML."""
    def tag(name, text):
        m = re.search(rf"<{name}>(.*?)</{name}>", text, re.DOTALL)
        return m.group(1).strip() if m else ""
    samples = re.split(r"=+\s*\(next sample\)\s*=+", raw)
    out = []
    for i, ch in enumerate(samples):
        if len(samples) > 1:
            out.append(f'<div class="vrsample">sample {i+1}</div>')
        ed, gf = tag("error_description", ch), tag("gap_filling", ch)
        if ed:
            out.append('<div class="vrlabel">what it flagged</div>'
                       f'<div class="vrtxt">{latex_segment_to_html(ed)}</div>')
        if gf:
            out.append('<div class="vrlabel">gaps it filled / repaired to accept</div>'
                       f'<div class="vrtxt">{latex_segment_to_html(gf)}</div>')
        audits = re.findall(r"<audit>(.*?)</audit>", ch, re.DOTALL)
        items = []
        for a in audits:
            cited = tag("cited_as", a)
            hyps = re.findall(r"<satisfied>\s*(true|false)\s*</satisfied>", a, re.I)
            mark = "".join("✓" if h.lower() == "true" else "✗" for h in hyps) or "—"
            if cited:
                items.append(f'<li>{latex_segment_to_html(cited)} <span class="audmark">{mark}</span></li>')
        if items:
            out.append('<div class="vrlabel">cited-result audits</div><ul class="vraud">'
                       + "".join(items) + "</ul>")
        if not (ed or gf or audits):
            out.append('<div class="vrtxt">(no structured detail)</div>')
    return "".join(out)


def render_bv_box(bv):
    """Block-verifier verdict box (blind, N=3) + judge agreement vs golden."""
    caught = bv["verdict"] == "INCORRECT"
    runs = bv.get("run_verdicts", [])
    runtxt = (" · runs: " + " ".join("✗" if v == "INCORRECT" else "✓" for v in runs)) if runs else ""
    head_col = "#1a7f37" if caught else "#b3261e"
    head_lbl = "flagged INCORRECT — caught" if caught else "said CORRECT — missed"
    j = bv.get("judge") or {}
    ag = j.get("agreement")
    h = [f'<div class="bvbox" style="border-left-color:{head_col}">']
    h.append(f'<div class="bvhead"><span class="bvtag" style="background:{head_col}">'
             f'Block verifier (blind, N={bv.get("n", 1)})</span> {head_lbl}'
             f'<span class="bvruns">{runtxt}</span></div>')
    if ag:
        h.append(f'<div class="bvjudge">vs golden reviewer: '
                 f'<span class="agpill" style="background:{AGREE_COLOR.get(ag)}">{esc(ag)}</span> '
                 + ("(same error)" if j.get("verifier_found_same_error") else "(different/none)")
                 + (f'<div class="bvexpl">{esc(j.get("explanation",""))}</div>' if j.get("explanation") else "")
                 + '</div>')
    vr = (bv.get("llm_output") or "").strip()
    if vr:
        h.append('<details class="bvreason"><summary>verifier reasoning</summary>'
                 f'<div class="bvreasontxt">{render_verifier_reasoning(vr)}</div></details>')
    h.append('</div>')
    return "".join(h)


def render_node(key, blocks, children, errs_by_key, opened, depth, sid, bv_by_key):
    b = blocks[key]
    tag, bid = key
    assumptions, body = split_statement(b.get("statement"))
    errs = errs_by_key.get(key, [])  # list of (row, is_primary)
    is_err = bool(errs)
    is_open = key in opened or tag == "THEOREM"

    title = title_of(body, f"{SHORT[tag]} {bid}")
    # right-side badge: severity if errored, else a faint "block" marker
    if is_err:
        sev = max(errs, key=lambda t: ["minor", "major", "fatal"].index(t[0]["severity"]))[0]["severity"]
        badge = f'<span class="score err" style="background:{SEV[sev]}">{esc(sev)}</span>'
    else:
        badge = '<span class="score ok">no error flagged</span>'

    cls = "node" + (" errnode" if is_err else "")
    op = " open" if is_open else ""
    h = [f'<details class="{cls}"{op}>']
    label = "Thm:" if tag == "THEOREM" else f"{SHORT[tag]}. {bid}:"
    h.append(f'<summary><span class="lab">{esc(label)}</span> '
             f'<span class="ttl">{latex_segment_to_html(title)}</span>{badge}</summary>')
    h.append('<div class="body">')
    if assumptions:
        h.append('<div class="assum"><span class="mini">Assumptions / Conditions / Definitions</span>'
                 f'{render_items(assumptions)}</div>')
    if body:
        h.append('<div class="stmt"><span class="mini">Statement</span>'
                 f'{render_items(body)}</div>')
    proof = b.get("proof")
    if proof and proof.strip().lower() != "none":
        h.append('<div class="prf"><span class="mini">Proof</span>'
                 f'{render_items(proof)}</div>')
    if b.get("deps"):
        h.append(f'<div class="deps">depends on: {esc(b["deps"])}</div>')
    # mapped review errors -> salmon boxes (full box on the deepest mapped block,
    # a compact pointer on the shallower mapped blocks)
    for e, is_primary in errs:
        if is_primary:
            quotes = e.get("reviewer_quotes", [])
            if quotes:
                by_rev = {}
                for q in quotes:
                    by_rev.setdefault(q["reviewer"], []).append(q)
                qhtml = "".join(
                    f'<div class="rquote{"" if all(q.get("verbatim", True) for q in qs) else " nv"}">'
                    f'<span class="rwho">Reviewer {rev}</span>'
                    + " ".join(latex_segment_to_html(q["quote"]) for q in qs)
                    + '</div>'
                    for rev, qs in by_rev.items())
            else:
                qhtml = '<em>(no specific reviewer quote extracted)</em>'
            h.append('<div class="vresp">'
                     f'<div class="vhead"><span class="pill" style="background:{SEV[e["severity"]]}">{esc(e["severity"])}</span> '
                     f'<span class="pill ghost">{esc(e["error_type"])}</span> {esc(e["title"])}</div>'
                     '<div class="rquotes"><span class="mini">What the reviewer originally wrote</span>'
                     f'{qhtml}</div>'
                     '<details class="orig"><summary>error summary</summary>'
                     f'<div class="origtxt">{esc(e["error_description"])}</div></details>')
            if e.get("mapping_note"):
                h.append(f'<div class="vnote">map note: {esc(e["mapping_note"])}</div>')
            h.append('</div>')
        else:
            deepest = max((pb for pb in e["pf_blocks"]),
                          key=lambda pb: len(pb["id"].split(".")) if pb["tag"] != "THEOREM" else 0)
            h.append(f'<div class="vptr"><span class="pill" style="background:{SEV[e["severity"]]}">{esc(e["severity"])}</span> '
                     f'part of error “{esc(e["title"])}” — full detail on {esc(SHORT[deepest["tag"]])} {esc(deepest["id"])} below</div>')
    # block-verifier verdict (only on blocks we actually verified)
    bv = bv_by_key.get((sid, tag, bid))
    if bv:
        h.append(render_bv_box(bv))
    # children
    for ck in children.get(key, []):
        h.append(render_node(ck, blocks, children, errs_by_key, opened, depth + 1, sid, bv_by_key))
    h.append('</div></details>')
    return "".join(h)


def main():
    by_sub = {}
    for r in ROWS:
        by_sub.setdefault(r["id"], []).append(r)

    sections = []
    nav = []
    for sid in sorted(set(FATAL_IDS) | set(by_sub)):
        pf_path = PF_DIR / f"{sid}.pf.txt"
        if not pf_path.exists():
            continue
        blocks, order = parse_pf(pf_path.read_text())
        children, theorem_keys = build_children(blocks)
        # errors by block key
        errs_by_key = {}
        for r in by_sub.get(sid, []):
            keys = [(pb["tag"], pb["id"]) for pb in r["pf_blocks"]]
            depth = lambda k: len(k[1].split(".")) if k[0] != "THEOREM" else 0
            primary = max(keys, key=depth) if keys else None
            for k in keys:
                errs_by_key.setdefault(k, []).append((r, k == primary))
        opened = open_set(errs_by_key)
        pn = int(sid[:2]); sub = sid[2:]
        n_err = len(by_sub.get(sid, []))
        nav.append(f'<a href="#s{sid}">{sid}</a>')
        sections.append(f'<h2 id="s{sid}" class="subhead">Problem {pn} · Submission {sub} '
                        f'<span class="cnt">{len(blocks)} blocks · {n_err} mapped error(s)</span></h2>')
        roots = theorem_keys or [k for k in order if k[1].count(".") == 0]
        for rk in roots:
            sections.append(render_node(rk, blocks, children, errs_by_key, opened, 0, sid, BV_BY_KEY))

    from collections import Counter
    agc = Counter((b.get("judge") or {}).get("agreement") for b in BV)
    page = TEMPLATE.format(nav=" ".join(nav), body="\n".join(sections),
                           n_sub=len([s for s in sorted(set(FATAL_IDS)|set(by_sub)) if (PF_DIR/f"{s}.pf.txt").exists()]),
                           n_err=len(ROWS), n_bv=len(BV),
                           n_agree=agc.get("agree", 0), n_partial=agc.get("partial", 0),
                           n_disagree=agc.get("disagree", 0))
    page = page.replace("<!--MATHJAX-->", mathjax_head())  # inline MathJax (self-contained)
    OUT.write_text(page, encoding="utf-8")
    print(f"Wrote {OUT} ({len(ROWS)} errors)")


TEMPLATE = r"""<!DOCTYPE html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>PF proof tree + mapped errors</title>
<!--MATHJAX-->
<style>
:root{{--ink:#171313;--gray:#69626d;--sand:#f2ece9;--line:#cdd6e4;}}
*{{box-sizing:border-box;}}
body{{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:var(--ink);
max-width:1000px;margin:0 auto;padding:20px 18px 80px;line-height:1.5;}}
h1{{margin:0 0 4px;}} .sub{{color:var(--gray);margin:0 0 12px;}}
.toolbar{{position:sticky;top:0;background:#fff;padding:8px 0;border-bottom:1px solid #eee;z-index:50;
white-space:nowrap;overflow-x:auto;box-shadow:0 2px 4px rgba(0,0,0,.05);}}
.toolbar a{{margin-right:8px;text-decoration:none;color:#1a73e8;font-size:.85em;}}
.subhead{{border-bottom:2px solid var(--ink);padding-bottom:4px;margin-top:30px;scroll-margin-top:46px;}}
.subhead .cnt{{font-size:.55em;color:var(--gray);font-weight:400;}}
.controls{{margin:8px 0;}} .controls button{{font-size:.82em;padding:3px 10px;margin-right:6px;border:1px solid var(--line);background:#f6f8fc;border-radius:6px;cursor:pointer;}}

/* tree nodes */
details.node{{border:1px solid var(--line);border-radius:8px;margin:6px 0;background:#fff;}}
details.node>.body{{padding:2px 12px 10px 28px;}}
details.node summary{{list-style:none;cursor:pointer;padding:8px 12px;display:flex;align-items:flex-start;gap:7px;
border-radius:8px;background:#eef2fb;}}
details.node summary::-webkit-details-marker{{display:none;}}
details.node summary::before{{content:"▶";color:#5b6b86;font-size:.8em;margin-top:3px;transition:transform .12s;}}
details.node[open]>summary::before{{transform:rotate(90deg);}}
.lab{{font-weight:700;color:#1f3b66;white-space:nowrap;}}
.ttl{{flex:1;overflow-wrap:anywhere;min-width:0;}}
.score{{font-size:.7em;font-weight:700;padding:2px 8px;border-radius:12px;white-space:nowrap;align-self:center;}}
.score.ok{{background:#e7ecf3;color:#8b94a3;}} .score.err{{color:#fff;text-transform:uppercase;}}

/* errored nodes stand out */
details.errnode{{border-color:#e0a9a3;}}
details.errnode>summary{{background:#fae9e6;}}

/* nested theorem root is bluer */
details.node>summary .lab{{}}

.mini{{display:block;font-size:.66em;text-transform:uppercase;letter-spacing:.5px;color:var(--gray);font-weight:700;margin:8px 0 1px;}}
.assum{{font-size:.92em;}} .assum,.stmt{{margin-top:2px;}}
.stmt{{background:#f7faff;border-left:3px solid #9fc0ef;padding:4px 10px;border-radius:0 6px 6px 0;overflow-x:auto;}}
.prf{{font-size:.93em;border-top:1px dotted var(--line);padding-top:4px;overflow-x:auto;}}
.assum{{overflow-x:auto;}}
.body{{overflow-wrap:anywhere;}}
ol.asm{{margin:4px 0;padding-left:22px;}} ol.asm li{{margin:3px 0;}}
.deps{{font-size:.78em;color:var(--gray);margin-top:6px;}}

/* mapped error = block-verifier-response box */
.vresp{{background:#fdecea;border:1px solid #e7b3ab;border-left:4px solid #b3261e;border-radius:0 8px 8px 0;padding:8px 11px;margin:10px 0 4px;}}
.vhead{{font-weight:600;margin-bottom:4px;}}
.pill{{color:#fff;font-size:.66em;font-weight:700;padding:2px 7px;border-radius:6px;text-transform:uppercase;}}
.pill.ghost{{background:#e7d7d4!important;color:#8a5a52;}}
.vdesc{{font-size:.93em;}}
.rquotes{{margin-top:2px;}}
.rquote{{border-left:3px solid #b3261e;background:#fff;padding:5px 11px;margin:5px 0;font-size:.93em;border-radius:0 6px 6px 0;}}
.rquote.nv{{border-left-style:dashed;}}
.rwho{{display:inline-block;font-size:.68em;font-weight:700;color:#b3261e;text-transform:uppercase;letter-spacing:.4px;margin-right:7px;vertical-align:1px;}}
.orig{{margin-top:8px;}} .orig>summary{{font-size:.82em;color:#8a5a52;cursor:pointer;font-weight:600;}}
.origtxt{{background:#fff;border:1px solid #eccfca;border-radius:6px;padding:7px 10px;margin-top:4px;font-size:.9em;}}
.vnote{{font-size:.82em;color:var(--gray);margin-top:5px;font-style:italic;}}
.vptr{{font-size:.84em;color:#8a5a52;background:#fbf1ef;border:1px dashed #e7b3ab;border-radius:6px;padding:5px 9px;margin:8px 0 4px;}}
.bvbox{{background:#eef4f1;border:1px solid #cfe0d6;border-left:4px solid #1a7f37;border-radius:0 8px 8px 0;padding:8px 11px;margin:8px 0 4px;}}
.bvhead{{font-weight:600;font-size:.92em;}}
.bvtag{{color:#fff;font-size:.66em;font-weight:700;padding:2px 7px;border-radius:6px;text-transform:uppercase;margin-right:6px;}}
.bvruns{{color:#69626d;font-size:.85em;}}
.bvjudge{{margin-top:5px;font-size:.9em;}}
.agpill{{color:#fff;font-size:.68em;font-weight:700;padding:2px 7px;border-radius:6px;text-transform:uppercase;}}
.bvexpl{{margin-top:4px;color:#333;font-size:.95em;}}
.bvreason{{margin-top:6px;}} .bvreason>summary{{font-size:.82em;color:#3a6b53;cursor:pointer;font-weight:600;}}
.bvreasontxt{{background:#fff;border:1px solid #d6e6dd;border-radius:6px;padding:7px 10px;margin-top:4px;font-size:.9em;max-height:400px;overflow:auto;}}
.vrlabel{{font-size:.66em;text-transform:uppercase;letter-spacing:.5px;color:#3a6b53;font-weight:700;margin:8px 0 2px;}}
.vrsample{{font-size:.7em;font-weight:700;color:#69626d;border-top:1px dashed #cfe0d6;padding-top:6px;margin-top:8px;}}
.vrsample:first-child{{border-top:0;}}
.vraud{{margin:2px 0;padding-left:20px;}} .vraud li{{margin:2px 0;}}
.audmark{{font-family:monospace;color:#1a7f37;}}
</style></head><body>
<h1>PF proof tree — review errors & block verification</h1>
<p class="sub">Each fatal-error proof shown as its pseudo-formalised tree (Theorem → Proposition → Lemma → Claim → Fact). Blocks with a mapped referee error are highlighted (with the verbatim reviewer comment); the {n_bv} deepest of those also carry the <b>blind block-verifier</b> verdict (N=3, pessimistic) and a judge label of whether it matches the golden reviewer comment (<span style="color:#1a7f37">agree</span> {n_agree} · <span style="color:#c77700">partial</span> {n_partial} · <span style="color:#b3261e">disagree/missed</span> {n_disagree}).</p>
<div class="toolbar">{nav}</div>
<div class="controls"><button onclick="document.querySelectorAll('details.node').forEach(d=>d.open=true)">expand all</button>
<button onclick="document.querySelectorAll('details.node').forEach(d=>d.open=false)">collapse all</button></div>
{body}
</body></html>"""


if __name__ == "__main__":
    main()
