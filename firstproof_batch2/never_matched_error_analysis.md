# Error analysis — the 4 blocks still not matched after v1/tm/v2/v3/v4

With every verifier version run (v1 no-web, theorem-vs-original, v2 web+citations,
v3 web+definitions+counterexample, v4 verbatim definition/lemma pinning), 4 of the
35 critical blocks are still not fully matched:

| Block | Best status | What every version did |
|---|---|---|
| 05C · Lemma 5.1 | ✗ no-match | all versions return CORRECT |
| 05C · Proposition 5 | ✗ no-match | all versions return CORRECT |
| 10D · Lemma 1.2 | ★ partial | INCORRECT, but for the wrong reason |
| 10D · Lemma 4.3 | ★ partial | INCORRECT, but for the wrong reason |

They split into two qualitatively different failure modes.

---

## Cluster A — 05C: silent quantifier weakening behind a citation (both 0-pass)

**The defect (reviewers agree across 3 referees).** The proof cites Bounebache–Zambotti
[BZ14] for absolute continuity of the resolvent w.r.t. the invariant measure μ, and
uses it **pointwise / for every initial condition x**. But [BZ14] only establishes it
for **μ-almost-every x**. The uniqueness argument breaks under the correct (a.e.)
version: knowing `R_α(x,A)=0` for μ-a.e. x does not let you conclude the λ-integral
vanishes. (Lemma 5.1 states the overstatement; Proposition 5 is where it is used.)

**What the verifiers did.** v2, v3, **and v4 all return CORRECT on all 3 runs** — they
never flag it. This is the verifier's single hardest failure mode and even verbatim
lemma-pinning (v4) did not crack it.

**Why even v4 missed it.**
1. **The distinction is invisible in the block text.** The PF block presents the cited
   result as a clean statement ("absolute continuity holds"); the quantifier "for μ-a.e.
   x vs for every x" is exactly the word that was dropped, so there is nothing in the
   block that *looks* wrong. The verifier has to independently retrieve [BZ14], read the
   precise proposition, and notice the proof silently strengthened it.
2. **Pinning [BZ14] verbatim apparently failed or was not decisive.** The cited
   proposition is in a specific paper; if the model cannot retrieve its exact statement
   (paywalled / not surfaced by search), v4's exact-name rule has nothing to compare
   against, and the base prompt's gap-filling leniency ("trust a cited result's
   conclusion") then lets it assume the citation says what the proof claims.
3. **The error is a measure-zero subtlety, not a name/existence error** — v4's strengths
   (exact-name definition pinning, undefined-object detection) don't target it. What is
   needed is specifically: *retrieve the cited statement and diff its quantifier against
   the usage*, and treat an a.e.→everywhere upgrade as load-bearing.

**Actionable lever.** A targeted "citation-quantifier diff": for each cited result,
require the verifier to quote the source's exact quantifiers/domain and explicitly
compare ("source says μ-a.e. x; proof uses every x — do these match?"). This is narrower
and more forcing than v4's general hypothesis check, which here got absorbed by the
"trust the cited conclusion" instruction.

---

## Cluster B — 10D: right block, right step, wrong reason (both partial)

Both 10D blocks are flagged INCORRECT by multiple versions, but the judge rates them
**partial** because the verifier's reason is not the reviewer's defect.

### 10D · Lemma 1.2 — false free-product criterion
**Golden defect:** the proper-proximality criterion for `A∗B` "is incorrect without
controlling the atom sizes of A,B" — under the stated dim assumptions `A∗B` can still
have a one-dimensional summand, so the criterion fails.
**What the verifiers said:** v2 attacks the **citation** ("Boutonnet–Ioana–Peterson Thm
4.1 … this citation is not valid / miscited"); v3 and v4 attack an **undefined
"threshold"** the proof invokes. All correctly distrust the same final step, but none
reach the actual mathematical content — the missing atom-size hypothesis and the
1-dimensional-summand counterexample.
**Why:** the verifier found *a* legitimate hole (an unsupported/under-specified citation)
and stopped there; it never did the structural reasoning (construct A,B meeting the
stated hypotheses whose free product has a 1-dim summand) that would surface the
reviewer's specific condition. A counterexample-construction step that must *exhibit*
A,B — not just doubt the citation — would target this.

### 10D · Lemma 4.3 — nonexistent "proper proximal ideal"
**Golden defect:** the proof rests on a **nonexistent / meaningless object** — a
"norm-closed proper proximal ideal" — and a bogus characterization of proper proximality;
the notion did not even exist when the cited paper was written.
**What the verifiers said:** every version flags a *different, real* gap — that
Claim 4.3.2 only gives vanishing on the generators `Xe_D^A Y`, not on the whole
norm-closed ideal `J_prop(A)` they generate ("ψ completely vanishes on all of J_prop(A)"
is unjustified). Correct as a gap, but not the golden defect.
**Why v4 specifically missed it — a PF artifact.** v4's definition-pinning **pinned
`J_prop(A)` to the inline definition the PF supplies** ("the norm-closed ideal in
B(L²A) generated by operators `Xe_D^A Y`"). Because the object is *locally defined in
the proof*, v4's exact-name rule is satisfied (branch (a): "defined in the proof") and
never fires — even though the *named concept* "proper proximal ideal" is exactly the
nonexistent notion the reviewer objects to. The pseudo-formalisation, by rewriting the
bogus object into a self-contained inline definition, **masked the existence error** and
redirected the verifier to a secondary technical gap.

**Actionable lever.** STEP 1 should not stop at "is it defined in the proof?": when the
proof attaches a **named** notion to an inline definition AND treats it as an established
concept (or cites external support for it), the verifier must also check that the *name*
denotes a real notion in the literature consistent with that definition. A locally
coined definition for a named object that does not exist should itself be a red flag.

---

## Summary of root causes

1. **05C (×2, 0-pass):** silent quantifier weakening (a.e.→everywhere) behind a real
   citation the verifier can't pin precisely; absorbed by "trust the cited conclusion."
   → needs explicit citation-quantifier diffing.
2. **10D Lemma 1.2 (partial):** verifier settles for a citation/under-specification
   complaint instead of constructing the counterexample that reveals the missing
   atom-size hypothesis. → needs forced counterexample *construction*.
3. **10D Lemma 4.3 (partial):** the PF rewrote a nonexistent named object into a
   self-contained inline definition, so v4's "defined in the proof" branch accepted it
   and the existence error was masked. → needs name-vs-literature checking even for
   locally-defined named notions.

Two of three residual failures (the 10D pair) are reachable with concrete prompt levers;
the 05C pair is the genuine hard ceiling — a measure-theoretic subtlety hidden behind a
citation, where the only fix is to actually obtain and read the cited statement.
