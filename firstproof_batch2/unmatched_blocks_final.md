# Unmatched / partially-matched blocks (all verifiers)

Match status is taken across **all** verifiers and runs: standard block verifier
(N=3) + theorem-vs-original matching verifier (theorem blocks, N=3) + web-search
verifier (N=3). A block "matches" if any run of any verifier identifies the
reviewer's actual error.

**Block-level totals (35 critical blocks):** ✓ matched ≥1 run **22** · ★ partial only **4** · ✗ 0-pass **9**.

---

## ✗ 0-pass blocks — never matched in any run (9)

### Citation-related that web search still missed (3)
1. **03C · Claim 3.2.1** [unjustified_gap] — Unproved Hoeffding–Pinelis comparison lemma
   - Reviewer: "The citations provided do not imply the stated lemma."
2. **05C · Lemma 5.1** [false_claim] — Resolvent absolute continuity overstated from μ-a.e. to every initial condition
   - Reviewer: "incorrectly cites a result … claiming absolute continuity … everywhere."
3. **05C · Lemma 6.1** [incorrect_step] — Uses the unavailable pointwise resolvent statement
   - Reviewer: "a wrong statement due to an incorrect citation. The result holds for almost every x."

### Downstream of a caught root (1)
4. **04C · Proposition 2** [unjustified_gap] — Final proof only invokes the unsupported quoted theorem
   - (Root cause 04C Prop 1 — the hallucinated Guth citation — *was* caught by web search.)

### Non-citation math / construction gaps (5)
5. **05D · Proposition 4** [unjustified_gap] — Topological irreducibility asserted heuristically from additive noise
6. **08A · Lemma 4.1** [unjustified_gap] — Unproved relative valuated Higgs completion
7. **08C · Claim 4.3.1** [unjustified_gap] — Unjustified reversal of quotient/flag incidence
8. **09D · Proposition 3** [unjustified_gap] — Undefined superspace evaluation (isolating hook coefficients)
9. **09D · Proposition 4** [unjustified_gap] — Identifies an evaluated coinvariant algebra with the super-coinvariant algebra

---

## ★ Partial-only blocks — flagged a problem, but never the exact reviewer error (4)

1. **04D · Lemma 2.1** [false_claim] — Asserted foundational volume inequalities are false
   - Reviewer: false "by a scaling argument" (problem is scale-invariant).
   - Runs: standard ★★★ · web ★★★ — consistently suspicious, never lands the scaling reason.
2. **08D · Lemma 5.2** [false_claim] — False dismissal of elementary/continuous lifts containing the boundary point
   - Runs: standard ✗✗✗ · web ✗✗★ — mostly missed; one web run partial.
3. **10D · Lemma 1.2** [false_claim] — False free-product criterion for the base cases
   - Reviewer: "incorrect without controlling the atom sizes of A,B."
   - Runs: standard ✗✗✗ · web ★★★ — web search near-catch (questions the BIP citation, misses the exact condition).
4. **10D · Lemma 4.3** [incorrect_step] — Wrong characterization of proper proximality via a nonexistent ideal
   - Reviewer: "'norm-closed proper proximal ideal' is not an existing notation."
   - Runs: standard ★★★ · web ✗★★ — recognizes something is wrong, doesn't nail the nonexistent object.

---

## Takeaway
Of the 13 not-fully-matched blocks (9 zero-pass + 4 partial): ~5 are citation-related
(03C 3.2.1, 05C ×2, 04C Prop 2 downstream, 10D 1.2) and the rest are genuine
non-citation mathematical defects (false inequalities, nonsensical constructions,
undefined objects) — the verifier's real ceiling, which web search cannot lift.
