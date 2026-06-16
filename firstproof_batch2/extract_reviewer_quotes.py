"""For each mapped error, extract the VERBATIM referee sentence(s) that correspond
to it, drawn only from the source reviewers' own review text (summary +
recommendation + inline comments, from corpus.json). Adds `reviewer_quotes`
(list of {reviewer, quote}) to each row of pf_review_map_checked.json (in place).
"""

import asyncio
import json
import os
import re
import time
from pathlib import Path

from openai import AsyncOpenAI

HERE = Path(__file__).resolve().parent
MAP = HERE / "pf_review_map_checked.json"
ROWS = json.loads(MAP.read_text())
CORPUS = {c["id"]: c for c in json.loads((HERE / "corpus.json").read_text())}

MODEL = os.environ.get("QUOTE_MODEL", "gpt-5.4-mini-2026-03-17")
EFFORT = "medium"
CONCURRENCY = 6

SYSTEM = """You extract verbatim referee quotes. Given one error found in a math \
proof and the referee report(s) that flagged it, return the exact sentence(s) the \
reviewer(s) actually wrote that express THIS error. Rules:
- Quotes MUST be copied verbatim (character-for-character) from the provided \
review text; do not paraphrase, summarise, or stitch fragments.
- Pick the 1-3 sentences most directly stating this specific error. Prefer the \
sharpest correctness statement (from the Correctness summary or an inline comment).
- Attribute each quote to the reviewer number whose text it came from.
- If a source reviewer's text contains nothing specific to this error, omit that \
reviewer rather than inventing a quote."""

USER = """ERROR
- title: {title}
- description: {desc}

REFEREE REPORT TEXT (quote only from here):
{reviews}
"""

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "quotes": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "reviewer": {"type": "integer"},
                    "quote": {"type": "string"},
                },
                "required": ["reviewer", "quote"],
            },
        },
    },
    "required": ["quotes"],
}


def review_text_for(sid, source_reviewers):
    sub = CORPUS[sid]
    revs = sub["reviews"]
    wanted = set(source_reviewers) or {r["reviewer"] for r in revs}
    chunks = []
    for r in revs:
        if r["reviewer"] not in wanted:
            continue
        parts = [f"===== Reviewer {r['reviewer']} ====="]
        if r["review_summary"]:
            parts.append("[Correctness / summary]\n" + r["review_summary"])
        if r["recommendation"]:
            parts.append("[Recommendation]\n" + r["recommendation"])
        for i, c in enumerate(r["inline_comments"], 1):
            parts.append(f"[Inline comment {i}]\n{c}")
        chunks.append("\n\n".join(parts))
    return "\n\n".join(chunks)


def _norm(s):
    return re.sub(r"\s+", " ", s).strip()


async def process(client, sem, row):
    async with sem:
        reviews = review_text_for(row["id"], row.get("source_reviewers", []))
        prompt = USER.format(title=row["title"], desc=row["error_description"], reviews=reviews)
        last = None
        for attempt in range(4):
            try:
                resp = await client.responses.create(
                    model=MODEL, instructions=SYSTEM,
                    input=[{"role": "user", "content": prompt}],
                    text={"format": {"type": "json_schema", "name": "quotes",
                                     "schema": SCHEMA, "strict": True}},
                    reasoning={"effort": EFFORT}, max_output_tokens=2000,
                )
                data = json.loads(resp.output_text)
                break
            except Exception as e:
                last = e
                await asyncio.sleep(2 * (attempt + 1))
        else:
            print(f"  !! {row['id']} {row['title'][:30]} FAILED {str(last)[:80]}")
            row["reviewer_quotes"] = []
            return
        nrev = _norm(reviews)
        for q in data["quotes"]:
            q["verbatim"] = _norm(q["quote"]) in nrev
        row["reviewer_quotes"] = data["quotes"]
        vb = sum(1 for q in data["quotes"] if q["verbatim"])
        print(f"  ok {row['id']:<4} {row['severity']:<5} {len(data['quotes'])} quote(s) ({vb} verbatim)")


async def main():
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    sem = asyncio.Semaphore(CONCURRENCY)
    t0 = time.perf_counter()
    print(f"Extracting reviewer quotes for {len(ROWS)} errors (model={MODEL})")
    await asyncio.gather(*[process(client, sem, r) for r in ROWS])
    MAP.write_text(json.dumps(ROWS, indent=2, ensure_ascii=False))
    nq = sum(len(r.get("reviewer_quotes", [])) for r in ROWS)
    nv = sum(1 for r in ROWS for q in r.get("reviewer_quotes", []) if q.get("verbatim"))
    print(f"\nDone in {time.perf_counter()-t0:.0f}s. {nq} quotes ({nv} verbatim) -> {MAP}")


if __name__ == "__main__":
    asyncio.run(main())
