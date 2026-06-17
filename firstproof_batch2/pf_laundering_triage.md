# PF faithfulness — whole-proof coverage sweep + laundering triage

Method: for each proof, GPT-5.5 compared the **full raw author proof** against the
**full reassembled PF** (a whole-proof *coverage* check, which — unlike per-block
faithfulness — catches content dropped *between* blocks). A second GPT-5.5 pass then
judged whether any divergence is **tied to the reviewer's actual error** ("laundering":
the PF dropped/softened the very thing the referee objected to, so a blind PF-only
verifier is less able to detect it) vs benign (title/bibliography/relabelling).

`verif` = does any verifier version (v1/tm/v2/v3/v4) match the reviewer on this proof:
✓ matched · ★ partial · ✗ missed.

| proof | coverage | laundering tied to error | verif | finding |
|---|---|---|---|---|
| 01D | diverges | no | ✓ | — |
| 02D | diverges | **yes** | ✓ | dropped caveats/gap-assessment; recast heuristic steps as assertive lemmas |
| 03B | diverges | no | ✓ | — |
| 03C | diverges | no | ✓ | — |
| 03D | diverges | **yes** | ✓ | sanitised the author's "Partial Solution"/necessity-gap framing |
| 04A | diverges | no | ✓ | — |
| 04B | diverges | no | ✓ | — |
| 04C | diverges | no | ✓ | — |
| 04D | diverges | no | ✓ | — |
| 05B | diverges | **yes** | ✓ | dropped admissions that ABLM gives only conditional uniqueness |
| **05C** | diverges | **yes** | **✗** | **dropped the "pointwise absolute continuity" remark (the exact overstated property)** |
| 05D | diverges | **yes** | ✓ | removed editor warning; recast heuristic irreducibility + invalid uniqueness as lemmas |
| 06D | diverges | **yes** | ✓ | softened the unquantified "heavily exceeds" overclaim |
| 08A | **faithful** | no | ✓ | — |
| 08C | diverges | maybe | ✓ | dropped the set-level p⊥ formula / lattice-duality citations |
| 08D | diverges | **yes** | ✓ | softened the false "all rank-2 quotients exhausted" claim |
| 09D | diverges | **yes** | ✓ | turned undefined "OSP combinatorial basis" into an asserted basis theorem |
| 10B | diverges | **yes** | ✓ | dropped the problem statement + "proves only a conditional lemma" disclaimer |
| **10D** | diverges | **yes** | ✓* | **dropped the "norm-closed proper proximal ideal" definition** |

\*10D was ★ partial until the PF was re-done; after re-PF + re-verify it is ✓.

## Counts
- Coverage: **18/19 diverge**, 1 faithful (08A). (Most divergences are benign.)
- Laundering tied to the reviewer's error: **10 yes**, 1 maybe (08C), 8 no.

## The systematic laundering mode
The dominant pattern across the 10 flagged proofs is the same: **the PF strips the
author's own hedges and recasts asserted/heuristic claims as formal results.** Concretely
it drops "Partial Solution" headers, editor/caveat warnings, "this is only heuristic"
admissions, and unquantified hand-waving ("heavily exceeds"), and re-packages them as
clean `LEMMA`/`PROPOSITION` statements with citations. This makes a flawed proof look
**more rigorous than the author presented it** — which (a) can suppress error detection
and (b) inflates apparent proof quality. It is the same failure that hid 10D's nonexistent
ideal and 05C's overstated resolvent.

## Priority
- **High (laundering + detection failed):** only **05C** (✗) — and **10D** (was ★). Both
  validated as fixable by re-PF: re-PF'd 10D → v4 matches both blocks; re-PF'd 05C now
  passes the coverage check as faithful (re-verification pending).
- **Lower (laundering but still matched):** 02D, 03D, 05B, 05D, 06D, 08D, 09D, 10B (+08C
  maybe). The verifier caught these despite the laundering, but the PF still overstates
  the proof's rigor — a benchmark-integrity issue worth re-PF'ing for data quality.
- **Clean wrt the error:** 01D, 03B, 03C, 04A, 04B, 04C, 04D, 08A.

Artifacts: `faithcheck/coverage/<sid>.txt` (reports), `faithcheck/triage/<sid>.json`
(per-proof laundering verdicts), `run_coverage_check.py`, `run_laundering_triage.py`.
