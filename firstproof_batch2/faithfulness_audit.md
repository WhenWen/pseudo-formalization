# PF Faithfulness Audit — fatal-error proofs

One subagent per proof compared `pf_clean_proofs/<id>.tex` (clean original) against
`pf_outputs/<id>.pf.txt` (PF rewrite), checking for rewriter artifacts and — most
importantly — whether the known fatal error was silently repaired.

## Summary

- **19/19 fatal errors PRESERVED** (none silently fixed/hidden).
- Verdicts: **7 FAITHFUL, 12 MINOR_ARTIFACTS, 0 SERIOUS_MISMATCH**.
- NOTE: `<DEPS id="theorem_N">` is spec-compliant (the PF prompt mandates this
  naming for theorem-proof DEPS). Agents flagged it as an inconsistency in most
  proofs — those are FALSE POSITIVES and should be ignored.

| id | verdict | fatal preserved | notable genuine mismatch |
|----|---------|-----------------|--------------------------|
| 01D | FAITHFUL | yes | — |
| 02D | MINOR_ARTIFACTS | yes | tidy-up of an equivalent inequality chain (3.2) |
| 03B | FAITHFUL | yes | — |
| 03C | MINOR_ARTIFACTS | yes | trivial added one-liner (7.2) |
| 03D | MINOR_ARTIFACTS | yes | proof body softens necessity to "not established" (stmt still asserts iff) |
| 04A | MINOR_ARTIFACTS | yes | added optimization algebra (4.2.2, 4.5); EAT still an assumption |
| 04B | FAITHFUL | yes | — |
| 04C | MINOR_ARTIFACTS | yes | synthesized Prop 2; lemma split |
| 04D | FAITHFUL | yes | — |
| 05B | MINOR_ARTIFACTS | yes | **dropped 2 examples (ex:nullmod) + "what is missing"/"final conclusion" prose** |
| 05C | FAITHFUL | yes | cross-subtree DEPS reach (5.2→4.1.2) |
| 05D | FAITHFUL | yes | mild: 4.3 promotes "reversible wrt μ" to a premise |
| 06D | MINOR_ARTIFACTS | yes | added structural one-liner (3.1); cross-subtree DEPS (5.3.2→4.2) |
| 08A | FAITHFUL | yes | benign relocated justification (2.2) |
| 08C | MINOR_ARTIFACTS | yes | gappy duality claims repackaged as citation-backed claims; mild added line (1.1) |
| 08D | MINOR_ARTIFACTS | yes | implicit "forced cardinality c" made explicit (Prop 3) |
| 09D | MINOR_ARTIFACTS | yes | **added connective justification over the fatal step (Lemma 3.3 / Prop 3 proof)** |
| 10B | MINOR_ARTIFACTS | yes | **dropped the "this is a different/relaxed result" disclaimer**; trivial added algebra (1.2) |
| 10D | FAITHFUL | yes | explicit numeric criterion not restated (reasoning retained) |

## Top items to review
1. **09D** — rewriter manufactured connective reasoning ("Thus the copies are counted by…")
   that partially papers over the fatal ill-defined count. Verify the PF leaf still
   exposes the gap.
2. **05B** — dropped the examples and "what is missing" / "final conclusion" sections,
   which are where the original openly admits the uniqueness gap.
3. **10B** — PF presents the abstract relaxed lemma as the theorem with no flag that it
   is NOT the requested graph-product theorem.

All other findings are cosmetic (trivial added one-liners, hoisted/synthesized blocks,
trivial restating decompositions, cross-subtree DEPS reaches mirroring the original's own
back-references) and preserve the mathematics.
