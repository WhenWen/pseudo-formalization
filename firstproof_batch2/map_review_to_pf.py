"""Map each review error to its corresponding block(s) in the PF (pseudo-formalised)
rewrite. For every error of every PF'd proof we ask the model ONLY to name the PF
block(s) (tag + id) the original errored text was decomposed into; the actual PF
block text ("GPT expansion") is then extracted verbatim from the PF file by id, so
it is exact rather than re-generated.

Output rows (pf_review_map.json) carry, per error:
  - the review/error info (title, type, severity, description)
  - author_original : the verbatim original block the author wrote (errored_block)
  - pf_blocks       : [{tag, id}] the corresponding PF blocks
  - pf_expansion    : the verbatim PF statement+proof text for those blocks
  - mapping_note / match_confidence
"""

import argparse
import asyncio
import json
import os
import re
import time
from pathlib import Path

from openai import AsyncOpenAI

HERE = Path(__file__).resolve().parent
ERRORS = json.loads((HERE / "errors.json").read_text())
PF_DIR = HERE / "pf_outputs"
OUT = HERE / "pf_review_map.json"
FATAL_IDS = (HERE / "pf_fatal_ids.txt").read_text().split()

DEFAULT_MODEL = "gpt-5.5"
DEFAULT_EFFORT = "high"
CONCURRENCY = 6

TAGS = ["THEOREM", "PROPOSITION", "LEMMA", "CLAIM", "FACT"]

SYSTEM = """You are aligning a flawed math proof with its pseudo-formalised (PF) \
rewrite. The PF rewrite decomposes the proof into tagged blocks: THEOREM / \
PROPOSITION / LEMMA / CLAIM / FACT, each with a _STATEMENT and a _PROOF and a \
dotted id (THEOREM/PROPOSITION id="K", LEMMA id="K.L", CLAIM id="K.L.C", FACT \
id="K.L.C.F").

You are given one ERROR found in the original proof (with the exact original text \
span it lives in) and the FULL PF rewrite. Identify which PF block(s) that original \
span was turned into — i.e. where this same content/argument now lives in the PF \
tree. Usually 1-3 blocks. Prefer the most specific (deepest) block(s) that contain \
the errored content; include a parent block only if the error spans it.

Return tag+id pairs so the block is unambiguous (note id="1" can be both THEOREM 1 \
and PROPOSITION 1 — disambiguate via the tag). Also give a one-sentence note on \
how the original maps to those blocks and whether the flaw is still visible there."""

USER_TMPL = """ERROR
- title: {title}
- type/severity: {etype} / {sev}
- description: {desc}
- ORIGINAL TEXT SPAN (what the author wrote, verbatim):
\"\"\"
{block}
\"\"\"

FULL PF REWRITE (find the corresponding block(s) here):
{pf}
"""

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "pf_blocks": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "tag": {"type": "string", "enum": TAGS},
                    "id": {"type": "string"},
                },
                "required": ["tag", "id"],
            },
        },
        "match_confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "mapping_note": {"type": "string"},
    },
    "required": ["pf_blocks", "match_confidence", "mapping_note"],
}


def extract_block(pf: str, tag: str, bid: str):
    """Return verbatim '<TAG_STATEMENT ...> ... </> <TAG_PROOF ...> ... </>' for a
    given tag+id, or None if not found."""
    out = []
    for kind in ("STATEMENT", "PROOF"):
        m = re.search(rf'<{tag}_{kind} id="{re.escape(bid)}">(.*?)</{tag}_{kind}>',
                      pf, re.DOTALL)
        if m:
            out.append(f"[{tag} {bid} — {kind.lower()}]\n{m.group(1).strip()}")
    return "\n\n".join(out) if out else None


async def process(client, sem, sub_id, err, pf_text, model, effort):
    async with sem:
        prompt = USER_TMPL.format(
            title=err.get("title", ""), etype=err.get("error_type", ""),
            sev=err.get("severity", ""), desc=err.get("error_description", ""),
            block=err.get("errored_block", ""), pf=pf_text,
        )
        last = None
        for attempt in range(5):
            try:
                resp = await client.responses.create(
                    model=model, instructions=SYSTEM,
                    input=[{"role": "user", "content": prompt}],
                    text={"format": {"type": "json_schema", "name": "pf_map",
                                     "schema": SCHEMA, "strict": True}},
                    reasoning={"effort": effort}, max_output_tokens=4000,
                )
                data = json.loads(resp.output_text)
                break
            except Exception as e:
                last = e
                await asyncio.sleep(2 * (attempt + 1))
        else:
            print(f"  !! {sub_id}:{err.get('title','')[:30]} FAILED {str(last)[:90]}")
            return None

        # Extract verbatim PF block text for each named block.
        pieces, resolved = [], []
        for b in data["pf_blocks"]:
            txt = extract_block(pf_text, b["tag"], b["id"])
            if txt:
                pieces.append(txt)
                resolved.append({**b, "found": True})
            else:
                resolved.append({**b, "found": True if txt else False})
        n_found = sum(1 for b in resolved if b["found"])
        print(f"  ok {sub_id}  {err.get('severity','')[:5]:<5} -> "
              f"{[b['tag'][:4]+' '+b['id'] for b in data['pf_blocks']]} "
              f"({n_found}/{len(resolved)} extracted, conf={data['match_confidence']})")
        return {
            "id": sub_id,
            "title": err.get("title"),
            "error_type": err.get("error_type"),
            "severity": err.get("severity"),
            "error_description": err.get("error_description"),
            "source_reviewers": err.get("source_reviewers", []),
            "author_original": err.get("errored_block"),
            "block_location": err.get("block_location"),
            "pf_blocks": resolved,
            "pf_expansion": "\n\n".join(pieces),
            "match_confidence": data["match_confidence"],
            "mapping_note": data["mapping_note"],
        }


async def main(model, effort, only):
    targets = []
    for r in ERRORS:
        if r["id"] not in FATAL_IDS:
            continue
        if only and r["id"] not in set(only):
            continue
        pf_path = PF_DIR / f"{r['id']}.pf.txt"
        if not pf_path.exists():
            print(f"  (skip {r['id']}: no PF output)")
            continue
        pf_text = pf_path.read_text()
        for err in r.get("errors", []):
            targets.append((r["id"], err, pf_text))
    print(f"Mapping {len(targets)} errors across "
          f"{len({t[0] for t in targets})} PF'd proofs (model={model})")
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    sem = asyncio.Semaphore(CONCURRENCY)
    t0 = time.perf_counter()
    rows = await asyncio.gather(*[
        process(client, sem, sid, err, pf, model, effort) for sid, err, pf in targets])
    rows = [r for r in rows if r]
    if only and OUT.exists():  # merge: keep rows for submissions not in --only
        keep = [r for r in json.loads(OUT.read_text()) if r["id"] not in set(only)]
        rows = keep + rows
    rows.sort(key=lambda r: (r["id"], {"fatal": 0, "major": 1, "minor": 2}.get(r["severity"], 3)))
    OUT.write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    print(f"\nDone in {time.perf_counter()-t0:.0f}s. {len(rows)} mappings -> {OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--effort", default=DEFAULT_EFFORT)
    ap.add_argument("--only", nargs="*", default=None)
    a = ap.parse_args()
    asyncio.run(main(a.model, a.effort, a.only))
