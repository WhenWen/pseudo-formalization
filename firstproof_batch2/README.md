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
7. **Block verification (versioned ladder)** — all BLIND (reviewer text never sent),
   gpt-5.5/high, N=3 pessimistic, on the critical block per error:
   - **v1** `run_block_verifier.py` — component verifier, no web → `block_verify_results.json`
   - **tm** `run_theorem_verifier.py` — theorem checked vs the ORIGINAL problem (scope
     errors) → `theorem_verify_results.json`
   - **v2** `run_websearch_verifier.py` — + web search & citation fact-check (First Proof
     domains blocked) → `websearch_verify_results.json`
   - **v3** `run_bv_v3.py` — + definition-pinning & counterexample search → `bv_v3_results.json`
   - **v4** `run_bv_v4.py` — + *verbatim* definition/lemma pinning, exact-name rule →
     `bv_v4_results.json` (`v4_prompt_full.md`)
8. **Misattribution fix** — Codex audit over no-match blocks reads the full PF with DEPS
   and reassigns each error from the deepest cited block to the block whose OWN
   statement/proof holds the flaw (often a cross-dependency): `build_misattr_prompts.py`
   → `merge_misattr.py`.
9. **PF-laundering audit + re-PF** — whole-proof coverage check (`run_coverage_check.py`)
   finds PF rewrites that dropped the author's own hedges/definitions and so hid the
   referee's defect (`pf_laundering_triage.md`); **10D** and **05C** were re-PF'd
   (`pf_outputs_prerepf_gpt/` keeps the originals) and re-verified.
10. **Judged vs referees** — `judge_verdicts.py` / `judge_runs.py` /
   `judge_websearch_runs.py` adjudicate each verifier output against the verbatim referee
   quote (✓ agree · ★ partial · ✗ disagree). A block "matches" if any run of any version
   agrees; a proof matches if any of its critical blocks matches.

## Final judged results
Verifier ladder + misattribution fix + re-PF, judged against the referee quotes:

- **Standard judge, full batch (19 proofs, 35 critical blocks):** **34/35 blocks** and
  **19/19 proofs** matched; the only unmatched block is 05C Proposition 7 (a downstream
  λ≪μ step). Biggest gains: **v2** (web/citations, +9 blocks over v1) and **v4** (verbatim
  pinning); the theorem-matching verifier catches all 5 theorem-level scope errors; v3
  adds scaling/definition cases. See `unmatched_blocks_final.md`, `missed_blocks_analysis.md`.
- **Tightened judge** — "agree" requires the verifier to name the *concrete essence* of
  the referee's defect (reason-presentation + citation-vs-content + epistemic-access rules;
  `judge_prompt.md`) — evaluated on the **leaner set** of 11 proofs whose text does NOT
  self-admit incompleteness (`leaner_set.json`, `run_incompleteness_scan.py`):
  **12 match / 5 partial / 1 miss** blocks and **10/11 proofs** (only 08A demoted).
  Per-block flips: `judge_tightening_flips.md`; numbers: `leaner_tallies.json`. (The
  tightened re-judge was applied to the leaner-subset matched blocks, so a fresh
  full-batch recompute is a hybrid: 29 match / 5 partial / 1 miss blocks, 18/19 proofs.)

Cross-cutting findings: the deepest-block heuristic misattributes ~1/3 of errors to an
innocent invoking block; the PF rewrite systematically launders author hedges (dropped
"Partial Solution" notes, sanitized nonexistent objects), which both suppresses detection
and inflates apparent rigor; gluing/assembly steps are the verifier's hardest class
(missed the real gap in P8, false-flagged a correct P7 cobordism). PF faithfulness was
also audited per proof (`faithfulness_audit.md`): all 19 fatal errors preserved, none
silently repaired.

## Serving the HTML
`python serve_nocache.py 41665` serves this dir with no-cache headers. `pf_tree.html`
(full, 19 proofs) and `pf_tree_lean.html` (leaner 11-proof set) are fully self-contained
(no network needed to render).
