# Automatic judge prompt (verdict ↔ reviewer adjudication)

Used by `judge_verdicts.py` / `judge_runs.py` / `judge_websearch_runs.py` to decide whether a block verifier's output AGREES with the golden reviewer comment. Model `gpt-5.5`, reasoning effort `high`, JSON-schema-constrained output.

The reviewer comment is treated as GROUND TRUTH; the judge does not re-judge the math.

## SYSTEM

```text
You are adjudicating whether an automated block verifier's verdict on a piece of a mathematical proof matches the human referee's assessment.

The REVIEWER COMMENT is GOLDEN ground truth: the referee is correct that the stated error is real and is located as described. Your job is NOT to re-judge the math — assume the reviewer is right.

You are given the verifier's full output (its CORRECT/INCORRECT verdict plus its reasoning) and the golden reviewer comment(s) about the same block. Decide whether the verifier's verdict AGREES with the reviewer:
- "agree": the verifier returned INCORRECT and its reasoning identifies essentially the SAME defect the reviewer describes.
- "partial": the verifier returned INCORRECT but for a DIFFERENT or only partially overlapping reason (it flagged something, but not the reviewer's actual defect), OR it hedged.
- "disagree": the verifier returned CORRECT (i.e. it missed the golden error), or its reasoning contradicts the reviewer.

Also set verifier_found_same_error = true only when the verifier specifically identifies the reviewer's defect (not merely any issue).
```

## USER (template; `{gold}` = reviewer comment(s), `{verifier}` = the BV output being judged)

```text
GOLDEN REVIEWER COMMENT(S) (ground truth — the real, correctly-located error):
{gold}

BLOCK VERIFIER OUTPUT (verdict + reasoning to be judged):
{verifier}

Does the verifier's verdict match the golden reviewer comment?
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

For each known error on the block, the verbatim reviewer quote(s) are pulled from `pf_review_map_checked.json` and formatted as:

```text
• Error: <title> [<severity>/<error_type>]
  Reviewer said (GOLDEN):
    - (Reviewer N) "<verbatim quote>"
```

A run that returned CORRECT is auto-scored `disagree` (it missed the error) without a model call; only INCORRECT runs are sent to the judge. Block-level agreement = best of its runs (agree > partial > disagree).
