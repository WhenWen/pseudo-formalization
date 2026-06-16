# Unmatched / partially-matched blocks (all verifiers, after misattribution fix)

Match status is across **all** verifiers and runs: standard block verifier v1
(N=3) + theorem-vs-original matching verifier (theorem blocks, N=3) + web-search
verifier v2 (N=3) + v3 (web + definitions + counterexample, N=3). A block
"matches" if any run of any verifier identifies the reviewer's actual error.
Symbols: ✓ agree · ★ partial · ✗ disagree.

## Misattribution fix (this pass)

A Codex audit over the no-match blocks read the **full proof decomposition with
DEPS** (not just the ancestor chain) and found that several blamed blocks are
**correct on their own** — they merely invoke a dependency/parent/sibling block
where the real flaw lives. The critical attribution was moved and the true blocks
re-verified with v1/v2/v3 (N=3):

| Proof | Was (deepest) | → True error block | Now matched? |
|---|---|---|---|
| 03C | Claim 3.2.1 | **Proposition 1** (the Hoeffding–Pinelis lemma is Prop 1's own asserted theorem) | ✓ (v2, v3) |
| 04C | Proposition 2 | **Proposition 1** (Prop 2 only packages lemmas; the unsupported Guth citation is in Prop 1) | ✓ (v2, v3) |
| 05C | Lemma 6.1 | **Proposition 5** (Lemma 6.1 follows validly from Prop 5) | ✗ still missed |
| 05D | Proposition 4 | **Lemma 4.5** (the false uniqueness criterion) | ✓ |
| 05D | Proposition 4 | **Lemma 4.2** (heuristic topological irreducibility) | ✓ |
| 08C | Claim 4.3.1 | **Claim 4.1.2** (the unjustified flag-incidence reversal) | ✓ |
| 09D | Proposition 3 | **Proposition 6** (undefined superspace-evaluation step) | ✗ still missed |

Five no-match blocks were confirmed correctly attributed and left in place
(05C Lemma 5.1, 08A Lemma 4.1, 09D Proposition 4, 10D Lemma 1.2, 10D Lemma 4.3).

**Block-level totals (35 critical blocks):** ✓ matched ≥1 run **27** · ★ partial only **3** · ✗ 0-pass **5**
(was 24 / 4 / 9 before the fix).
**Proof-level:** ✓ **16** · ★ **1** (10D) · ✗ **2** (05C, 08A).

---

## ✗ 0-pass blocks — never matched in any run (5)

### Resolvent absolute-continuity / citation subtlety (05C, 2 blocks)
1. **05C · Lemma 5.1** [false_claim] — Resolvent absolute continuity overstated from μ-a.e. to every initial condition.
   - Reviewer: "incorrectly cites a result … claiming absolute continuity … everywhere."
2. **05C · Proposition 5** [incorrect_step] — *(reattributed from Lemma 6.1)* upgrades the cited resolvent result from μ-a.e. x to every x.
   - Reviewer: "a wrong statement due to an incorrect citation. The result holds for almost every x."
   - v1 ✗✗✗ · v2 ✗✗✗ · v3 ✗✗✗ — the measure-theoretic "a.e. vs everywhere" gap none of the versions land.

### Non-citation math / construction gaps (3)
3. **08A · Lemma 4.1** [unjustified_gap] — Unproved relative valuated Higgs completion ("never been proved that it defines a completion for general matroids").
4. **09D · Proposition 4** [unjustified_gap] — Identifies an evaluated coinvariant algebra with the super-coinvariant algebra ("flat-out nonsensical, like evaluating a coinvariant algebra at a superspace").
5. **09D · Proposition 6** [unjustified_gap] — *(reattributed from Proposition 3)* undefined superspace evaluation used to isolate hook coefficients ("What does it mean to evaluate a GL_m character at a superspace?").

---

## ★ Partial-only blocks — flagged a problem, but never the exact reviewer error (3)

1. **04D · Lemma 3.1** [incorrect_step] — Asserted inequalities are false by a scaling argument (problem is scale-invariant).
   - v1 ★★★ · v2 ★★★ — consistently suspicious, never lands the scaling reason.
2. **10D · Lemma 1.2** [false_claim] — False free-product criterion for the base cases ("incorrect without controlling the atom sizes of A,B").
   - v1 ✗✗✗ · v2 ★★★ · v3 ★★★ — web/v3 question the criterion, miss the exact atom-size condition.
3. **10D · Lemma 4.3** [incorrect_step] — Wrong characterization of proper proximality via a nonexistent ideal ("'norm-closed proper proximal ideal' is not an existing notation").
   - v1 ★★★ · v2 ✗★★ · v3 ★★★ — recognizes something is wrong, doesn't nail the nonexistent object.

---

## Takeaway
After fixing misattribution, the verifier's residual ceiling is 8 not-fully-matched
blocks (5 zero-pass + 3 partial). The 05C pair is a citation/measure-theory
subtlety (a.e. vs everywhere); the rest are genuine non-citation defects
(false scale-invariant inequalities, undefined/nonsensical constructions,
unproved completions) — failures web search cannot lift.
