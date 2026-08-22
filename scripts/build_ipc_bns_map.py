#!/usr/bin/env python3
"""Propose an IPC -> BNS section mapping from the corpus itself.

WHY THIS IS NEEDED
    On 1 July 2024 the Bharatiya Nyaya Sanhita replaced the Indian Penal Code.
    511 IPC sections became 358 BNS sections: some merged, some split, some are
    new, some were dropped. Both codes remain valid law -- which one applies
    depends on WHEN the offence happened.

    A system holding both codes cannot answer "what is section 420" without
    knowing that the same offence is section 318 in the newer code. That
    correspondence is what this table provides.

HOW THE CANDIDATES ARE GENERATED
    Every chunk is already embedded -- a vector, a list of 1536 numbers
    representing its meaning. So for each IPC section we take its existing
    vector and search the BNS half of the index for the nearest match. No new
    embedding calls, no cost.

    Nearest-by-meaning is a reasonable way to PROPOSE a pair, because the two
    codes describe the same offences in similar language.

WHY THIS IS NOT GROUND TRUTH
    It is a candidate generator, not an authority. Two risks:

      1. Circularity. Using the retriever to build the table that the retriever
         is later evaluated against would flatter it. The table must therefore
         be verified by a human against the official government comparison
         documents before any evaluation uses it.

      2. Split provisions. Where one IPC section maps to several BNS sections,
         nearest-neighbour returns only one. The `alternatives` column keeps
         the runners-up so a reviewer can see the ambiguity.

    Output carries a `verified` column, false everywhere until a law student
    checks it. Nothing downstream should treat unverified rows as gold.

USAGE
    python scripts/build_ipc_bns_map.py
    python scripts/build_ipc_bns_map.py --min-score 0.75 --limit 60
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from clients.qdrant_client import COLLECTION, qdrant  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "ipc_bns_map_candidates.csv"

TITLE_RE = re.compile(r"Section\s+\S+\.\s*(.{3,150}?)[—–]", re.S)


def short_title(text: str, limit: int = 90) -> str:
    m = TITLE_RE.search(text or "")
    raw = m.group(1) if m else (text or "")[:limit]
    return re.sub(r"\s+", " ", raw).strip().rstrip(".")[:limit]


def load_sections(client, corpus: str) -> dict[str, dict]:
    """section_number -> {vector, text}. Keeps the LONGEST chunk per section,
    since that is the one carrying the substantive provision rather than a
    cross-page fragment."""
    best: dict[str, dict] = {}
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=COLLECTION,
            limit=400,
            offset=offset,
            with_payload=True,
            with_vectors=True,
            scroll_filter={"must": [{"key": "corpus", "match": {"value": corpus}}]},
        )
        for p in points:
            payload = p.payload or {}
            sec = payload.get("section_number")
            text = payload.get("text") or ""
            if not sec:
                continue
            if sec not in best or len(text) > len(best[sec]["text"]):
                best[sec] = {"vector": p.vector, "text": text, "page": payload.get("page")}
        if offset is None:
            break
    return best


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-score", type=float, default=0.0,
                    help="only report candidates at or above this similarity")
    ap.add_argument("--limit", type=int, default=0, help="stop after N sections (0 = all)")
    args = ap.parse_args()

    client = qdrant()
    print("Loading sections from the index (no embedding calls, no cost)…")
    ipc = load_sections(client, "IPC")
    print(f"  IPC sections: {len(ipc)}")
    print(f"  BNS sections: {len(load_sections(client, 'BNS'))}")

    rows = []
    items = sorted(ipc.items(), key=lambda kv: (len(kv[0]), kv[0]))
    if args.limit:
        items = items[: args.limit]

    print(f"\nMatching {len(items)} IPC sections against the BNS half of the index…")
    for i, (sec, data) in enumerate(items, 1):
        hits = client.search(
            collection_name=COLLECTION,
            query_vector=data["vector"],
            query_filter={"must": [{"key": "corpus", "match": {"value": "BNS"}}]},
            limit=4,
            with_payload=True,
        )
        hits = [h for h in hits if (h.payload or {}).get("section_number")]
        if not hits:
            continue
        top = hits[0]
        if top.score < args.min_score:
            continue
        alts = ";".join(
            f"BNS {h.payload['section_number']}@{h.score:.3f}" for h in hits[1:4]
        )
        rows.append(
            {
                "ipc_section": sec,
                "ipc_title": short_title(data["text"]),
                "ipc_page": data["page"],
                "bns_section": top.payload["section_number"],
                "bns_page": top.payload.get("page"),
                "similarity": round(float(top.score), 4),
                "alternatives": alts,
                "relation": "one_to_one_candidate",
                "verified": "false",
                "verified_by": "",
                "notes": "",
            }
        )
        if i % 100 == 0:
            print(f"  {i}/{len(items)}…")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    scores = sorted(r["similarity"] for r in rows)
    print(f"\n  wrote {len(rows)} candidate pairs -> {OUT.relative_to(ROOT)}")
    print(f"  similarity  min {scores[0]:.3f}  median {scores[len(scores)//2]:.3f}  max {scores[-1]:.3f}")
    strong = sum(1 for s in scores if s >= 0.80)
    print(f"  {strong} pairs at similarity >= 0.80 ({100*strong//len(scores)}%)")
    print("\n  ALL ROWS ARE UNVERIFIED. A human must check them against the official")
    print("  BPRD / state-police comparison tables before any evaluation uses them.")


if __name__ == "__main__":
    main()
