# First Proof (Batch 2) — error localization, pseudo-formalization & block verification

Pipeline built on top of the *First Proof Second Batch* AI-solution + referee-review
corpus (github.com/1stproof/batch-2). Clone that repo into `batch-2/` (gitignored,
~1.2 GB) to regenerate from scratch.

## Stages
1. **`parse_corpus.py`** → `corpus.json` — clean proof text per submission + each
   review split into summary / recommendation / inline `\review{}` comments.
2. **`map_errors.py`** → `errors.json` — gpt-5.5 maps referee findings to verbatim
   errored blocks + a paragraph each (40 submissions, 56 errored blocks, 22 flawed).
3. **`make_report.py`** → `report.html` — error map vs referee editorial decisions.
4. **PF rewrite** (Codex CLI) — `prep_pf.py` selects the 19 fatal-error proofs →
   `pf_clean_proofs/`, `pf_prompts/`; `pf_run.sh` runs `codex exec` →
   `pf_outputs/<id>.pf.txt`. `prep_pf_strict.py` re-runs 05B/09D/10B with a strict
   add-nothing/drop-nothing prompt (`pf_outputs_strict/`, promoted; v1 in
   `pf_outputs_v1/`).
5. **Review → PF-block map** — `map_review_to_pf.py` → `pf_review_map.json`
   (each error's author text paired with its PF "expansion" block); Codex
   cross-check via `build_xcheck_prompts.py` + `codex_xcheck.sh` →
   `merge_xcheck.py` → `pf_review_map_checked.json`. Reviewer quotes added by
   `extract_reviewer_quotes.py`.
6. **`make_pf_tree_report.py`** → `pf_tree.html` — interactive proof tree with
   mapped errors + verbatim reviewer quotes (self-contained: MathJax inlined via
   `mathjax_inline.py` + `assets/tex-svg.js`).
7. **Block verification** — `run_block_verifier.py` runs the codebase's
   component verifier (gpt-5.5, high, 16K, N=1) BLIND (no reviewer text) on the
   ancestor-collapsed deepest block per error (36 blocks) → `block_verify_results.json`.

## Headline result
Blind block verification on the 36 known-wrong deepest blocks caught **11/36 (31%)**
as INCORRECT and missed 25 — most missed errors are `incomplete` / `unjustified_gap`
(the verifier's gap-filling leniency). Faithfulness of the PF rewrites was audited
(see `faithfulness_audit.md`): all 19 fatal errors preserved, none silently repaired.

## Serving the HTML
`python serve_nocache.py 41665` serves this dir with no-cache headers. The HTML
reports are fully self-contained (no network needed to render).
