#!/usr/bin/env python3
"""Generate evaluation queries FROM the corpus, with certain gold answers.

THE PROBLEM THIS SOLVES
    An evaluation set needs GOLD -- the known-correct answer, written down
    before the system runs. Normally deciding "the right section here is IPC
    420" is a legal judgement, which means waiting for someone with legal
    training.

    That blocks everything on another person's calendar.

THE TRICK
    Build the question FROM the section. Then the section is the answer BY
    CONSTRUCTION, not by anyone's opinion:

        index holds:  "Section 378. Theft.-Whoever, intending to take
                       dishonestly any movable property..."
        title:        "Theft"

        query   "What does Section 378 of the IPC provide?"
        gold    IPC 378          <- certain: the query was built from it

    Nobody needs to verify that. It is true by how the query was made.

WHAT THIS DOES AND DOES NOT MEASURE
    DOES:  retrieval. Did the system find the section the question is about?
           That covers cross-statute confusion, routing accuracy, recall, and
           citation grounding -- the paper's three headline metrics.

    DOES NOT: whether the generated ANSWER is good legal advice. That still
           needs a lawyer, and it is a separate experiment.

THREE PHRASINGS PER SECTION -- and the contrast IS the experiment
    numbered   names the section AND the code   most information given
    topic_code names the subject and the code   some information
    topic_only names only the subject           how real people ask

    Comparing them answers: does telling the system which law you mean help,
    or does it trigger routing that sends the query somewhere worse?

USAGE
    python eval/generate_from_corpus.py --per-corpus 40
    python eval/generate_from_corpus.py --per-corpus 40 --out eval/generated.jsonl
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from clients.qdrant_client import COLLECTION, qdrant  # noqa: E402
from ingest.registry import DOCUMENT_REGISTRY  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "eval" / "generated_queryset.jsonl"

# "Section 378. Theft.-Whoever..." -> title is "Theft"
# Indian statutes put the marginal note between the number and the em-dash.
TITLE_RE = re.compile(r"Section\s+\S+?\.\s*(.{3,120}?)\s*[—–]")

HUMAN_NAME = {
    "IPC": "the Indian Penal Code",
    "BNS": "the Bharatiya Nyaya Sanhita",
    "CRPC": "the Code of Criminal Procedure",
    "CPA": "the Consumer Protection Act",
}

# Titles that describe document plumbing rather than law. A query about
# "Short title and commencement" measures nothing useful.
SKIP_TITLES = re.compile(
    r"^(short title|commencement|extent|definitions?|interpretation|repeal|"
    r"savings?|schedule|omitted|amendment of|substitution of)\b",
    re.I,
)


def clean_title(text: str) -> str | None:
    m = TITLE_RE.search(text or "")
    if not m:
        return None
    title = re.sub(r"\s+", " ", m.group(1)).strip(" .—-")
    if len(title) < 6 or len(title) > 110:
        return None
    if SKIP_TITLES.match(title):
        return None
    if not re.search(r"[A-Za-z]{4}", title):
        return None
    return title


def load_sections(client, corpus: str) -> list[dict]:
    """One entry per section: the longest chunk carrying that number, plus its
    title. Longest wins because short ones are cross-page fragments."""
    best: dict[str, dict] = {}
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=COLLECTION,
            limit=400,
            offset=offset,
            with_payload=True,
            with_vectors=False,
            scroll_filter={"must": [{"key": "corpus", "match": {"value": corpus}}]},
        )
        for p in points:
            pl = p.payload or {}
            sec, text = pl.get("section_number"), pl.get("text") or ""
            if not sec:
                continue
            if sec not in best or len(text) > len(best[sec]["text"]):
                best[sec] = {"section": sec, "text": text, "page": pl.get("page")}
        if offset is None:
            break

    out = []
    for entry in best.values():
        entry["title"] = clean_title(entry["text"])
        # A title is required only where topic phrasings will be built.
        if entry["title"] or corpus not in TITLE_QUALITY_OK:
            out.append(entry)
    return out


# The BNS PDF carries no marginal notes -- extraction returns the first clause
# of the provision instead of a title ("Except in the cases hereinafter
# excepted..."). Topic-based phrasings built from that are nonsense, so BNS gets
# the numbered variant only, which needs no title. Gold is equally certain, and
# numbered queries are the ones that matter most for cross-statute testing.
TITLE_QUALITY_OK = {"IPC", "CRPC", "CPA"}


def make_queries(corpus: str, entry: dict, counter: dict) -> list[dict]:
    """Phrasings of the same question, all sharing one certain gold answer."""
    sec = entry["section"]
    title = entry.get("title")
    act = HUMAN_NAME[corpus]

    variants = [("numbered", f"What does Section {sec} of {act} provide?", "technical")]

    if title and corpus in TITLE_QUALITY_OK:
        lower = title[0].lower() + title[1:]
        variants += [
            ("topic_code", f"Which section of {act} deals with {lower}?", "technical"),
            ("topic_only", f"What is the law on {lower} in India?", "layman"),
        ]

    rows = []
    pair_id = f"G_{corpus}_{sec}"
    for variant, text, register in variants:
        counter["n"] += 1
        rows.append(
            {
                "query_id": f"G{counter['n']:04d}",
                "pair_id": pair_id,
                "text": text,
                "category": "generated_retrieval",
                "variant": variant,
                "numbering_scheme": corpus if variant != "topic_only" else "none",
                "expected_corpus": corpus,
                "expected_sections": [f"{corpus} {sec}"],
                "answerable_from_corpus": True,
                "phrasing_register": register,
                "gold_status": "certain_by_construction",
                "source_page": entry["page"],
                "section_title": title or "",
                "notes": "query generated FROM this section; gold needs no legal review",
            }
        )
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-corpus", type=int, default=40,
                    help="how many sections to sample from each law")
    ap.add_argument("--seed", type=int, default=20260823, help="fixed for reproducibility")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    random.seed(args.seed)
    client = qdrant()
    counter = {"n": 0}
    rows: list[dict] = []

    print(f"  sampling up to {args.per_corpus} sections per corpus (seed {args.seed})\n")
    print(f"  {'CORPUS':<8}{'SECTIONS':>10}{'USABLE TITLE':>14}{'SAMPLED':>9}{'QUERIES':>9}")
    print("  " + "-" * 52)

    for info in sorted(DOCUMENT_REGISTRY.values(), key=lambda i: i.statute_code):
        corpus = info.corpus
        sections = load_sections(client, corpus)
        sample = random.sample(sections, min(args.per_corpus, len(sections)))
        made = []
        for entry in sorted(sample, key=lambda e: e["section"]):
            made.extend(make_queries(corpus, entry, counter))
        rows.extend(made)
        print(f"  {corpus:<8}{len(sections):>10}{len(sections):>14}{len(sample):>9}{len(made):>9}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    import collections
    reg = collections.Counter(r["phrasing_register"] for r in rows)
    var = collections.Counter(r["variant"] for r in rows)

    print("  " + "-" * 52)
    print(f"  {'TOTAL':<8}{'':<10}{'':<14}{'':<9}{len(rows):>9}")
    print(f"\n  wrote {len(rows)} queries -> {args.out.relative_to(ROOT)}")
    print(f"  gold status: certain_by_construction (no legal review needed)")
    print(f"\n  by variant : {dict(var)}")
    print(f"  by register: {dict(reg)}")
    print(f"\n  estimated run cost ~${len(rows)*0.0059:.2f}  (~Rs {len(rows)*0.0059*88:.0f})")

    print("\n  SAMPLES")
    for r in rows[:6]:
        print(f"    [{r['variant']:<10}] {r['text'][:66]}")
        print(f"                 gold {r['expected_sections']}")


if __name__ == "__main__":
    main()
