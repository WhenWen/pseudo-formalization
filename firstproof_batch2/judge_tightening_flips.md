# Tightened judge — re-judge of the leaner subset (flips)

The automatic judge (`judge_verdicts.py`, see `judge_prompt.md`) was tightened so that
**"agree" (matched) requires the verifier to present the *concrete essence* of the
reviewer's defect**, not merely flag the right block. Four layers:

1. **Concrete essence** — right block + vague/generic reason ("unjustified", "needs
   proof") = *partial*, not agree.
2. **Reason-presentation** — if the reviewer gives a concrete reason (the specific
   failing hypothesis, or why a claim is provably wrong), agree only if the verifier
   presents *that* reason.
3. **Citation-vs-content** — a citation/existence complaint ("not in the cited source")
   does not match a reviewer reason that specific mathematical content is unproved/false.
4. **Epistemic-access** — if the verifier's stated basis is its own inability to
   retrieve / pin / verify a citation or named construction ("not found", "UNPINNED",
   "cannot perform the audit"), that is *partial* vs a substantive "unproved/false"
   reviewer reason — even if the verifier names the relevant objects.

Re-judged the **32 matched entries of the 11 leaner-subset proofs** (only those; the
full report still mixes tightened leaner + old non-leaner judging).

## Validation case
**08A Lemma 4.1 (v4): agree×3 → partial×3.** v4's entire basis was that the cited
constructions ("Murota truncation theorem", "Dress–Terhalle well-layering") could not be
pinned under their exact names — a citation-access failure — whereas the reviewer's point
is substantive: the submission never proves the `h_j` are valuated matroids satisfying the
adjacent quotient relations / valuated Plücker relations.

## Per-version entry flips (was agree-containing → no longer)

| version | block | old | new |
|---|---|---|---|
| v1 | 04C Proposition 1 | ✓✓✓ | ★★★ |
| v1 | 08C Claim 4.1.1 | ✗★✓ | ✗★★ |
| v1 | 08D Lemma 5.1 | ✗★✓ | ✗★★ |
| v2 | 03B Lemma 1.1 | ✓✓✓ | ★★★ |
| v2 | 08C Claim 4.1.1 | ✓★★ | ★★★ |
| v3 | 04C Proposition 1 | ✓★★ | ★★★ |
| v3 | 08D Lemma 5.2 | ✓★✓ | ★★★ |
| v4 | 03B Lemma 1.1 | ✓✓★ | ★★★ |
| v4 | 08A Lemma 4.1 | ✓✓✓ | ★★★ |
| v4 | 08D Lemma 5.1 | ✓★★ | ★★★ |
| v4 | 08D Lemma 5.2 | ✓★✓ | ★★★ |

(✓ agree · ★ partial · ✗ disagree, per N=3 run)

## Block-level flips (critical block, across all versions)

| block | before | after |
|---|---|---|
| 03B Lemma 1.1 | match | **partial** |
| 08A Lemma 4.1 | match | **partial** |
| 08C Claim 4.1.1 | match | **partial** |
| 08D Lemma 5.1 | match | **partial** |
| 08D Lemma 5.2 | match | **partial** |

Note: **04C Proposition 1** did NOT flip at block level — v1 and v3 demoted to partial,
but v2 and v4 still agree, so the block stays matched.

## Leaner-set tallies (before → after tightening)

| level | before | after (tightened) |
|---|---|---|
| block | 17 match / 1 miss | **12 match / 5 partial / 1 miss** |
| proof | 11 match | **10 match / 1 partial** |

Only proof **08A** lost its match (its sole critical block, Lemma 4.1, demoted). **08D**
stays matched via Proposition 5; the still-missed block is **05C Proposition 7** (the
downstream λ≪μ block).

Standalone matched/covered on the leaner set after tightening:
v1, v2, v3, v4, tm — see `leaner_tallies.json`.

---

# Per-block × per-version detail

✓ agree · ★ partial · ✗ disagree (one symbol per N=3 run).


## Lost match — all matching versions flipped (5)


### 03B LEMMA 1.1  (match → partial)

| ver | old | new | |
|---|---|---|---|
| v2 | ✓✓✓ | ★★★ | **flipped** |
| v4 | ✓✓★ | ★★★ | **flipped** |

### 08A LEMMA 4.1  (match → partial)

| ver | old | new | |
|---|---|---|---|
| v4 | ✓✓✓ | ★★★ | **flipped** |

### 08C CLAIM 4.1.1  (match → partial)

| ver | old | new | |
|---|---|---|---|
| v1 | ✗★✓ | ✗★★ | **flipped** |
| v2 | ✓★★ | ★★★ | **flipped** |

### 08D LEMMA 5.1  (match → partial)

| ver | old | new | |
|---|---|---|---|
| v1 | ✗★✓ | ✗★★ | **flipped** |
| v4 | ✓★★ | ★★★ | **flipped** |

### 08D LEMMA 5.2  (match → partial)

| ver | old | new | |
|---|---|---|---|
| v3 | ✓★✓ | ★★★ | **flipped** |
| v4 | ✓★✓ | ★★★ | **flipped** |

## Stayed matched but SOME versions flipped (1)


### 04C PROPOSITION 1  (match → match)

| ver | old | new | |
|---|---|---|---|
| v1 | ✓✓✓ | ★★★ | **flipped** |
| v2 | ✓✓✓ | ✓✓✓ | held |
| v3 | ✓★★ | ★★★ | **flipped** |
| v4 | ✓✓✓ | ✓✓✓ | held |

## Fully robust — no version flipped


### 01D PROPOSITION 6  (match → match)

| ver | old | new | |
|---|---|---|---|
| v2 | ✓✓✓ | ✓✓✓ | held |
| v4 | ✓✓✓ | ✓✓✓ | held |

### 03B LEMMA 2.2  (match → match)

| ver | old | new | |
|---|---|---|---|
| v2 | ✓✓✗ | ✓✓✗ | held |
| v4 | ✓✓✓ | ✓★✓ | held |

### 03C PROPOSITION 1  (match → match)

| ver | old | new | |
|---|---|---|---|
| v2 | ✓✓✓ | ✓✓✓ | held |
| v3 | ✓✓✓ | ✓✓✓ | held |
| v4 | ✓✓✓ | ✓✓✓ | held |

### 03C PROPOSITION 2  (match → match)

| ver | old | new | |
|---|---|---|---|
| v2 | ✓✓✓ | ✓✓✓ | held |
| v4 | ✓✓✓ | ✓✓✓ | held |

### 05C PROPOSITION 6  (match → match)

| ver | old | new | |
|---|---|---|---|
| v4 | ✓✓✓ | ✓✓✓ | held |

### 06D PROPOSITION 5  (match → match)

| ver | old | new | |
|---|---|---|---|
| v1 | ✓✓✓ | ✓✓✓ | held |
| v2 | ✓✓✓ | ✓✓✓ | held |
| v4 | ✓✓✓ | ✓✓✓ | held |

### 08C CLAIM 4.1.2  (match → match)

| ver | old | new | |
|---|---|---|---|
| v2 | ✓✓✗ | ✓✓✗ | held |
| v3 | ✗✓✓ | ✗✓✓ | held |
| v4 | ✓✓✓ | ✓✓✓ | held |

### 08D PROPOSITION 5  (match → match)

| ver | old | new | |
|---|---|---|---|
| v2 | ✓✗✗ | ✓✗✗ | held |
| v4 | ✓✓✓ | ★✓★ | held |

### 10D LEMMA 1.2  (match → match)

| ver | old | new | |
|---|---|---|---|
| v4 | ✓✓★ | ✓✓★ | held |

### 10D LEMMA 4.1  (match → match)

| ver | old | new | |
|---|---|---|---|
| v4 | ✓✓✓ | ✓✓✓ | held |
