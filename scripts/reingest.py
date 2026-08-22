#!/usr/bin/env python3
"""Rebuild the vector index from the PDFs in tests/data/.

WHY A CLEAN REBUILD RATHER THAN AN UPDATE
    The live index was built by an older version of the chunking code. Its
    chunk ids use a different format, so new ids would not overwrite the old
    records -- they would sit alongside them, and the index would contain two
    incompatible generations of the same documents.

    It also contains 618 duplicate chunks (34%) and corpus tags that were
    hand-patched into the database by fix_corpus_tags.py rather than produced
    by the pipeline. None of that should survive.

WHAT CHANGED IN THE PIPELINE
    - chunk ids are deterministic, derived from (document, page, position), so
      a future re-ingest REPLACES rather than duplicates
    - corpus tags come from ingest/registry.py, an explicit lookup, not from
      keyword guessing that left the IPC 95% "Unknown"
    - chunks follow section boundaries, so a provision arrives whole
    - table-of-contents listings are dropped

COST
    ~293k tokens at $0.02 per million = about $0.006 (half a rupee).

USAGE
    python scripts/reingest.py --dry-run     count only, write nothing
    python scripts/reingest.py               rebuild for real
"""

from __future__ import annotations

import argparse
import collections
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from clients.qdrant_client import COLLECTION, ensure_collection, qdrant  # noqa: E402
from ingest.chunk import chunk_page, drop_shadowed_fragments, tokens  # noqa: E402
from ingest.extract import extract_text_pdf_bytes  # noqa: E402
from ingest.index import index_chunks  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tests" / "data"


def build_chunks() -> list[dict]:
    chunks: list[dict] = []
    for pdf in sorted(DATA.glob("*.pdf")):
        pages = extract_text_pdf_bytes(pdf.read_bytes())
        made = []
        for page, text in pages:
            made.extend(chunk_page(pdf.name, page, text))
        print(f"  {pdf.name[:46]:<48}{len(pages):>4} pages  ->{len(made):>5} chunks")
        chunks.extend(made)

    # Cross-page pass. Cannot run inside chunk_page(), which sees one page at
    # a time and therefore cannot know that a 15-word entry on page 4 is
    # shadowed by the 215-word provision on page 49.
    chunks, dropped = drop_shadowed_fragments(chunks)
    if dropped:
        print()
        print(f"  dropped {len(dropped)} contents entries shadowed by the real provision:")
        for d in sorted(dropped, key=lambda c: (c["corpus"], c["page"]))[:12]:
            preview = " ".join(d["text"].split())[:62]
            print(f"    {d['corpus']:<6}s.{str(d['section_number']):<6}p.{d['page']:<5}{preview}")
        if len(dropped) > 12:
            print(f"    ... and {len(dropped) - 12} more")
    return chunks


def report(chunks: list[dict]) -> None:
    by_corpus = collections.Counter(c["corpus"] for c in chunks)
    total_tokens = sum(tokens(c["text"]) for c in chunks)
    ids = collections.Counter(c["chunk_id"] for c in chunks)
    print()
    print(f"  total chunks         {len(chunks)}")
    print(f"  duplicate chunk ids  {sum(1 for v in ids.values() if v > 1)}   (must be 0)")
    print(f"  approx tokens        {total_tokens:,}")
    print(f"  embedding cost       ~${total_tokens / 1e6 * 0.02:.4f}")
    print()
    for corpus, n in by_corpus.most_common():
        print(f"    {corpus:<6}{n:>6}  {100 * n / len(chunks):5.1f}%")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="count only, write nothing")
    args = ap.parse_args()

    print("Building chunks from", DATA)
    chunks = build_chunks()
    report(chunks)

    if args.dry_run:
        print("\ndry run — nothing written")
        return

    client = qdrant()

    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION in existing:
        info = client.get_collection(COLLECTION)
        print(f"\n  deleting existing collection '{COLLECTION}' "
              f"({info.points_count} points, built by an older pipeline)")
        client.delete_collection(COLLECTION)

    ensure_collection(client)
    print(f"  created empty collection '{COLLECTION}'")

    print(f"\n  embedding and indexing {len(chunks)} chunks…")
    started = time.time()
    index_chunks(chunks)
    elapsed = time.time() - started

    final = client.get_collection(COLLECTION)
    print(f"  done in {elapsed:.0f}s — {final.points_count} points indexed")

    if final.points_count != len(chunks):
        print(f"  WARNING: expected {len(chunks)} points, found {final.points_count}")


if __name__ == "__main__":
    main()
