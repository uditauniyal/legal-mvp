"""check01 -- PAIRED CHECK for exp01_retrieval.py.  Wave 2, Subagent 1.

WHY A SECOND ROUTE AT ALL
    exp01 computes every retrieval number through metrics_lib -- load_logs(),
    load_stages(), ranked_sections(), normalise_section(), same_section(),
    correctness_label(), wilson(). If any ONE of those has a defect, every
    number in results/retrieval_metrics.csv is wrong in the same direction and
    nothing inside exp01 can notice. Defect E2 in this project was exactly
    that: a headline metric returned 0.0 for its entire existence because
    "IPC Section 302" and "Section 302" were compared as strings.

    So this file recomputes the headline values WITHOUT importing metrics_lib
    at all. It reads experiments/stages.jsonl and runs/eval_*/eval_summary.jsonl
    with the json module, matches sections with its own rule, and computes its
    own Wilson interval from the algebra. Then it asserts agreement with
    results/retrieval_metrics.csv.

WHAT IS AND IS NOT INDEPENDENT
    Independent: the join, the section-matching rule, the recall arithmetic,
                 the reciprocal-rank arithmetic, the Wilson interval.
    Shared:      experiments/stages.jsonl itself (there is only one copy of
                 the re-run) and the fact that it holds 621 already-deduplicated
                 req_ids. This route does NOT re-use load_logs()'s
                 deduplication -- it takes stages.jsonl's row set as given --
                 so a dedup bug in load_logs() WOULD surface here as a row-count
                 mismatch.

TWO RANK CONVENTIONS ARE CHECKED SEPARATELY
    A first run of this file disagreed with exp01 on every k<15 cell while
    agreeing exactly at k=15. That was not a bug in either route: exp01's
    primary series ranks only chunks that CARRY a section_number (metrics_lib
    drops the others, compressing positions), while this file's natural loop
    ranks chunks AS RETRIEVED. Both are now computed here, independently, and
    each is asserted against its own series in the CSV:

        ranks_compressed  -> recall_at_k, mrr_at_k, ndcg_at_k
        ranks_positional  -> recall_at_k_positional, mrr_at_k_positional,
                             ndcg_at_k_positional

    They must be EQUAL at k=15 and the compressed one must be >= the
    positional one at every k. Both invariants are asserted, because a
    violation of either would mean the drop rule is doing something other
    than deleting list entries.

THE TWO EXTERNAL ANCHORS, from before this wave
    layman_situation, filtered_n, Recall@15  ==  9/120  = 0.075   (Wave 1)
    pooled all labelled, raw_15, Recall@15   == 327/617 = 0.5300  (GATE)
    A disagreement is a FINDING to report loudly, never something to adjust to.

ZERO API calls. Reads only; writes nothing.

Run:  ./venv/Scripts/python.exe experiments/check01_retrieval_check.py
"""
from __future__ import annotations

import csv
import glob
import json
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STAGES = ("raw_15", "reranked_15", "filtered_n")
KS = (1, 3, 5, 10, 15)
REPORT_SETS = ("generated_retrieval", "paired_recodification",
               "paired_dated_conflict", "layman_situation")

TOL = 1e-9


# ------------------------------------------------------- independent helpers

def own_wilson(k, n):
    """95% Wilson score interval, written out from the algebra rather than
    imported, so a defect in metrics_lib.wilson() cannot hide here."""
    if n == 0:
        return 0.0, 0.0, 0.0
    z = 1.959963985
    p = k / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2.0 * n)) / denom
    half = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / denom
    return p, max(0.0, centre - half), min(1.0, centre + half)


_SPLIT = re.compile(r"^\s*([A-Za-z]+)\s*(?:sec(?:tion)?s?\.?|s\.)?\s*(.+?)\s*$",
                    re.IGNORECASE)


def own_gold_key(gold):
    """'IPC Section 302' / 'IPC 302' / 'BNS 318(4)' -> ('IPC', '302').

    Own parser. Deliberately simple and deliberately NOT normalise_section():
    a shared bug cannot be caught by a shared parser.
    """
    m = _SPLIT.match(str(gold or ""))
    if not m:
        return None
    act = m.group(1).upper()
    num = re.sub(r"\s+", "", m.group(2)).upper()
    return (act, num) if num else None


def own_chunk_key(chunk):
    sn = chunk.get("section_number")
    if not sn:
        return None                      # preamble / continuation / footnote
    return (str(chunk.get("corpus") or "").upper(),
            re.sub(r"\s+", "", str(sn)).upper())


def own_first_hit_ranks(chunks, golds):
    """(compressed_rank, positional_rank) of the first chunk matching ANY gold
    section; None where there is no hit. Own loop, own equality rule (exact
    act + exact number).

    positional = the chunk's 1-based position in the list AS RETRIEVED.
    compressed = its 1-based position once chunks with no section_number have
                 been removed, which is what metrics_lib.ranked_sections()
                 hands to every metric.
    """
    keys = [g for g in (own_gold_key(x) for x in golds or []) if g]
    if not keys:
        return None, None
    seen = 0
    for pos, c in enumerate(chunks, 1):
        ck = own_chunk_key(c)
        if ck is None:
            continue                       # dropped by the compressed rule
        seen += 1
        if ck in keys:
            return seen, pos
    return None, None


# ------------------------------------------------------------------- loading

def own_load():
    """stages.jsonl x eval_summary.jsonl, joined on req_id, no metrics_lib."""
    stages = {}
    with open(os.path.join(ROOT, "experiments", "stages.jsonl"),
              encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                r = json.loads(line)
                stages[r["req_id"]] = r

    gold = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "runs", "eval_*",
                                              "eval_summary.jsonl"))):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if r.get("req_id"):
                    gold[r["req_id"]] = r          # last wins

    rows = []
    for rid, st in stages.items():
        g = gold.get(rid)
        if not g:
            continue
        golds = g.get("expected_sections") or []
        if not golds:
            continue                                # the SMOKE rows
        comp, posn = {}, {}
        for s in STAGES:
            comp[s], posn[s] = own_first_hit_ranks(st.get(s, []), golds)
        rows.append({
            "req_id": rid,
            "query_set": g.get("category"),
            "golds": golds,
            "ranks": comp,               # metrics_lib convention
            "ranks_positional": posn,    # as-retrieved convention
        })
    return rows


# -------------------------------------------------------------------- checks

def read_csv_values():
    """{(metric, query_set, stage, k): (value, n, ci_lo, ci_hi)}"""
    out = {}
    path = os.path.join(ROOT, "results", "retrieval_metrics.csv")
    with open(path, encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            key = (r["metric"], r["query_set"], r["stage"], r["k"])
            out[key] = r
    return out


def main():
    rows = own_load()
    csv_rows = read_csv_values()
    failures = []
    checked = 0

    print("INDEPENDENT ROUTE: stages.jsonl x eval_summary.jsonl, own parser, "
          "own arithmetic")
    print("rows joined with gold: %d" % len(rows))

    def subset(qs):
        return rows if qs == "ALL" else [r for r in rows if r["query_set"] == qs]

    # ---------------------------------------------------- the two anchors
    lay = subset("layman_situation")
    lay_hits = sum(1 for r in lay
                   if r["ranks"]["filtered_n"] is not None
                   and r["ranks"]["filtered_n"] <= 15)
    assert (lay_hits, len(lay)) == (9, 120), (
        "ANCHOR 1 FAILED -- layman_situation Recall@15 at filtered_n is "
        "%d/%d by the independent route. Wave 1 established 9/120 = 0.075. "
        "This is a FINDING. Do not adjust to match." % (lay_hits, len(lay)))
    print("ANCHOR 1 OK  layman filtered_n Recall@15 = %d/%d = %.4f  "
          "(Wave 1: 9/120 = 0.0750)"
          % (lay_hits, len(lay), lay_hits / len(lay)))

    pool_hits = sum(1 for r in rows
                    if r["ranks"]["raw_15"] is not None
                    and r["ranks"]["raw_15"] <= 15)
    assert (pool_hits, len(rows)) == (327, 617), (
        "ANCHOR 2 FAILED -- pooled Recall@15 at raw_15 is %d/%d by the "
        "independent route. The GATE established 327/617. This is a FINDING. "
        "Do not adjust to match." % (pool_hits, len(rows)))
    print("ANCHOR 2 OK  pooled raw_15  Recall@15 = %d/%d = %.4f  "
          "(GATE: 327/617 = 0.5300)"
          % (pool_hits, len(rows), pool_hits / len(rows)))

    # ---- both rank conventions, every Recall@k / MRR@k / nDCG@k cell
    CONVENTIONS = (("ranks", ""), ("ranks_positional", "_positional"))

    def cmp_cell(metric, qs, stage, k, mine, label="value"):
        cell = csv_rows.get((metric, qs, stage, str(k)))
        if cell is None:
            failures.append("MISSING CSV ROW %s %s %s k=%s" % (metric, qs, stage, k))
            return None
        if abs(float(mine) - float(cell[label])) > 1e-6:
            failures.append("%s %s %s k=%s %s: independent %.8f != csv %s"
                            % (metric, qs, stage, k, label, float(mine),
                               cell[label]))
        return cell

    print("\nRecall@k / MRR@k / nDCG@k, BOTH rank conventions, vs "
          "results/retrieval_metrics.csv")
    for qs in list(REPORT_SETS) + ["ALL"]:
        d = subset(qs)
        n = len(d)
        for stage in STAGES:
            for rank_key, suffix in CONVENTIONS:
                for k in KS:
                    rk = [r[rank_key][stage] for r in d]
                    hits = sum(1 for x in rk if x is not None and x <= k)
                    p, lo, hi = own_wilson(hits, n)
                    cell = cmp_cell("recall_at_k" + suffix, qs, stage, k, p)
                    if cell is not None:
                        checked += 1
                        cmp_cell("recall_at_k" + suffix, qs, stage, k, n, "n")
                        cmp_cell("recall_at_k" + suffix, qs, stage, k, lo, "ci_lo")
                        cmp_cell("recall_at_k" + suffix, qs, stage, k, hi, "ci_hi")

                    mrr = sum((1.0 / x) if (x is not None and x <= k) else 0.0
                              for x in rk) / n
                    if cmp_cell("mrr_at_k" + suffix, qs, stage, k, mrr) is not None:
                        checked += 1

                    nd = sum((1.0 / math.log2(x + 1))
                             if (x is not None and x <= k) else 0.0
                             for x in rk) / n
                    if cmp_cell("ndcg_at_k" + suffix, qs, stage, k, nd) is not None:
                        checked += 1

    # ---- invariants between the two conventions, on the raw ranks
    print("invariants -- compressed rank <= positional rank on every hit; "
          "the two agree at k=15")
    for r in rows:
        for stage in STAGES:
            a, b = r["ranks"][stage], r["ranks_positional"][stage]
            checked += 1
            if (a is None) != (b is None):
                failures.append(
                    "%s %s: one convention found a hit and the other did not "
                    "(compressed=%r positional=%r). Dropping list entries must "
                    "never change WHETHER gold is present."
                    % (r["req_id"], stage, a, b))
            elif a is not None and a > b:
                failures.append(
                    "%s %s: compressed rank %d > positional rank %d. Removing "
                    "entries can only move an item earlier." % (r["req_id"], stage, a, b))

    # -------------------- structural: cited/grounded must carry no stage or k
    print("structural -- cited/grounded must have EMPTY stage and k")
    for key, r in csv_rows.items():
        if r["metric"] == "positive_rate":
            checked += 1
            if r["stage"] != "" or r["k"] != "":
                failures.append(
                    "positive_rate %s/%s carries stage=%r k=%r; cited and "
                    "grounded are properties of the answer and must not vary "
                    "with stage or k" % (r["query_set"], r["definition"],
                                         r["stage"], r["k"]))

    # ----------------------------------------------------------- verdict
    print("\nchecks run: %d" % checked)
    if failures:
        print("\nPAIRED CHECK FAILED -- %d disagreements:" % len(failures))
        for f in failures[:40]:
            print("  " + f)
        raise SystemExit(1)
    print("PAIRED CHECK PASSED -- every Recall@k, MRR@15 and nDCG@15 cell "
          "reproduced by an independent route, and both external anchors hold.")


if __name__ == "__main__":
    main()
