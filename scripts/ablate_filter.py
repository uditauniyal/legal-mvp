#!/usr/bin/env python3
"""Can the EMBEDDINGS tell the IPC from the BNS, with the filter switched off?

WHY THIS EXPERIMENT HAD TO EXIST
    The main evaluation reported a perfect corpus confusion matrix on the
    paired set -- 33/33 IPC queries answered from the IPC, 33/33 BNS queries
    from the BNS, zero off-diagonal. That looks like a clean negative result:
    no cross-statute confusion.

    It is not a result at all. The Router reads the Act name out of the query
    and applies a hard Qdrant filter:

        ipc_numbered   filter=IPC     33
        bns_numbered   filter=BNS     33
        neutral_topic  filter=None    33

    With the filter on, an IPC-numbered query CANNOT return a BNS chunk. The
    matrix was measuring a keyword lookup, and the diagonal was guaranteed
    before any embedding was compared. Reporting it as evidence that dense
    retrieval separates the two codes would have been badly wrong.

    This script removes the filter and asks the question the matrix could not.

WHAT IT DOES
    Embeds each numbered paired query and searches the whole index with no
    corpus restriction. Then reports which corpus supplied most of the top 15
    chunks, and which supplied the single top-scoring one.

    Retrieval only -- no generation, no LLM. One embedding call for 66 short
    queries, a fraction of a rupee, and it is deterministic given a fixed
    index.

READING THE NUMBERS AGAINST CHANCE
    A corpus that occupies more of the index wins more often for free. Shares
    of the 1,899 indexed chunks:

        CrPC 39.1%    IPC 31.3%    BNS 22.3%    CPA 7.3%

    So "IPC dominates" is worth ~31% by chance and "BNS dominates" ~22%.
    Anything close to those numbers means the Act name in the query carried
    no usable signal.

USAGE
    python scripts/ablate_filter.py
"""

from __future__ import annotations

import collections
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
QUERYSET = ROOT / "eval" / "paired_queryset.jsonl"

from clients.openai_client import embed_texts  # noqa: E402
from clients.qdrant_client import COLLECTION, qdrant  # noqa: E402

CORPORA = ["IPC", "BNS", "CRPC", "CPA"]


def wilson(k: int, n: int) -> tuple[float, float, float]:
    if n == 0:
        return 0.0, 0.0, 0.0
    z = 1.959963985
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, centre - half), min(1.0, centre + half)


def corpus_shares(client) -> dict[str, float]:
    """Share of the index held by each corpus -- the chance baseline."""
    counts, offset = collections.Counter(), None
    while True:
        points, offset = client.scroll(
            collection_name=COLLECTION, limit=500, offset=offset,
            with_payload=True, with_vectors=False)
        for p in points:
            counts[(p.payload or {}).get("corpus")] += 1
        if offset is None:
            break
    total = sum(counts.values()) or 1
    return {k: v / total for k, v in counts.items() if k}


def main() -> None:
    rows = [json.loads(l) for l in QUERYSET.read_text(encoding="utf-8").splitlines() if l.strip()]
    numbered = [r for r in rows if r["variant"] in ("ipc_numbered", "bns_numbered")]
    if not numbered:
        raise SystemExit("No numbered paired queries. Run: python eval/paired_queries.py")

    client = qdrant()
    base = corpus_shares(client)

    print()
    print("  chance baseline (share of the index):  " +
          "   ".join(f"{c} {100*base.get(c,0):.1f}%" for c in CORPORA))
    print(f"  queries: {len(numbered)} numbered paired queries, corpus filter DISABLED")

    vectors, _meta = embed_texts([r["text"] for r in numbered])

    dominant = collections.defaultdict(collections.Counter)
    top1 = collections.defaultdict(collections.Counter)
    for row, vec in zip(numbered, vectors):
        hits = client.search(collection_name=COLLECTION, query_vector=vec,
                             limit=15, with_payload=True)
        if not hits:
            continue
        want = row["expected_corpus"]
        seen = collections.Counter((h.payload or {}).get("corpus") for h in hits)
        dominant[want][seen.most_common(1)[0][0]] += 1
        top1[want][(hits[0].payload or {}).get("corpus")] += 1

    for label, table in (("DOMINANT corpus among the top 15", dominant),
                         ("corpus of the single TOP-1 chunk", top1)):
        print()
        print(f"  {label}")
        print("  " + f"{'QUERY NAMES':<14}" + "".join(f"{c:>8}" for c in CORPORA)
              + f"{'N':>7}   {'CORRECT':^22}   CHANCE")
        print("  " + "-" * 78)
        for want in ("IPC", "BNS"):
            row = table[want]
            n = sum(row.values())
            p, lo, hi = wilson(row.get(want, 0), n)
            print("  " + f"{want:<14}" + "".join(f"{row.get(c,0):>8}" for c in CORPORA)
                  + f"{n:>7}   {100*p:5.1f}% [{100*lo:4.1f},{100*hi:5.1f}]"
                  + f"   {100*base.get(want,0):5.1f}%")

    print()
    print("  A query that NAMES a code and still lands in the other one is a")
    print("  cross-statute retrieval failure. Compare each row against its chance")
    print("  column: a value near chance means the Act name carried no signal.")


if __name__ == "__main__":
    main()
