#!/usr/bin/env python3
"""check02 -- PAIRED CHECK for exp02_routing.py.

    ./venv/Scripts/python.exe experiments/check02_routing_check.py

WHY A SECOND ROUTE
    exp02 reads chunk corpora out of experiments/stages.jsonl, which is a
    REPLAY: Wave 0 re-ran retrieval against Qdrant, replaying each query's
    RECORDED corpus filter, in order to capture the `section_number` the
    original logs never stored.  If that replay drifted from the original
    runs -- a changed index, a changed filter, a changed k -- every number in
    exp02 would be wrong in a way no amount of internal consistency would
    reveal.

    So the headline value is re-derived from a source exp02 never touches:
    the ORIGINAL server logs, runs/*/queries.jsonl, field
    `retrieval.chunks[*].corpus`.

    Those stored chunks are the POST-adaptive-filter survivors (SCHEMA.md 4b:
    len(chunks) < len(scores_raw) on 467 of 859 rows), so the original logs
    can only be compared against the `filtered_n` stage.  raw_15 has no second
    source and is therefore NOT checkable -- that is stated, not hidden.

WHAT IS ASSERTED
    1. layman CrPC share of filtered_n chunks, stages.jsonl vs original logs
    2. the same for all four books
    3. index counts sum to 1,899 over exactly four books
    4. the over-representation ratio written to the CSV equals the one
       re-derived here from the original logs

    A DISAGREEMENT IS A FINDING, not a thing to paper over.  This script
    prints both numbers before it asserts, so a failure shows its working.
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from experiments.metrics_lib import load_logs, load_stages  # noqa: E402

CORPORA = ["IPC", "BNS", "CRPC", "CPA"]
CSV = ROOT / "results" / "routing_confusion.csv"
TOL = 0.005   # half a percentage point on a share


def original_log_chunks():
    """{req_id: [corpus, ...]} straight from the untouched server logs.

    Deliberately NOT via load_logs(), which does not carry chunk records.
    req_id is unique across all 859 rows, so last-wins is a no-op here.
    """
    out = {}
    for f in (ROOT / "runs").rglob("queries.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            rid = rec.get("req_id")
            if not rid:
                continue
            chunks = (rec.get("retrieval") or {}).get("chunks") or []
            out[rid] = [c.get("corpus") for c in chunks]
    return out


def main():
    failures = []
    df = load_logs()
    stages = load_stages()
    lay = df[df.query_set == "layman_situation"]
    print("layman queries: %d" % len(lay))

    orig = original_log_chunks()
    missing = [q for q in lay.req_id if q not in orig]
    if missing:
        raise SystemExit("STOP: %d layman req_ids missing from runs/*/"
                         "queries.jsonl" % len(missing))

    a = collections.Counter()   # route 1: stages.jsonl, filtered_n
    b = collections.Counter()   # route 2: original logs, retrieval.chunks
    n_len_mismatch = 0
    for rid in lay.req_id:
        ca = [c.get("corpus") for c in stages[rid]["filtered_n"]]
        cb = orig[rid]
        if len(ca) != len(cb):
            n_len_mismatch += 1
        a.update(ca)
        b.update(cb)

    ta, tb = sum(a.values()), sum(b.values())
    print("\nCHECK 1+2 -- layman retrieval share, filtered_n stage")
    print("   route 1  experiments/stages.jsonl  : %d chunks" % ta)
    print("   route 2  runs/*/queries.jsonl      : %d chunks" % tb)
    print("   per-query chunk-count mismatches   : %d of %d"
          % (n_len_mismatch, len(lay)))
    print("\n   %-6s %12s %12s %10s" % ("BOOK", "route 1", "route 2", "delta"))
    for c in CORPORA:
        sa, sb = a[c] / ta, b[c] / tb
        flag = "" if abs(sa - sb) <= TOL else "   <== DISAGREEMENT"
        print("   %-6s %11.4f %12.4f %10.4f%s" % (c, sa, sb, sa - sb, flag))
        if abs(sa - sb) > TOL:
            failures.append("share_%s: stages=%.4f logs=%.4f" % (c, sa, sb))

    crpc_a, crpc_b = a["CRPC"] / ta, b["CRPC"] / tb
    assert abs(crpc_a - crpc_b) <= TOL, (
        "FINDING: CrPC layman share disagrees between the replay and the "
        "original logs -- stages.jsonl %.4f vs runs/*/queries.jsonl %.4f. "
        "Do NOT publish either until this is explained." % (crpc_a, crpc_b))
    print("\n   OK: CrPC share agrees, %.4f vs %.4f (|delta| <= %.3f)"
          % (crpc_a, crpc_b, TOL))

    # ------------------------------------------------ CHECK 3: index census
    from clients.qdrant_client import COLLECTION, qdrant
    client = qdrant()
    counts, offset = collections.Counter(), None
    while True:
        pts, offset = client.scroll(collection_name=COLLECTION, limit=1000,
                                    offset=offset, with_payload=True,
                                    with_vectors=False)
        for p in pts:
            counts[(p.payload or {}).get("corpus")] += 1
        if offset is None:
            break
    total = sum(counts.values())
    print("\nCHECK 3 -- index census: %d points, books %s"
          % (total, dict(counts)))
    assert total == 1899, "index holds %d points, expected 1899" % total
    assert set(counts) == set(CORPORA), (
        "index books are %s, expected exactly %s" % (sorted(counts), CORPORA))
    print("   OK: 1,899 points across exactly IPC/BNS/CRPC/CPA")

    # ---------------------------- CHECK 4: CSV ratio vs independent re-derive
    csv = pd.read_csv(CSV)
    row = csv[(csv.metric == "over_representation_ratio_CRPC")
              & (csv.stage == "filtered_n")]
    assert len(row) == 1, "expected exactly one CRPC filtered_n ratio row"
    published = float(row.iloc[0]["value"])
    rederived = crpc_b / (counts["CRPC"] / total)
    print("\nCHECK 4 -- over-representation ratio, CrPC, filtered_n")
    print("   published in routing_confusion.csv : %.4fx" % published)
    print("   re-derived from original logs      : %.4fx" % rederived)
    assert abs(published - rederived) <= 0.02, (
        "FINDING: published ratio %.4f != independently re-derived %.4f"
        % (published, rederived))
    print("   OK: agree within 0.02x")

    print("\nNOT CHECKABLE: the raw_15 stage. The original logs stored only "
          "post-adaptive-filter survivors, so no second source for the "
          "pre-filter 15 exists. Reported, not hidden.")

    if failures:
        raise SystemExit("FAILURES: " + "; ".join(failures))
    print("\nALL CHECKS PASSED")


if __name__ == "__main__":
    main()
