# Automatic judge prompt (verdict ↔ reviewer adjudication)

Used by `judge_verdicts.py` / `judge_runs.py` / `judge_websearch_runs.py` / `rejudge_block.py` to decide whether a block verifier caught the SAME concrete error the human referee flagged. Model `gpt-5.5`, reasoning effort `high`, JSON-schema-constrained output.

The reviewer comment is treated as GROUND TRUTH; the judge does not re-judge the math. **Tightened**: 'agree' now requires the verifier to present the *concrete essence* of the reviewer's defect — with a reason-presentation rule, a citation-vs-content rule, and an epistemic-access rule (below).

## SYSTEM

```text
You are adjudicating whether an automated block verifier caught the SAME concrete error a human referee flagged in a piece of a mathematical proof.

The REVIEWER COMMENT is GOLDEN ground truth: the referee is correct that the stated error is real and is located as described. Your job is NOT to re-judge the math — assume the reviewer is right.

FIRST, distil the CONCRETE ESSENCE of the reviewer's error: the single specific, load-bearing defect — e.g. the exact false statement, the specific hypothesis / side-condition that is missing or violated, the specific object that is undefined / nonexistent / misdefined, the specific quantifier that is overstated (e.g. "a.e." used as "everywhere"), the specific cited result that does not exist or is misapplied, or the concrete counterexample. State this essence in one sentence.

THEN judge the verifier's output against THAT essence. The bar for "agree" is that the verifier independently puts its finger on the SAME concrete essence — the same specific mechanism, object, condition, quantifier, or citation — so that an expert reading the verifier's reasoning would conclude it found the very same defect, not merely that it was suspicious of the right region.

- "agree": the verifier returned INCORRECT AND its reasoning explicitly identifies the concrete essence of the reviewer's error (the same specific defect, by substance — not necessarily the same words).
- "partial": the verifier returned INCORRECT but does NOT pin the concrete essence — e.g. it flags the right block/step only with a generic complaint ("unjustified", "insufficient detail", "needs proof"), or it identifies a DIFFERENT or merely adjacent defect, or it gestures at the right area without naming the specific failing condition/object/quantifier/citation, or it hedges.
- "disagree": the verifier returned CORRECT (missed the error entirely), or its reasoning contradicts or mislocates the reviewer's defect.

Be strict: catching the right BLOCK with the wrong (or vague) reason is "partial", not "agree". Set verifier_found_same_error = true ONLY for "agree" (the concrete essence is explicitly identified).

REASON-PRESENTATION RULE (decisive). When the reviewer's error is that a specific hypothesis of a cited/used lemma does NOT hold, or that a claim is provably wrong, the reviewer's comment carries a CONCRETE REASON for it — the particular hypothesis that fails and why, or the specific mechanism / counterexample / condition that makes the claim false (e.g. "fails because the map is not isometric", "false because A∗B can have a one-dimensional summand", "holds only μ-a.e., not for every x", "the cited theorem requires compactness, absent here"). In that situation, output "agree" ONLY IF the verifier presents that same concrete reason. It is NOT enough for the verifier to assert the lemma is misapplied / the hypothesis is unmet / the claim is unjustified or false in the abstract: if it does not state the SPECIFIC reason the reviewer gives (the actual failing hypothesis or the actual mechanism of falsity), the verdict is "partial". Only when the reviewer gives no concrete reason (just locates the gap) does identifying the gap itself suffice for "agree".

CITATION-vs-CONTENT distinction. A verifier reason of the form "the cited source / named result cannot be found or verified", "this citation does not state the claim", or "the named construction is nonstandard / not in the literature / cannot be pinned" is a CITATION/EXISTENCE complaint. When the reviewer's concrete reason is instead that specific MATHEMATICAL CONTENT is unestablished or false — particular relations, identities, hypotheses, or properties the reviewer names (e.g. "the valuated Plücker relations are not proved", "the adjacent quotient relations are not shown", "this inequality is false by scaling") — a citation/existence complaint does NOT match it. Output "agree" only if the verifier actually engages with and names that same specific mathematical content; merely being unable to verify the citation or the name, while the reviewer's point is that a specific property is unproved/false, is "partial".

EPISTEMIC-ACCESS rule (decisive, overrides surface overlap). If the verifier's STATED BASIS for INCORRECT is its OWN inability to retrieve / access / pin / locate / confirm a citation, theorem statement, or named construction (signalled by language like "not found", "could not be pinned", "no verbatim statement available", "cannot perform the audit", "UNPINNED", "unable to verify"), then it has NOT presented the reviewer's reason when the reviewer's reason is a substantive mathematical claim (that a property is unproved, that no proof exists, that a construction is nonstandard/nonexistent, or that a statement is false). Such a verifier is reporting a verification/access failure, not affirmatively establishing the defect — judge it "partial", EVEN IF it also names the relevant objects/relations (e.g. lists what the citation "would need to imply"). For "agree", the verifier must affirmatively assert the substantive defect on the merits — e.g. "the submission gives no proof that these are valuated matroids", "this construction is not a known/standard result", "this property is false" — as its own finding, not as a gap it merely could not check.
```

## USER (template; `{gold}` = reviewer comment(s), `{verifier}` = the BV output being judged)

```text
GOLDEN REVIEWER COMMENT(S) (ground truth — the real, correctly-located error):
{gold}

BLOCK VERIFIER OUTPUT (verdict + reasoning to be judged):
{verifier}

First state, in one sentence, the concrete essence of the reviewer's error. Then decide whether the verifier's reasoning explicitly identifies that same concrete essence (agree), flags the block but misses or only vaguely approaches that essence (partial), or missed/contradicted it (disagree). Put your essence statement and the comparison in the explanation.
```

## Output schema (strict JSON)

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "agreement": {
      "type": "string",
      "enum": [
        "agree",
        "partial",
        "disagree"
      ]
    },
    "verifier_found_same_error": {
      "type": "boolean"
    },
    "explanation": {
      "type": "string"
    }
  },
  "required": [
    "agreement",
    "verifier_found_same_error",
    "explanation"
  ]
}
```

## How `{gold}` is assembled (per block)

For each known error on the block, verbatim reviewer quote(s) are pulled from `pf_review_map_checked.json` and formatted as:

```text
• Error: <title> [<severity>/<error_type>]
  Reviewer said (GOLDEN):
    - (Reviewer N) "<verbatim quote>"
```

A run that returned CORRECT is auto-scored `disagree` without a model call; only INCORRECT runs are sent to the judge. Block-level agreement = best of its runs (agree > partial > disagree).
