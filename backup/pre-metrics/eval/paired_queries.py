#!/usr/bin/env python3
"""Paired IPC <-> BNS queries -- the set that actually tests the thesis.

WHY THIS SET EXISTS
    The other two sets measure real things but neither tests the claim.

        eval/generate_from_corpus.py  builds a question FROM a section, so the
                                      gold is certain. It calibrates retrieval.
                                      It contains ZERO IPC/BNS pairs.
        eval/layman_queries.py        tests whether messy human language
                                      reaches the law at all.

    Neither asks the question the paper is about: when the same offence exists
    under two numbering schemes, can a dense retriever tell them apart?

THE DESIGN IS THE EXPERIMENT
    Each provision produces three queries that share a pair_id:

        ipc_numbered   "What is the punishment for cheating and dishonestly
                        inducing delivery of property under Section 420 of the
                        Indian Penal Code?"
        bns_numbered   "... under Section 318(4) of the Bharatiya Nyaya
                        Sanhita?"
        neutral_topic  "What is the law on cheating and dishonestly inducing
                        delivery of property in India?"

    Same offence. Same words for the offence. The ONLY thing that changes is
    the numbering scheme -- and under `neutral_topic`, nothing identifies a
    scheme at all.

    A dense retriever embeds meaning. "Section 420 IPC" and "Section 318(4)
    BNS" mean nearly the same thing, and the two provisions are worded almost
    identically in the two codes, so there is very little signal separating
    them. That is the failure this set is built to measure rather than assume.

WHAT EACH VARIANT ANSWERS
    ipc_numbered vs bns_numbered   Does naming the code work at all? Build a
                                   confusion matrix of retrieved corpus
                                   against expected corpus. Off-diagonal
                                   entries ARE cross-statute retrieval failure.
    neutral_topic                  With no scheme named, which code does the
                                   system default to? A strong lean toward
                                   either one is a bias worth reporting, since
                                   the correct answer depends on a date the
                                   query does not contain.

GOLD
    Taken from data/recodification_map.json, restricted to entries whose BNS
    target was located in this index and whose bare-Act text was read to
    confirm the subject matches. Unverified entries (all CrPC -> BNSS, because
    the BNSS is not ingested) are excluded: a gold label no retriever can
    reach measures the corpus, not the system.

    The gold is therefore as certain as generate_from_corpus.py's -- both ends
    of every pair were read out of the index.

USAGE
    python eval/paired_queries.py
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "eval" / "paired_queryset.jsonl"
MAP = ROOT / "data" / "recodification_map.json"

HUMAN_NAME = {
    "IPC": "the Indian Penal Code",
    "BNS": "the Bharatiya Nyaya Sanhita",
    "CRPC": "the Code of Criminal Procedure",
    "BNSS": "the Bharatiya Nagarik Suraksha Sanhita",
}


def section_of(ref: str) -> str:
    """'BNS 318(4)' -> '318(4)'."""
    return ref.split(" ", 1)[1]


def build() -> list[dict]:
    data = json.loads(MAP.read_text(encoding="utf-8"))
    rows: list[dict] = []
    n = 0

    for entry in data["mappings"]:
        # Only pairs where BOTH ends were confirmed present in this index.
        if entry["confidence"] != "verified_in_corpus":
            continue
        old, subject = entry["from"], entry["subject"]
        new = entry["to"][0]
        old_act, new_act = old.split(" ", 1)[0], new.split(" ", 1)[0]
        pair_id = f"P_{old.replace(' ', '')}"

        variants = [
            ("ipc_numbered",
             f"What is the punishment for {subject} under Section "
             f"{section_of(old)} of {HUMAN_NAME[old_act]}?",
             [old], old_act, [new], "technical"),
            ("bns_numbered",
             f"What is the punishment for {subject} under Section "
             f"{section_of(new)} of {HUMAN_NAME[new_act]}?",
             [new], new_act, [old], "technical"),
            ("neutral_topic",
             f"What is the law on {subject} in India?",
             [old, new], "EITHER", [], "layman"),
        ]

        for variant, text, gold, corpus, counterpart, register in variants:
            n += 1
            rows.append({
                "query_id": f"P{n:04d}",
                "pair_id": pair_id,
                "text": text,
                "category": "paired_recodification",
                "variant": variant,
                "numbering_scheme": corpus if corpus != "EITHER" else "none",

                # --- gold ------------------------------------------------
                "expected_sections": gold,
                "expected_corpus": corpus,
                "expected_corpora": [old_act, new_act] if corpus == "EITHER" else [corpus],
                "gold_mode": "either_era" if corpus == "EITHER" else "exact",
                "gold_status": "certain_by_construction",

                # --- the measurement -------------------------------------
                # Retrieving THIS instead of the gold is not a generic miss.
                # It is the specific failure the paper names: the right
                # offence found under the wrong numbering scheme. Counted
                # separately from ordinary retrieval error.
                "counterpart_sections": counterpart,
                "counterpart_corpus": (new_act if variant == "ipc_numbered"
                                       else old_act if variant == "bns_numbered"
                                       else None),

                "answerable_from_corpus": True,
                "phrasing_register": register,
                "subject": subject,
                "substantive_change_note": entry.get("note", ""),
                "notes": ("same offence, same wording, only the numbering "
                          "scheme differs across the pair"),
            })
    return rows


def main() -> None:
    rows = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    var = collections.Counter(r["variant"] for r in rows)
    corp = collections.Counter(r["expected_corpus"] for r in rows)
    pairs = len({r["pair_id"] for r in rows})

    print(f"  wrote {len(rows)} paired queries -> {OUT.relative_to(ROOT)}")
    print(f"  from {pairs} verified IPC<->BNS provision pairs\n")
    print(f"  by variant         : {dict(var)}")
    print(f"  by expected corpus : {dict(corp)}")
    print(f"  gold status        : certain_by_construction "
          f"(both ends read out of the index)")
    print(f"\n  estimated run cost ~${len(rows)*0.0059:.2f}  "
          f"(~Rs {len(rows)*0.0059*88:.0f})")

    print("\n  SAMPLE -- one provision across all three variants:")
    for r in [x for x in rows if x["pair_id"] == "P_IPC420"]:
        print(f"    [{r['variant']:<14} -> {str(r['expected_corpus']):<7}] {r['text'][:88]}")
        print(f"                          gold={r['expected_sections']}  "
              f"counterpart={r['counterpart_sections']}")


if __name__ == "__main__":
    main()
