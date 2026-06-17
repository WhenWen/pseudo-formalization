# The 8 not-fully-matched blocks — detail + analysis

After the misattribution fix, 8 of the 35 critical blocks are still not fully
matched by any verifier: **5 zero-pass** (never agree) and **3 partial-only**
(flag a problem, never the reviewer's exact defect). Run symbols are per N=3 run:
✓ agree · ★ partial · ✗ disagree · — not run. Verifiers: v1 (no web) · v2 (web +
citation fact-check) · v3 (web + definition-pinning + counterexample).

| # | Block | Type | v1 | v2 | v3 | Status |
|---|---|---|---|---|---|---|
| 1 | 05C · Lemma 5.1 | false_claim | ✗✗✗ | ✗✗✗ | ✗✗✗ | 0-pass |
| 2 | 05C · Proposition 5 | incorrect_step | ✗✗✗ | ✗✗✗ | ✗✗✗ | 0-pass |
| 3 | 08A · Lemma 4.1 | unjustified_gap | ✗✗✗ | ✗✗✗ | ✗✗✗ | 0-pass |
| 4 | 09D · Proposition 4 | unjustified_gap | ✗✗✗ | ✗✗✗ | ✗✗✗ | 0-pass |
| 5 | 09D · Proposition 6 | unjustified_gap | ✗✗✗ | ✗✗✗ | ✗✗✗ | 0-pass |
| 6 | 04D · Lemma 3.1 | incorrect_step | ★★★ | ★★★ | — | partial |
| 7 | 10D · Lemma 1.2 | false_claim | ✗✗✗ | ★★★ | ★★★ | partial |
| 8 | 10D · Lemma 4.3 | incorrect_step | ★★★ | ✗★★ | ★★★ | partial |

---

## Block detail

### 1. 05C · Lemma 5.1 — resolvent absolute continuity overstated
Reviewer: *"the AI incorrectly cites a result concerning the resolvent, claiming
absolute continuity with respect to μ … everywhere."* The cited Bounebache–Zambotti
result gives absolute continuity only for **μ-a.e.** initial point; the lemma asserts
it for **every** initial condition.

### 2. 05C · Proposition 5 — uses the unavailable pointwise resolvent statement
*(Reattributed from Lemma 6.1, which follows validly from Prop 5.)* Reviewer:
*"a wrong statement due to an incorrect citation. The result holds for almost every x."*
Prop 5 upgrades the same μ-a.e. resolvent fact to every x and then runs the
λ-integral argument on it.

### 3. 08A · Lemma 4.1 — unproved relative valuated Higgs completion
Reviewer: *"it has never been proved that it defines a completion for general
matroids M."* The lemma asserts, by citation only, that the minimization-defined
functions hⱼ are valuated matroids with hⱼ ⪯ hⱼ₊₁ — a construction not established
in the cited sources or in the submission.

### 4. 09D · Proposition 4 — evaluating a coinvariant algebra at a superspace
Reviewer: *"Some of the statements are wrong, and some flat-out nonsensical, like
evaluating a coinvariant algebra at a superspace."* Prop 4 introduces an undefined
"evaluation at E = ℂ^{1|1}" with no defined functor/substitution.

### 5. 09D · Proposition 6 — undefined superspace evaluation to isolate hook coefficients
*(Reattributed from Proposition 3.)* Reviewer: *"What does it mean to evaluate a
GLₘ character at a superspace? They might be trying to get a plethysm here…"* Prop 6
treats the ordinary GLₘ Schur expansion as evaluable at the superspace and claims the
surviving hook terms recover individual coefficients — passage never defined.

### 6. 04D · Lemma 3.1 — false inequalities (partial)
Reviewer: *"Inequalities (1) and (2) are false. This can be seen by a scaling
argument. The problem is invariant under scaling."* All runs flag the inequality as
suspicious/under-justified, but none produce the scale-invariance refutation.

### 7. 10D · Lemma 1.2 — free-product criterion missing atom-size control (partial)
Reviewer: *"the statement is incorrect without controlling the atom sizes of A,B."*
v2/v3 question the proper-proximality threshold criterion (good direction) but never
isolate the missing atom-size condition.

### 8. 10D · Lemma 4.3 — nonexistent "norm-closed proper proximal ideal" (partial)
Reviewer: *"'norm-closed proper proximal ideal' is not an existing notation, and the
definition doesn't make sense."* Verifiers sense the object is ill-formed but never
state flatly that the ideal does not exist / is undefined.

---

## Analysis — why these survive

**A. Quantifier-weakening behind a real citation (05C ×2).** The hardest class. The
cited theorem genuinely exists and is genuinely close; the proof silently strengthens
"for μ-a.e. x" to "for every x." Web search *confirms the citation exists* and the
verifier then accepts it — fact-checking existence is the wrong instrument for a
**quantifier/measure-zero gap**. Catching this needs the verifier to retrieve the
cited statement's **exact hypotheses and conclusion** and diff them against the usage,
not just confirm the reference is real. This is the clearest place a v4 ("quote the
cited theorem verbatim, then check the quantifiers line up") would help.

**B. Undefined objects in a narrow subfield (08A, 09D ×2).** The flawed step invents
or misuses an object ("relative valuated Higgs completion", "evaluate a coinvariant
algebra / GLₘ character at a superspace") that has no standard definition. v3's
definition-pinning step is designed for exactly this, yet it still returns CORRECT —
because the surrounding prose is fluent and plausible, the model **charitably supplies
a meaning** instead of declaring the object undefined. The reviewer's confidence
("flat-out nonsensical") comes from domain expertise the model lacks; web search finds
*related* legitimate notions and the model assumes the proof means one of those. The
failure mode is **charitable interpretation**, not missing information — v3 would need
a much stricter "if you cannot find this exact object defined in the literature, return
INCORRECT and name it" stance, applied without the escape hatch of a nearby concept.

**C. False elementary claim refutable by a structural argument (04D, partial).** The
inequality is false by scale-invariance — a one-line refutation a human sees
immediately. The verifier flags it as under-justified (hence ★) but never runs the
scaling/dimensional-analysis check that would turn suspicion into a counterexample.
v3's counterexample step fires on small numeric instances but does not try
**symmetry/scaling** refutations; that is a tractable upgrade.

**D. Missing side condition / ill-formed definition (10D ×2, partial).** The verifier
correctly smells trouble (★ across web runs) but stops short of the precise defect: the
exact missing hypothesis (atom sizes of A, B) or the categorical claim that the named
object does not exist. These are "almost there" — the reasoning is in the right region
but lacks the final commitment, often because the verifier hedges rather than asserting
the strong negative the reviewer states.

### Cross-cutting takeaway
Only **2 of 8** (05C pair) are citation-driven, and even those are *quantifier* gaps
behind real references — not the hallucinated-citation case web search already solves.
The remaining 6 are the verifier's genuine ceiling: **charitable interpretation of
undefined objects** and **hedging instead of committing to a strong refutation**.
Two concrete, non-speculative levers:
1. **Verbatim-citation diffing** — retrieve and quote the cited theorem, then check
   hypotheses/quantifiers match the usage (targets A).
2. **Adversarial definition stance + structural counterexamples** — force INCORRECT
   when an object cannot be pinned to a literature definition, and add
   symmetry/scaling refutations to the counterexample step (targets B, C, D).
