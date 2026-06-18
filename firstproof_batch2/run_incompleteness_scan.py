"""Scan each RAW author proof (pf_clean_proofs/<sid>.tex) with GPT-5.5 and decide
whether the proof ITSELF admits being incomplete / partial / gapped — i.e. the
author signals the result is not fully established (e.g. "Partial Solution", "we do
not prove", "this is only heuristic", "remains open", "we were unable to", "sketch",
an editor/caveat note, etc.). We scan the raw text because the PF tends to launder
such hedges away.

Then emit leaner_set.json = the sids that do NOT claim incompleteness.

Outputs: faithcheck/incomplete/<sid>.json + leaner_set.json + printed table.
"""
import asyncio
import json
import os
from pathlib import Path
from openai import AsyncOpenAI

HERE = Path(__file__).resolve().parent
RAW = HERE / "pf_clean_proofs"
OUT = HERE / "faithcheck" / "incomplete"
OUT.mkdir(parents=True, exist_ok=True)
MODEL = os.environ.get("IS_MODEL", "gpt-5.5")
EFFORT = os.environ.get("IS_EFFORT", "high")
CONC = int(os.environ.get("IS_CONCURRENCY", "6"))

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "claims_incomplete": {"type": "string", "enum": ["yes", "partial", "no"]},
        "evidence_quotes": {"type": "string", "description": "verbatim author phrases signalling incompleteness, or ''"},
        "explanation": {"type": "string"},
    },
    "required": ["claims_incomplete", "evidence_quotes", "explanation"],
}

PROMPT = """You are reading a mathematical proof exactly as its author wrote it. Decide whether the proof ITSELF acknowledges that it is INCOMPLETE / partial / not fully established.

Count as a self-admission of incompleteness ONLY explicit authorial signals, such as:
- "Partial Solution", "Sketch", "We do not (fully) prove ...", "we were unable to ...",
- "this step is only heuristic / informal / not rigorous", "we leave ... open", "remains to be shown", "we conjecture", "modulo ...", "assuming ...(a gap)",
- an explicit editor/author caveat or disclaimer that some step/claim is not justified,
- statements that only a special case / one direction is proved when the full result was asked.

Do NOT count as incompleteness:
- ordinary citations to external results, standard "it is well known", routine omitted-but-standard steps,
- confident claims that later turn out to be wrong (a confident but false/gappy proof that does NOT admit it is still "no").

The question is ONLY whether the AUTHOR flags incompleteness, not whether the proof is actually correct.

== PROOF ==
{raw}

Decide:
- claims_incomplete: "yes" if the author clearly flags the proof/result as incomplete or only partially established; "partial" if there is a localized hedge on one sub-step but the proof is otherwise presented as complete; "no" if the proof presents itself as a complete proof.
- evidence_quotes: verbatim phrase(s) supporting this, or "".
- explanation: 1-2 sentences.

Respond ONLY with the JSON object required by the schema."""


async def one(client, sem, sid):
    raw = (RAW / f"{sid}.tex").read_text()
    async with sem:
        last = None
        for attempt in range(4):
            try:
                r = await client.responses.create(
                    model=MODEL, input=[{"role": "user", "content": PROMPT.format(raw=raw)}],
                    text={"format": {"type": "json_schema", "name": "incomplete", "schema": SCHEMA, "strict": True}},
                    reasoning={"effort": EFFORT}, max_output_tokens=12000)
                v = json.loads(r.output_text)
                (OUT / f"{sid}.json").write_text(json.dumps(v, indent=2, ensure_ascii=False))
                print(f"  {sid}: {v['claims_incomplete']:8} | {v['evidence_quotes'][:70]}", flush=True)
                return sid, v
            except Exception as e:
                last = e; await asyncio.sleep(2 * (attempt + 1))
        print(f"  {sid}: ERROR {str(last)[:80]}", flush=True)
        return sid, None


async def main():
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"]); sem = asyncio.Semaphore(CONC)
    sids = sorted(p.stem for p in RAW.glob("*.tex"))
    print(f"Incompleteness scan ({MODEL}) on {len(sids)} proofs")
    res = dict(await asyncio.gather(*[one(client, sem, s) for s in sids]))
    lean = sorted(s for s, v in res.items() if v and v["claims_incomplete"] == "no")
    (HERE / "leaner_set.json").write_text(json.dumps({
        "criterion": "proofs whose RAW text does NOT self-admit incompleteness (claims_incomplete == 'no')",
        "leaner_sids": lean,
        "excluded": {s: (v or {}).get("claims_incomplete", "ERROR") for s, v in res.items() if not (v and v["claims_incomplete"] == "no")},
    }, indent=2, ensure_ascii=False))
    from collections import Counter
    print("\n=== counts:", dict(Counter((v or {}).get("claims_incomplete", "ERROR") for v in res.values())))
    print(f"=== leaner set ({len(lean)}): {lean}")


if __name__ == "__main__":
    asyncio.run(main())
