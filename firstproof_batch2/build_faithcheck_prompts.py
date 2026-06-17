"""Block-wise PF-vs-RAW faithfulness check.

For each PF block of a submission, give Codex the FULL raw author proof and that one
PF block (statement + proof + deps), and ask whether the PF block faithfully represents
what the raw text actually says — with special attention to ways a rewrite can
*launder* a defect: renaming/sanitising a nonstandard or nonexistent object into a
clean generic one, dropping an attribution/citation the author leaned on, silently
adding or removing a hypothesis, or strengthening/weakening a claim.

If unfaithful, Codex returns a corrected statement/proof that matches the raw text.

Prompts -> faithcheck/<SID>/prompts/<block>.txt   (SID from env FAITH_SID, default 10D)
"""
import json
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SID = os.environ.get("FAITH_SID", "10D")
RAW = (HERE / "pf_clean_proofs" / f"{SID}.tex").read_text()
PF = (HERE / "pf_outputs" / f"{SID}.pf.txt").read_text()
OUT = HERE / "faithcheck" / SID / "prompts"
OUT.mkdir(parents=True, exist_ok=True)

BLOCK_RE = re.compile(
    r'<(THEOREM|PROPOSITION|LEMMA|CLAIM|FACT)_(STATEMENT|PROOF) id="([^"]+)">(.*?)</\1_\2>', re.DOTALL)
DEPS_RE = re.compile(r'<DEPS id="([^"]+)">(.*?)</DEPS>', re.DOTALL)
SHORT = {"THEOREM": "Theorem", "PROPOSITION": "Proposition", "LEMMA": "Lemma",
         "CLAIM": "Claim", "FACT": "Fact"}


def parse():
    blocks, order = {}, []
    for m in BLOCK_RE.finditer(PF):
        k = (m.group(1), m.group(3))
        if k not in blocks:
            order.append(k)
        blocks.setdefault(k, {})[m.group(2).lower()] = m.group(4).strip()
    deps = {}
    for m in DEPS_RE.finditer(PF):
        did = m.group(1)
        did = did[len("theorem_"):] if did.startswith("theorem_") else did
        deps[did] = m.group(2).strip()
    return blocks, order, deps


TMPL = """A research-math proof was pseudo-formalised: rewritten into a hierarchy of tagged blocks (Theorem > Proposition > Lemma > Claim > Fact). Your job is a FAITHFULNESS check of ONE block against the original author text.

The pseudo-formalisation must FAITHFULLY preserve what the author actually wrote — including any flaws. It must NOT silently "clean up" the mathematics. In particular, watch for these laundering failures, which are UNFAITHFUL:
- renaming or re-describing a nonstandard / coined / possibly-nonexistent object as a clean, generic, standard-looking one (e.g. the author names a specific dubious object or invokes it as a known notion, but the block presents it as an ordinary construction);
- dropping an attribution/citation the author used to justify a step (or adding one the author did not give);
- silently adding, removing, or altering a hypothesis, quantifier, or condition;
- strengthening, weakening, or restating the claim differently from the author;
- presenting as well-defined / standard something the author presented as novel, asserted, or cited.

== ORIGINAL AUTHOR PROOF (authoritative source) ==
{raw}

== PF BLOCK UNDER REVIEW: {label} ==
STATEMENT:
{statement}

PROOF:
{proof}

DEPS: {deps}

Compare this block ONLY against the portion of the author text it corresponds to. Decide:
- faithful: "yes" if the block faithfully preserves the author's content (including any flaws) with no laundering; "no" if it diverges in any of the ways above; "partial" for a minor wording drift that does not change meaning.
- mismatch_description: if not "yes", state precisely what the block changed relative to the raw text and why it matters (name the laundered object / dropped citation / altered hypothesis).
- corrected_statement / corrected_proof: if "no", give a corrected version of the block's statement and proof that faithfully matches the raw author text (preserve the author's exact naming, attributions, and any flaws). Leave both "" if faithful or only partial.

Respond ONLY with the JSON object required by the output schema."""


def main():
    blocks, order, deps = parse()
    n = 0
    for (tag, bid) in order:
        b = blocks[(tag, bid)]
        label = f"{SHORT[tag]} {bid}"
        prompt = TMPL.format(raw=RAW.strip(), label=label,
                             statement=b.get("statement", "(none)"),
                             proof=b.get("proof", "None"), deps=deps.get(bid, "") or "(none)")
        fn = f"{tag}_{bid.replace('.', '_')}"
        (OUT / f"{fn}.txt").write_text(prompt, encoding="utf-8")
        n += 1
    print(f"Wrote {n} faithfulness prompts for {SID} -> {OUT}")


if __name__ == "__main__":
    main()
