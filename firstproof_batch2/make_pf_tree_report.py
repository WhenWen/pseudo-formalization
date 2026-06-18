"""Render each PF'd proof as an interactive collapsible PROOF TREE:
Theorem -> Propositions -> Lemmas -> Claims -> Facts, each node expandable and
showing its Assumptions/Conditions/Definitions, Statement, Proof and DEPS. Review
errors (from pf_review_map_checked.json) are attached inline to the blocks they map
to, as a salmon "review / error" box (the analog of a block-verifier response).

Output: pf_tree.html
"""

import html
import json
import os
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

# Optional: restrict to a leaner set of proofs (LEANER_SET=path to leaner_set.json).
_lean = os.environ.get("LEANER_SET")
if _lean:
    _keep = set(json.loads((HERE / _lean).read_text())["leaner_sids"])
    ROWS = [r for r in ROWS if r["id"] in _keep]
    FATAL_IDS = [s for s in FATAL_IDS if s in _keep]
    OUT = HERE / os.environ.get("PF_TREE_OUT", "pf_tree_lean.html")

# Blind block-verifier results + judge verdicts (optional).
_bv = HERE / "block_verify_results.json"
_jg = HERE / "verdict_judgements.json"
BV = json.loads(_bv.read_text()) if _bv.exists() else []
JUDGE = json.loads(_jg.read_text()) if _jg.exists() else []
_tv = HERE / "theorem_verify_results.json"
THEOREM_VS = {(r["sid"], r["tag"], r["id"]): r for r in (json.loads(_tv.read_text()) if _tv.exists() else [])}
_ws = HERE / "websearch_verify_results.json"
WS_BY_KEY = {(r["sid"], r["tag"], r["id"]): r for r in (json.loads(_ws.read_text()) if _ws.exists() else [])}
_v3 = HERE / "bv_v3_results.json"
V3_BY_KEY = {(r["sid"], r["tag"], r["id"]): r for r in (json.loads(_v3.read_text()) if _v3.exists() else [])}
_v4 = HERE / "bv_v4_results.json"
V4_BY_KEY = {(r["sid"], r["tag"], r["id"]): r for r in (json.loads(_v4.read_text()) if _v4.exists() else [])}
_jmap = {(j["sid"], j["label"]): j for j in JUDGE}
# keyed by (sid, tag, id); attach the matching judge verdict
BV_BY_KEY = {}
for b in BV:
    b = {**b, "judge": _jmap.get((b["sid"], b["label"]))}
    BV_BY_KEY[(b["sid"], b["tag"], b["id"])] = b

AGREE_COLOR = {"agree": "#1a7f37", "partial": "#c77700", "disagree": "#b3261e", None: "#777"}
# consistent match symbols: tick=matched, star=partial, cross=not matched
SYM = {"agree": "✓", "partial": "★", "disagree": "✗", None: "•"}


def sym_span(agreement):
    return f'<span class="msym" style="color:{AGREE_COLOR.get(agreement, "#777")}">{SYM.get(agreement, "•")}</span>'

SEV = {"fatal": "#b3261e", "major": "#c77700", "minor": "#7a7a00"}
TAGS = ["THEOREM", "PROPOSITION", "LEMMA", "CLAIM", "FACT"]
SHORT = {"THEOREM": "Thm", "PROPOSITION": "Prop", "LEMMA": "Lem", "CLAIM": "Claim", "FACT": "Fact"}

BLOCK_RE = re.compile(
    r'<(THEOREM|PROPOSITION|LEMMA|CLAIM|FACT)_(STATEMENT|PROOF) id="([^"]+)">(.*?)</\1_\2>',
    re.DOTALL)
DEPS_RE = re.compile(r'<DEPS id="([^"]+)">(.*?)</DEPS>', re.DOTALL)
_DEPTH_TAG = {1: "PROPOSITION", 2: "LEMMA", 3: "CLAIM", 4: "FACT"}


def dep_keys(deps_str):
    """Resolve a DEPS string into the set of cited (tag, id) blocks."""
    out = set()
    for d in (deps_str or "").split(","):
        d = d.strip()
        if not d:
            continue
        if d.startswith("theorem_"):
            out.add(("THEOREM", d[8:]))
        elif d.isdigit() or "." in d:
            out.add((_DEPTH_TAG.get(d.count(".") + 1), d))
    return {k for k in out if k[0]}


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


def block_anchor(sid, tag, bid):
    return f'bv-{sid}-{tag.lower()}-{bid.replace(".", "-")}'


def _runs_from_theorem(tv):
    """Make the matching verifier uniform with the judged verifiers: a catch
    (INCORRECT vs the original problem) counts as a match (agree)."""
    rvs = tv.get("run_verdicts", [])
    rjs = [{"verdict": v, "agreement": "agree" if v == "INCORRECT" else "disagree",
            "explanation": ""} for v in rvs]
    return rvs, tv.get("run_outputs", []), rjs


def version_box(box_id, title, run_verdicts, run_outputs, run_judges, cit_runs=None, web_total=None):
    """One collapsible, self-contained verifier-version box (used by v1/tm/v2/v3)."""
    if not run_verdicts:
        return ""
    caught = "INCORRECT" in run_verdicts
    col = "#1a7f37" if caught else "#b3261e"
    rank = {"agree": 0, "partial": 1, "disagree": 2}
    best = min((rj.get("agreement") for rj in run_judges if rj),
               key=lambda a: rank.get(a, 3), default=None)
    runsyms = "".join("✗" if v == "INCORRECT" else "✓" for v in run_verdicts)
    web = f' · {web_total} web source(s)' if web_total is not None else ''
    h = [f'<details class="bvbox vbox mj-lazy" id="{box_id}" style="border-left-color:{col}">']
    h.append('<summary class="bvhead">' + sym_span(best) + ' '
             f'<span class="bvtag" style="background:{col}">{esc(title)}</span> '
             f'{"flagged INCORRECT (any run)" if caught else "said CORRECT"}'
             f'<span class="bvruns"> · runs: {runsyms}{web}</span></summary>')
    h.append('<div class="bvruns-v">')
    for k, rv in enumerate(run_verdicts):
        rcol = "#1a7f37" if rv == "INCORRECT" else "#b3261e"
        rj = run_judges[k] if k < len(run_judges) else {}
        rag = (rj or {}).get("agreement")
        ro = run_outputs[k] if k < len(run_outputs) else ""
        nc = f' · {cit_runs[k]} web source(s)' if cit_runs and k < len(cit_runs) else ''
        h.append('<div class="bvrun">'
                 f'<div class="bvrunh">Run {k+1} &nbsp;<span class="rv" style="color:{rcol}">'
                 f'{"INCORRECT — flagged" if rv == "INCORRECT" else "CORRECT — no flag"}</span>'
                 f'<span class="bvruns">{nc}</span></div>'
                 '<div class="bvout"><div class="bvsublabel">Verifier output</div>'
                 f'{render_verifier_reasoning(ro) if ro else "<em>(no output)</em>"}</div>'
                 + (f'<div class="bvmatchblock" style="border-left-color:{AGREE_COLOR.get(rag, "#777")}">'
                    f'<div class="bvsublabel">Matches reviewer comment? {sym_span(rag)} '
                    f'<span class="agpill" style="background:{AGREE_COLOR.get(rag)}">{esc(rag)}</span></div>'
                    + (f'<div class="bvexpl">{latex_segment_to_html((rj or {}).get("explanation", ""))}</div>' if rj and rj.get("explanation") else "")
                    + '</div>' if rag else "")
                 + '</div>')
    h.append('</div></details>')
    return "".join(h)


def render_bv_box(key):
    """All verifier versions for a block, as PARALLEL collapsible boxes.
    Keyed by (sid,tag,id); each version renders only if it has a result, so a block
    that was (re-)verified by only some versions still shows correctly."""
    sid, tag, bid = key
    vid = block_anchor(sid, tag, bid)
    out = ['<div class="bvversions">']
    # v1 — no web search (only if present)
    bv = BV_BY_KEY.get(key)
    if bv:
        out.append(version_box(f"{vid}-v1", f'v1 · Block verifier (no web, N={bv.get("n", 1)})',
                               bv.get("run_verdicts") or [], bv.get("run_outputs") or [],
                               bv.get("run_judges") or []))
    # tm — theorem vs ORIGINAL problem (theorem blocks)
    tv = THEOREM_VS.get(key)
    if tv:
        rvs, ros, rjs = _runs_from_theorem(tv)
        out.append(version_box(f"{vid}-tm", f'theorem · vs ORIGINAL problem (N={tv.get("n", len(rvs))})',
                               rvs, ros, rjs))
    # v2 — web search (citation fact-check)
    wr = WS_BY_KEY.get(key)
    if wr:
        out.append(version_box(f"{vid}-v2", f'v2 · + web search (citations, N={wr.get("n", 1)})',
                               wr.get("run_verdicts") or [], wr.get("run_outputs") or [],
                               wr.get("run_judges") or [], wr.get("web_citation_runs"), wr.get("web_citations", 0)))
    # v3 — web + definitions + counterexample (not-matched blocks only)
    v3 = V3_BY_KEY.get(key)
    if v3:
        out.append(version_box(f"{vid}-v3", f'v3 · + definitions & counterexample (N={v3.get("n", 1)})',
                               v3.get("run_verdicts") or [], v3.get("run_outputs") or [],
                               v3.get("run_judges") or [], v3.get("web_citation_runs"), v3.get("web_citations", 0)))
    # v4 — web + verbatim definition/lemma pinning (never-matched blocks only)
    v4 = V4_BY_KEY.get(key)
    if v4:
        out.append(version_box(f"{vid}-v4", f'v4 · + verbatim definition/lemma pinning (N={v4.get("n", 1)})',
                               v4.get("run_verdicts") or [], v4.get("run_outputs") or [],
                               v4.get("run_judges") or [], v4.get("web_citation_runs"), v4.get("web_citations", 0)))
    out.append('</div>')
    return "".join(out)


def _OLD_render_bv_box(bv):
    """Block-verifier verdict box (blind, N=3) + judge agreement vs golden."""
    caught = bv["verdict"] == "INCORRECT"
    runs = bv.get("run_verdicts", [])
    runtxt = (" · runs: " + " ".join("✗" if v == "INCORRECT" else "✓" for v in runs)) if runs else ""
    head_col = "#1a7f37" if caught else "#b3261e"
    head_lbl = "flagged INCORRECT — caught" if caught else "said CORRECT — missed"
    j = bv.get("judge") or {}
    ag = j.get("agreement")
    vid = f'bv-{bv["sid"]}-{bv["tag"].lower()}-{bv["id"].replace(".", "-")}'
    h = [f'<div class="bvbox" id="{vid}-v1" style="border-left-color:{head_col}">']
    h.append(f'<div class="bvhead"><span class="bvtag" style="background:{head_col}">'
             f'v1 · Block verifier (no web, N={bv.get("n", 1)})</span> {head_lbl}'
             f'<span class="bvruns">{runtxt}</span></div>')
    run_judges = bv.get("run_judges")
    run_outputs = bv.get("run_outputs") or []
    if run_judges:
        # three runs stacked vertically; each shows the verifier OUTPUT first,
        # then a "matches reviewer?" visualization block.
        h.append('<div class="bvruns-v">')
        for k, rj in enumerate(run_judges):
            rv = rj.get("verdict", runs[k] if k < len(runs) else "")
            ag = rj.get("agreement")
            agcol = AGREE_COLOR.get(ag, "#777")
            same = rj.get("verifier_found_same_error")
            ro = run_outputs[k] if k < len(run_outputs) else ""
            rcol = "#1a7f37" if rv == "INCORRECT" else "#b3261e"
            rlbl = "INCORRECT — flagged" if rv == "INCORRECT" else "CORRECT — no flag"
            h.append('<div class="bvrun">')
            h.append(f'<div class="bvrunh">Run {k+1} &nbsp;<span class="rv" style="color:{rcol}">{rlbl}</span></div>')
            # 1) block verifier output
            h.append('<div class="bvout"><div class="bvsublabel">Block verifier output</div>'
                     f'{render_verifier_reasoning(ro) if ro else "<em>(no output)</em>"}</div>')
            # 2) match-vs-reviewer visualization
            h.append(f'<div class="bvmatchblock" style="border-left-color:{agcol}">'
                     f'<div class="bvsublabel">Matches reviewer comment? {sym_span(ag)} '
                     f'<span class="agpill" style="background:{agcol}">{esc(ag)}</span> '
                     + ("<b>same error</b>" if same else "different / none") + '</div>'
                     + (f'<div class="bvexpl">{esc(rj.get("explanation",""))}</div>' if rj.get("explanation") else "")
                     + '</div>')
            h.append('</div>')
        h.append('</div>')
    elif ag:  # fallback: single aggregated judge
        h.append(f'<div class="bvjudge">vs golden reviewer: {sym_span(ag)} '
                 f'<span class="agpill" style="background:{AGREE_COLOR.get(ag)}">{esc(ag)}</span> '
                 + ("(same error)" if j.get("verifier_found_same_error") else "(different/none)")
                 + (f'<div class="bvexpl">{esc(j.get("explanation",""))}</div>' if j.get("explanation") else "")
                 + '</div>')
    # theorem-level check against the ORIGINAL problem statement (scope check)
    tv = THEOREM_VS.get((bv["sid"], bv["tag"], bv["id"]))
    if tv:
        caught = tv["verdict"] == "INCORRECT"
        col = "#1a7f37" if caught else "#b3261e"
        lbl = ("flagged INCORRECT — proves a different/conditional statement than asked"
               if caught else "said CORRECT — proof matches the original problem")
        ed = ""
        for o in tv.get("run_outputs", []):
            m = re.search(r"<error_description>(.*?)</error_description>", o or "", re.DOTALL)
            if m and m.group(1).strip():
                ed = m.group(1).strip(); break
        rv = " ".join("✗" if v == "INCORRECT" else "✓" for v in tv.get("run_verdicts", []))
        h.append(f'<div class="bvbox tvbox" id="{vid}-tm" style="border-left-color:{col}">'
                 f'<div class="bvhead">{sym_span("agree" if caught else "disagree")} '
                 f'<span class="bvtag" style="background:{col}">'
                 f'Verifier vs ORIGINAL problem (blind, N=3)</span> {lbl}'
                 f'<span class="bvruns"> · runs: {rv}</span></div>'
                 + (f'<div class="bvexpl">{latex_segment_to_html(ed)}</div>' if ed else "")
                 + '</div>')
    # v2: block verifier WITH web search (citation fact-check)
    h.append(render_web_box(WS_BY_KEY.get((bv["sid"], bv["tag"], bv["id"])),
                            "v2 · + web search (citation fact-check)"))
    # v3: web search + definition-pinning + counterexample-seeking
    h.append(render_web_box(V3_BY_KEY.get((bv["sid"], bv["tag"], bv["id"])),
                            "v3 · + definitions & counterexample search"))
    h.append('</div>')
    return "".join(h)


def render_web_box(wr, title):
    """Render a multi-run web-enabled verifier box (used by v2 and v3)."""
    if not wr:
        return ""
    caught = wr["verdict"] == "INCORRECT"
    wcol = "#1a7f37" if caught else "#b3261e"
    ag = (wr.get("judge") or {}).get("agreement")
    runsyms = "".join("✗" if v == "INCORRECT" else "✓" for v in (wr.get("run_verdicts") or []))
    h = [f'<div class="bvbox wsbox" style="border-left-color:{wcol}">'
         f'<div class="bvhead">{sym_span(ag)} '
         f'<span class="bvtag" style="background:{wcol}">{esc(title)} (blind, N={wr.get("n", 1)})</span> '
         f'{"flagged INCORRECT (any run)" if caught else "said CORRECT"} '
         f'<span class="bvruns">· runs: {runsyms} · {wr.get("web_citations", 0)} web source(s)</span></div>']
    rvs = wr.get("run_verdicts") or []
    ros = wr.get("run_outputs") or []
    rjs = wr.get("run_judges") or []
    cps = wr.get("web_citation_runs") or []
    if rvs:
        h.append('<div class="bvruns-v">')
        for k in range(len(rvs)):
            rv = rvs[k]
            rcol = "#1a7f37" if rv == "INCORRECT" else "#b3261e"
            rj = rjs[k] if k < len(rjs) else {}
            rag = (rj or {}).get("agreement")
            ro = ros[k] if k < len(ros) else ""
            nc = cps[k] if k < len(cps) else 0
            h.append('<div class="bvrun">'
                     f'<div class="bvrunh">Run {k+1} &nbsp;<span class="rv" style="color:{rcol}">'
                     f'{"INCORRECT — flagged" if rv == "INCORRECT" else "CORRECT — no flag"}</span>'
                     f' <span class="bvruns">· {nc} web source(s)</span></div>'
                     '<div class="bvout"><div class="bvsublabel">Verifier output</div>'
                     f'{render_verifier_reasoning(ro) if ro else "<em>(no output)</em>"}</div>'
                     f'<div class="bvmatchblock" style="border-left-color:{AGREE_COLOR.get(rag, "#777")}">'
                     f'<div class="bvsublabel">Matches reviewer comment? {sym_span(rag)} '
                     f'<span class="agpill" style="background:{AGREE_COLOR.get(rag)}">{esc(rag)}</span></div>'
                     + (f'<div class="bvexpl">{latex_segment_to_html((rj or {}).get("explanation", ""))}</div>' if rj and rj.get("explanation") else "")
                     + '</div></div>')
        h.append('</div>')
    h.append('</div>')
    return "".join(h)


def render_node(key, blocks, children, errs_by_key, opened, depth, sid, bv_by_key, calls_wrong):
    b = blocks[key]
    tag, bid = key
    assumptions, body = split_statement(b.get("statement"))
    errs = errs_by_key.get(key, [])  # list of (row, is_primary)
    is_root_err = any(is_primary for (_, is_primary) in errs)   # deepest block of an error
    has_nonroot_err = bool(errs) and not is_root_err            # ancestor that only contains a deeper error
    wrong_called = calls_wrong.get(key, [])                     # DEPS cite a root-errored block
    is_err = is_root_err                                        # RED only for the root
    is_calls = (has_nonroot_err or bool(wrong_called)) and not is_root_err  # ORANGE
    is_open = key in opened or tag == "THEOREM"

    title = title_of(body, f"{SHORT[tag]} {bid}")
    # right-side badge: severity if errored, else a faint "block" marker
    if is_err:
        sev = max(errs, key=lambda t: ["minor", "major", "fatal"].index(t[0]["severity"]))[0]["severity"]
        badge = f'<span class="score err" style="background:{SEV[sev]}">{esc(sev)}</span>'
    else:
        badge = '<span class="score ok">no error flagged</span>'

    cls = "node" + (" errnode" if is_err else (" callsnode" if is_calls else ""))
    op = " open" if is_open else ""
    if is_calls:  # override the "no error flagged" badge for calls-wrong-lemma blocks
        badge = '<span class="score calls">calls flagged lemma</span>'
    anchor = f'blk-{sid}-{tag.lower()}-{bid.replace(".", "-")}'
    h = [f'<details class="{cls}" id="{anchor}"{op}>']
    label = "Thm:" if tag == "THEOREM" else f"{SHORT[tag]}. {bid}:"
    h.append(f'<summary><span class="lab">{esc(label)}</span> '
             f'<span class="ttl">{latex_segment_to_html(title)}</span>{badge}</summary>')
    h.append('<div class="body">')
    if is_calls and wrong_called:
        links = ", ".join(f'{SHORT[c[0]]} {c[1]}' for c in wrong_called)
        h.append(f'<div class="callsbox">⚠ This proof invokes a flagged (wrong) result: '
                 f'<b>{esc(links)}</b> — the defect is rooted there, not in this block.</div>')
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
                     f'<div class="origtxt">{latex_segment_to_html(e["error_description"])}</div></details>')
            if e.get("mapping_note"):
                h.append(f'<div class="vnote">map note: {esc(e["mapping_note"])}</div>')
            h.append('</div>')
        else:
            cb = e.get("critical_block") or {}
            ct, ci = cb.get("tag"), cb.get("id")
            where = f"{SHORT.get(ct, ct)} {ci}" if ct else "the flagged block"
            h.append(f'<div class="vptr"><span class="pill" style="background:{SEV[e["severity"]]}">{esc(e["severity"])}</span> '
                     f'involved in error “{esc(e["title"])}” — root cause is in {esc(where)}</div>')
    # block-verifier verdict (render if ANY version verified this block)
    k = (sid, tag, bid)
    if k in BV_BY_KEY or k in WS_BY_KEY or k in V3_BY_KEY or k in V4_BY_KEY or k in THEOREM_VS:
        h.append(render_bv_box(k))
    # children
    for ck in children.get(key, []):
        h.append(render_node(ck, blocks, children, errs_by_key, opened, depth + 1, sid, bv_by_key, calls_wrong))
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
            cb = r.get("critical_block")
            primary = (cb["tag"], cb["id"]) if cb else (max(keys, key=depth) if keys else None)
            # the audited critical block may not be among the originally mapped blocks
            for k in set(keys) | ({primary} if primary else set()):
                errs_by_key.setdefault(k, []).append((r, k == primary))
        # ROOT errored blocks = the deepest mapped block per error (where the
        # defect actually lives). Only these are red; ancestors / DEPS-callers are orange.
        root_errored = set()
        for r in by_sub.get(sid, []):
            cb = r.get("critical_block")
            if cb:
                root_errored.add((cb["tag"], cb["id"]))
            else:
                pb = max(r["pf_blocks"], key=lambda p: 0 if p["tag"] == "THEOREM" else len(p["id"].split(".")))
                root_errored.add((pb["tag"], pb["id"]))
        # blocks (not themselves a root error) whose DEPS cite a root-errored block
        calls_wrong = {}
        for k, blk in blocks.items():
            wrong = [c for c in dep_keys(blk.get("deps", "")) if c in root_errored]
            if wrong and k not in root_errored:
                calls_wrong[k] = wrong
        opened = open_set(errs_by_key) | set(calls_wrong) | {
            (_DEPTH_TAG[i], ".".join(k[1].split(".")[:i]))
            for k in calls_wrong for i in range(1, len(k[1].split(".")))
        }
        pn = int(sid[:2]); sub = sid[2:]
        n_err = len(by_sub.get(sid, []))
        # level-2: critical (wrong) blocks, each marked with its match symbol
        # (✓ agree / ★ partial / ✗ disagree vs the golden reviewer comment).
        judge_by = {(j["sid"], j["label"]): j for j in JUDGE}
        crit = {}
        for r in by_sub.get(sid, []):
            cb = r.get("critical_block")
            if cb:
                crit.setdefault((cb["tag"], cb["id"]), set()).add(r["error_type"])
        sublinks, all_ags = [], []
        for (tag, bid) in sorted(crit, key=lambda k: (k[0] != "THEOREM", [int(p) for p in k[1].split(".")])):
            vid = block_anchor(sid, tag, bid)
            blkanc = f"blk-{sid}-{tag.lower()}-{bid.replace('.', '-')}"
            # collect each verifier version's per-run agreements
            std = [(rj or {}).get("agreement") for rj in ((BV_BY_KEY.get((sid, tag, bid)) or {}).get("run_judges") or [])]
            tv = THEOREM_VS.get((sid, tag, bid))
            tm = ["agree" if v == "INCORRECT" else "disagree" for v in tv.get("run_verdicts", [])] if tv else []
            ws = [(rj or {}).get("agreement") for rj in ((WS_BY_KEY.get((sid, tag, bid)) or {}).get("run_judges") or [])]
            v3 = V3_BY_KEY.get((sid, tag, bid))
            v3ags = [(rj or {}).get("agreement") for rj in (v3.get("run_judges") or [])] if v3 else []
            v4 = V4_BY_KEY.get((sid, tag, bid))
            v4ags = [(rj or {}).get("agreement") for rj in (v4.get("run_judges") or [])] if v4 else []
            all_ags += std + tm + ws + v3ags + v4ags
            # level-3: one line per verifier version, linking to that version's box
            verlines = []
            for label, ags, suff in [("v1", std, "v1"), ("thm", tm, "tm"), ("v2", ws, "v2"), ("v3", v3ags, "v3"), ("v4", v4ags, "v4")]:
                if ags:
                    verlines.append(f'<a class="sidever" href="#{vid}-{suff}">'
                                    f'<span class="vlabel">{label}</span> '
                                    f'<span class="msyms">{"".join(sym_span(a) for a in ags)}</span></a>')
            sublinks.append(f'<div class="sideblock"><a class="sideblk blockhdr" href="#{blkanc}">{SHORT[tag]} {bid}</a>'
                            f'<div class="sidevers">{"".join(verlines)}</div></div>')
        # level-1 (proof) symbol: ✓ if ANY (block,run) matched, else ★ if ANY partial, else ✗
        lvl = "agree" if "agree" in all_ags else ("partial" if "partial" in all_ags else "disagree")
        nav.append('<details class="sideproof" open><summary class="sidelink">'
                   f'<span class="msym" style="color:{AGREE_COLOR[lvl]}">{SYM[lvl]}</span> <b>P{pn}·{sub}</b></summary>'
                   f'<div class="sidekids"><a class="sideblk top" href="#s{sid}">overview</a>{"".join(sublinks)}</div></details>')
        sections.append(f'<h2 id="s{sid}" class="subhead">Problem {pn} · Submission {sub} '
                        f'<span class="cnt">{len(blocks)} blocks · {n_err} mapped error(s)</span></h2>')
        roots = theorem_keys or [k for k in order if k[1].count(".") == 0]
        for rk in roots:
            sections.append(render_node(rk, blocks, children, errs_by_key, opened, 0, sid, BV_BY_KEY, calls_wrong))

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
margin:0;line-height:1.5;}}
h1{{margin:0 0 4px;}} .sub{{color:var(--gray);margin:0 0 12px;}}
.layout{{display:flex;align-items:flex-start;}}
.side{{position:sticky;top:0;align-self:flex-start;height:100vh;overflow-y:auto;flex:0 0 210px;
background:#f7f8fb;border-right:1px solid var(--line);padding:12px 8px;}}
.sidehead{{font-size:.7em;text-transform:uppercase;letter-spacing:.5px;color:var(--gray);font-weight:700;margin:0 6px 8px;}}
.sideproof{{margin-bottom:3px;}}
.sideproof>summary{{list-style:none;cursor:pointer;}}
.sideproof>summary::-webkit-details-marker{{display:none;}}
.sideproof>summary::before{{content:"▸";color:#9aa6b8;font-size:.8em;margin-right:3px;}}
.sideproof[open]>summary::before{{content:"▾";}}
.sidelink{{display:block;text-decoration:none;color:#1f3b66;padding:4px 6px;border-radius:6px;font-size:.85em;}}
summary.sidelink{{padding:4px 4px;}}
.sidelink:hover{{background:#e7eefb;}}
.sidelink b{{display:inline-block;min-width:42px;}}
.sidekids{{margin:1px 0 4px 16px;border-left:1px solid #dfe5ee;padding-left:6px;}}
.sideblk{{display:block;text-decoration:none;color:#3a517a;font-size:.8em;padding:2px 6px;border-radius:5px;}}
.sideblk:hover{{background:#e7eefb;}} .sideblk.top{{color:#8893a6;font-style:italic;}}
.sideblock{{margin:2px 0;}}
.blockhdr{{font-weight:600;color:#1f3b66;}}
.sidevers{{margin-left:12px;border-left:1px dotted #dfe5ee;padding-left:5px;}}
.sidever{{display:flex;gap:6px;text-decoration:none;color:#5a6b86;font-size:.78em;padding:1px 5px;border-radius:5px;}}
.sidever:hover{{background:#eef2fb;}}
.vlabel{{display:inline-block;min-width:26px;color:#8893a6;font-weight:700;}}
.msym{{font-weight:700;}} .msyms{{font-weight:700;letter-spacing:1px;font-family:monospace;}}
/* parallel collapsible verifier-version boxes */
.bvversions{{margin:8px 0 4px;}}
details.vbox{{margin:6px 0;}}
details.vbox>summary{{list-style:none;cursor:pointer;}}
details.vbox>summary::-webkit-details-marker{{display:none;}}
details.vbox>summary::before{{content:"▸ ";color:#9aa6b8;}}
details.vbox[open]>summary::before{{content:"▾ ";}}
:target{{scroll-margin-top:8px;animation:flashbg 1.4s ease-out;}}
@keyframes flashbg{{from{{background:#fff6cc;}}to{{background:transparent;}}}}
.vsep{{color:#c2c8d2;margin:0 2px;}}
.sidemeta,.sidmeta{{color:var(--gray);font-size:.85em;}} .sidn{{font-weight:700;}}
.sidn.hit{{color:#1a7f37;}} .sidn.miss{{color:#b3261e;}}
.content{{flex:1;min-width:0;max-width:1000px;padding:20px 22px 80px;}}
.subhead{{border-bottom:2px solid var(--ink);padding-bottom:4px;margin-top:30px;scroll-margin-top:8px;}}
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
/* blocks that call a flagged (wrong) lemma but are not the root error */
details.callsnode{{border-color:#e7c596;}}
details.callsnode>summary{{background:#fdf1e1;}}
.score.calls{{background:#c77700;color:#fff;}}
.callsbox{{background:#fdf1e1;border:1px solid #e7c596;border-left:4px solid #c77700;border-radius:0 8px 8px 0;padding:7px 11px;margin:6px 0;font-size:.9em;}}

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
.vptr{{font-size:.84em;color:#8a5a00;background:#fdf1e1;border:1px dashed #e7c596;border-radius:6px;padding:5px 9px;margin:8px 0 4px;}}
.bvbox{{background:#eef4f1;border:1px solid #cfe0d6;border-left:4px solid #1a7f37;border-radius:0 8px 8px 0;padding:8px 11px;margin:8px 0 4px;}}
.bvhead{{font-weight:600;font-size:.92em;}}
.bvtag{{color:#fff;font-size:.66em;font-weight:700;padding:2px 7px;border-radius:6px;text-transform:uppercase;margin-right:6px;}}
.bvruns{{color:#69626d;font-size:.85em;}}
.bvjudge{{margin-top:5px;font-size:.9em;}}
.agpill{{color:#fff;font-size:.68em;font-weight:700;padding:2px 7px;border-radius:6px;text-transform:uppercase;}}
.bvexpl{{margin-top:4px;color:#333;font-size:.92em;}}
.bvruns-v{{display:flex;flex-direction:column;gap:10px;margin-top:6px;}}
.bvrun{{background:#fbfdfc;border:1px solid #d6e6dd;border-radius:8px;padding:9px 11px;}}
.bvrunh{{font-weight:700;font-size:.9em;margin-bottom:5px;}} .bvrunh .rv{{font-weight:700;}}
.bvsublabel{{font-size:.66em;text-transform:uppercase;letter-spacing:.5px;color:#69626d;font-weight:700;margin-bottom:3px;}}
.bvout{{background:#fff;border:1px solid #e3e8ee;border-radius:6px;padding:7px 10px;max-height:340px;overflow:auto;}}
.bvmatchblock{{background:#f7f8fb;border:1px solid #e6e6ee;border-left:4px solid #777;border-radius:0 6px 6px 0;padding:7px 10px;margin-top:8px;}}
.bvreason{{margin-top:6px;}} .bvreason>summary{{font-size:.82em;color:#3a6b53;cursor:pointer;font-weight:600;}}
.bvreasontxt{{background:#fff;border:1px solid #d6e6dd;border-radius:6px;padding:7px 10px;margin-top:4px;font-size:.9em;max-height:400px;overflow:auto;}}
.vrlabel{{font-size:.66em;text-transform:uppercase;letter-spacing:.5px;color:#3a6b53;font-weight:700;margin:8px 0 2px;}}
.vrsample{{font-size:.7em;font-weight:700;color:#69626d;border-top:1px dashed #cfe0d6;padding-top:6px;margin-top:8px;}}
.vrsample:first-child{{border-top:0;}}
.vraud{{margin:2px 0;padding-left:20px;}} .vraud li{{margin:2px 0;}}
.audmark{{font-family:monospace;color:#1a7f37;}}
</style></head><body>
<div class="layout">
<nav class="side"><div class="sidehead">Proofs › wrong blocks<br><span style="font-weight:400;text-transform:none"><span style="color:#1a7f37">✓</span> matched · <span style="color:#c77700">★</span> partial · <span style="color:#b3261e">✗</span> not matched.<br>Per block, symbols per run by verifier version: <b>v1</b> (no web) · <b>|</b> theorem-vs-original (theorem blocks) · <b>v2</b> (web, citations) · <b>v3</b> (web + definitions + counterexample) · <b>v4</b> (web + verbatim definition/lemma pinning).<br>Proof: ✓ if any run of any block/version matched, else ★ if any partial, else ✗.</span></div>{nav}</nav>
<main class="content">
<h1>PF proof tree — review errors & block verification</h1>
<p class="sub">Each fatal-error proof shown as its pseudo-formalised tree (Theorem → Proposition → Lemma → Claim → Fact). Blocks with a mapped referee error are highlighted <span style="color:#b3261e">red</span> (with the verbatim reviewer comment); blocks that are not the root error but <span style="color:#c77700">call a flagged (wrong) lemma</span> via their dependencies are marked orange. The {n_bv} deepest flagged blocks also carry the <b>blind block-verifier</b> verdict (N=3, pessimistic) and a judge label of whether it matches the golden reviewer comment (<span style="color:#1a7f37">agree</span> {n_agree} · <span style="color:#c77700">partial</span> {n_partial} · <span style="color:#b3261e">disagree/missed</span> {n_disagree}).</p>
<div class="controls"><button onclick="document.querySelectorAll('details.node').forEach(d=>d.open=true)">expand all</button>
<button onclick="document.querySelectorAll('details.node').forEach(d=>d.open=false)">collapse all</button></div>
{body}
</main>
</div>
<script>
// Lazy MathJax: verifier boxes carry class "mj-lazy" and are skipped at load (keeps
// theorems/statements/quotes fast). Typeset a box the first time it is opened.
function mjTypeset(el){{
  if(!el || !window.MathJax || !MathJax.typesetPromise) return;
  el.querySelectorAll('.mj-lazy').forEach(function(n){{ n.classList.remove('mj-lazy'); }});
  if(el.classList) el.classList.remove('mj-lazy');
  if(el.dataset.mjDone) return;
  el.dataset.mjDone = '1';
  MathJax.typesetPromise([el]);
}}
// toggle does not bubble -> listen in capture phase
document.addEventListener('toggle', function(e){{
  if(e.target.tagName === 'DETAILS' && e.target.open) mjTypeset(e.target);
}}, true);
// open a target collapsible (and all ancestor collapsibles) when navigated to via #hash
function openTarget(){{
  var el = location.hash ? document.getElementById(decodeURIComponent(location.hash.slice(1))) : null;
  if(!el) return;
  var p = el;
  while(p){{ if(p.tagName === 'DETAILS'){{ p.open = true; mjTypeset(p); }} p = p.parentElement; }}
  mjTypeset(el);
  el.scrollIntoView();
}}
window.addEventListener('hashchange', openTarget);
window.addEventListener('load', openTarget);
</script>
</body></html>"""


if __name__ == "__main__":
    main()
