#!/usr/bin/env python3
"""Compare two evaluation runs of the SAME query set under different modes.

WHY A SEPARATE SCRIPT FROM analyze_eval.py
    analyze_eval.py describes ONE configuration. This one answers a different
    question: did changing exactly one thing help, and by how much?

    Keeping them apart matters because the comparison needs a guard the
    description does not: both runs must cover the same query_ids, or the
    "delta" is partly a difference in which questions were asked.

WHAT COUNTS AS A RESULT
    Three numbers per variant, and the third is the one that decides it:

        baseline    what Phase G's pipeline did
        + mapper    what the intervention did
        delta       the difference, with a 95% interval on each side

    A delta whose intervals overlap heavily is not a result at n=33, however
    large the point estimate looks.

THE CONTROL IS NOT OPTIONAL
    agree_control queries name a code the date agrees with, so the mapper
    should change nothing. If the control moves, the intervention has learned
    a preference rather than a rule, and the conflict numbers cannot be
    trusted.
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"

from core.citations import extract_provisions, same_provision  # noqa: E402

import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location("az", ROOT / "scripts" / "analyze_eval.py")
az = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(az)


def wilson(k, n):
    if n == 0:
        return 0.0, 0.0, 0.0
    z = 1.959963985
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def pct(k, n):
    p, lo, hi = wilson(k, n)
    return f"{100*p:5.1f}% [{100*lo:4.1f},{100*hi:5.1f}]" if n else "     -      "


def load(run_dir: Path, server: dict) -> dict[str, dict]:
    """query_id -> joined row, deduplicated (last write wins)."""
    out = {}
    for row in az.load_jsonl(run_dir / "eval_summary.jsonl"):
        rec = server.get(row.get("req_id") or "")
        if rec:
            out[row["query_id"]] = {"gold": row, "rec": rec}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", type=Path, required=True)
    ap.add_argument("--intervention", type=Path, required=True)
    ap.add_argument("--md", type=Path)
    args = ap.parse_args()

    server = az.load_server_records()
    a = load(args.baseline, server)
    b = load(args.intervention, server)

    shared = sorted(set(a) & set(b))
    lines = []

    def out(s=""):
        print(s)
        lines.append(s)

    out("=" * 96)
    out("  PHASE H — baseline vs intervention")
    out("=" * 96)
    out()
    out(f"  baseline      {args.baseline.name}  ({len(a)} rows)")
    out(f"  intervention  {args.intervention.name}  ({len(b)} rows)")
    out(f"  compared on   {len(shared)} query_ids present in BOTH")
    if len(shared) < max(len(a), len(b)):
        out(f"  NOTE: {max(len(a), len(b)) - len(shared)} rows appear in only one run "
            f"and are excluded — a delta over different questions is not a delta")
    if not shared:
        return

    modes = {m: collections.Counter(
        r["rec"].get("date", {}).get("mode") for r in d.values())
        for m, d in (("baseline", a), ("intervention", b))}
    out(f"  modes recorded  baseline={dict(modes['baseline'])}  "
        f"intervention={dict(modes['intervention'])}")

    def measure(rows, qids, fn):
        return sum(1 for q in qids if fn(rows[q])), len(qids)

    def gold_ret(r):
        return az.gold_retrieved(r["gold"]["expected_sections"], az.chunk_refs(r["rec"]), False)

    def gold_cit(r):
        return az.gold_cited(r["gold"]["expected_sections"], r["rec"])

    def wrong_era_ret(r):
        return az.gold_retrieved(r["gold"].get("wrong_era_sections") or [],
                                 az.chunk_refs(r["rec"]), False)

    def wrong_era_cit(r):
        return az.gold_cited(r["gold"].get("wrong_era_sections") or [], r["rec"])

    def corpus_ok(r):
        want = set(r["gold"].get("expected_corpora") or [])
        rc = az.retrieved_corpora(r["rec"])
        return bool(rc) and rc.most_common(1)[0][0] in want

    variants = sorted({a[q]["gold"].get("variant", "?") for q in shared})

    for title, fn in (
        ("GOLD PROVISION RETRIEVED  (the code the DATE selects)", gold_ret),
        ("GOLD PROVISION CITED", gold_cit),
        ("CORRECT CORPUS DOMINATES", corpus_ok),
        ("WRONG-ERA PROVISION RETRIEVED  (lower is better)", wrong_era_ret),
        ("WRONG-ERA PROVISION CITED      (lower is better)", wrong_era_cit),
    ):
        out()
        out("-" * 96)
        out(f"  {title}")
        out("-" * 96)
        out(f"  {'VARIANT':<22}{'N':>4}   {'BASELINE':^22}   {'+ INTERVENTION':^22}   {'DELTA':>9}")
        for v in variants:
            qids = [q for q in shared if a[q]["gold"].get("variant") == v]
            if not qids:
                continue
            ka, n = measure(a, qids, fn)
            kb, _ = measure(b, qids, fn)
            out(f"  {v:<22}{n:>4}   {pct(ka,n):^22}   {pct(kb,n):^22}   "
                f"{100*(kb-ka)/n:>+8.1f}pp")

    out()
    out("  Deltas are percentage points on the same queries. Read the two")
    out("  intervals, not the delta alone: at n=33 they are roughly +/-15 points")
    out("  wide, so a small delta with overlapping intervals is not a result.")

    if args.md:
        args.md.parent.mkdir(parents=True, exist_ok=True)
        args.md.write_text("```\n" + "\n".join(lines) + "\n```\n", encoding="utf-8")
        print(f"\n  written to {args.md}")


if __name__ == "__main__":
    main()
