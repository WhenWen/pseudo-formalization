# First Proof × Pseudo-Formalization — block verification study

1. **What we built** (repo: `WhenWen/pseudo-formalization`, branch `firstproof-pf-error-mapping`, dir `firstproof_batch2/`)
   1. Pulled the First Proof Batch-2 AI solutions + referee reviews; mapped **43 referee errors** across the **19 fatal-error proofs** to concrete blocks.
   2. Pseudo-formalized all 19 proofs via Codex (Theorem → Prop → Lemma → Claim → Fact).
   3. Mapped each error to its PF block, pairing the **verbatim reviewer comment** with the **GPT/PF expansion** (+ a GPT-5.5 judge of whether the verifier's verdict matches the reviewer).
   4. Self-contained, interactive HTML report (proof tree, two-level outline, error propagation, per-run match symbols).

2. **Block-verification results** (blind, GPT-5.5, N=3, pessimistic)
   1. Standard verifier catches the referee's actual error in **8/19 proofs** (any run, any block).
   2. Adding the **theorem-vs-original "matching" verifier** (checks the proof against the **original problem**, not the submission's own restated theorem) → **12/19** (★3, ✗4).
      1. The matching verifier flags **5/5** theorem-level "conditional / different-statement" scope errors that the standard verifier misses entirely.

3. **PF-hygiene finding** (the big one)
   1. Codex audit found **80 malformed PF blocks**; **15/37 (41%) of verified blocks were malformed**.
   2. Malformed blocks (proof text hoisted into the statement) were **masking** real errors: after fixing, **08C, 04D, 03D, 09D** flipped CORRECT → INCORRECT.
   3. 10 proofs were fixable in-place; **6 required a full re-PF** (impossible to fix locally).
   4. Also: the "deepest cited block" heuristic mislocalized **13/43** errors — the real flaw is usually a synthesis step in a parent block, not the (correct) sub-lemma.

4. **Takeaways**
   1. Block verification's gap-filling leniency makes it miss most `incomplete`/`unjustified_gap` errors even when correctly localized.
   2. Theorem-level scope errors need the original problem statement — they're invisible otherwise.
   3. PF output hygiene is a real confound and must be checked/repaired before trusting verification numbers.

5. **Links**
   1. Live report (Stanford net): http://tiger6.stanford.edu:41665/pf_tree.html
   2. Fork/branch: https://github.com/WhenWen/pseudo-formalization/tree/firstproof-pf-error-mapping/firstproof_batch2
