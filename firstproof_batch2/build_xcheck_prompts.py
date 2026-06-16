"""Build one Codex cross-check prompt per mapped error (from pf_review_map.json).
Codex independently judges whether the review-error -> PF-block mapping is correct
and whether the flaw is still present in the named PF block(s). The full PF rewrite
is included so Codex can tell if a different block would fit better.

Prompts -> codex_xcheck/prompts/<NNN>__<id>.txt  (NNN = row index, zero-padded)
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROWS = json.loads((HERE / "pf_review_map.json").read_text())
PF_DIR = HERE / "pf_outputs"
OUT = HERE / "codex_xcheck" / "prompts"
OUT.mkdir(parents=True, exist_ok=True)

TMPL = """You are an INDEPENDENT checker. An automated tool mapped one error found in a flawed mathematics proof to the block(s) of that proof's pseudo-formalised (PF) rewrite. Verify that mapping.

The PF rewrite decomposes the proof into tagged blocks THEOREM/PROPOSITION/LEMMA/CLAIM/FACT, each with a _STATEMENT and _PROOF and a dotted id.

== ERROR ==
title: {title}
type / severity: {etype} / {sev}
description: {desc}

== ORIGINAL TEXT THE AUTHOR WROTE (the errored span) ==
{orig}

== PROPOSED MAPPING ==
The tool claims this span maps to these PF block(s): {blockids}
Its note: {note}

== EXTRACTED TEXT OF THOSE PROPOSED PF BLOCK(S) ==
{expansion}

== FULL PF REWRITE (reference; check whether a different block fits better) ==
{pf}

Decide:
1. mapping_correct: do the proposed PF block(s) correctly correspond to the original errored content? Use "partial" if they capture it but miss/overreach a block, "no" if a different block is the real home.
2. error_present_in_pf: is the SAME flaw still present and visible in the proposed PF block(s), i.e. NOT silently repaired? ("partial" = weakened/obscured).
3. confidence: your confidence in this judgement.
4. suggested_blocks: if mapping_correct is not "yes", name the better PF block id(s) (e.g. "LEMMA 4.2"); else "".
5. assessment: 1-3 sentences explaining your verdict.

Respond ONLY with the JSON object required by the output schema."""


def main():
    for i, r in enumerate(ROWS):
        pf = (PF_DIR / f"{r['id']}.pf.txt").read_text()
        blockids = ", ".join(f"{b['tag']} {b['id']}" for b in r["pf_blocks"])
        prompt = TMPL.format(
            title=r["title"], etype=r["error_type"], sev=r["severity"],
            desc=r["error_description"], orig=r["author_original"],
            blockids=blockids, note=r["mapping_note"], expansion=r["pf_expansion"], pf=pf,
        )
        (OUT / f"{i:03d}__{r['id']}.txt").write_text(prompt, encoding="utf-8")
    print(f"Wrote {len(ROWS)} cross-check prompts -> {OUT}")


if __name__ == "__main__":
    main()
