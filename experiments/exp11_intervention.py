"""exp11 -- the intervention result, written to a results file.

WHAT THIS IS
    On 23 August the paired dated-conflict set was run twice at commit
    302e1f8, against the same index: once with the Date Resolver and Statute
    Mapper switched off (intervention='baseline') and once switched on
    (intervention='both'). One variable changed.

    That comparison was written up in docs/results/PHASE_H.md by
    scripts/compare_runs.py -- before the September measurement library
    existed. Only the pooled 'both' figure (68/98) was ever re-marked by the
    shared library, in results/retrieval_metrics.csv. The baseline figure and
    every per-variant figure existed only as prose.

    This script re-marks the SAME stored runs with the shared library and
    writes the result as rows, so the numbers can be quoted under the project
    rule: nothing in a submitted document that is not a CSV row made by a
    re-runnable script.

WHAT THIS IS NOT
    It does not re-run the system, call any model, or change any existing
    results file. It reads runs/ (read-only) and writes one new file.

WHY THE POOLED FIGURE IS NOT THE HEADLINE
    Pooled, the set goes 29/99 -> 68/98. But all 29 baseline hits are in the
    agree_control variant, where the named code and the conduct date agree and
    the baseline was already right. On the 66 questions the intervention
    actually targets, the baseline scored zero. Quoting the pooled figure
    would understate the effect on conflicts and hide that the control is
    flat. Both are written here; the conflict rows are the ones to quote.

CORRECTNESS
    retrieved@k, k=15, stage raw_15 -- the gold section is among the fifteen
    passages returned, before reranking or the score filter. Same definition
    and stage as the existing recall_at_k_both_rows row, so the pooled rows
    here must equal it; check11 enforces that.

    ./venv/Scripts/python.exe experiments/exp11_intervention.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from experiments.metrics_lib import (correctness_label, load_logs,  # noqa: E402
                                     load_stages, wilson)

OUT = ROOT / "results" / "intervention.csv"
QSET = ROOT / "eval" / "paired_dated_queryset.jsonl"
STAGE, K, DEFN = "raw_15", 15, "retrieved@k"
VARIANTS = ("conflict_bns_named", "conflict_ipc_named", "agree_control")
MODES = ("baseline", "both")


def variant_of() -> dict[str, str]:
    out = {}
    for line in QSET.read_text(encoding="utf-8").splitlines():
        if line.strip():
            q = json.loads(line)
            out[q["query_id"]] = q["variant"]
    return out


def tally() -> dict[tuple[str, str], list[int]]:
    var = variant_of()
    logs = load_logs()
    stages = load_stages()
    d = logs[logs["query_set"] == "paired_dated_conflict"]
    t: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    for r in d.to_dict("records"):
        r["_stage"] = STAGE
        v = var.get(r["query_id"])
        m = r.get("intervention")
        if v not in VARIANTS or m not in MODES:
            raise SystemExit(f"unexpected row: query_id={r['query_id']} "
                             f"variant={v} intervention={m}")
        t[(v, m)][0] += correctness_label(r, DEFN, k=K, stages=stages)
        t[(v, m)][1] += 1
    return t


def row(metric, qs, k_hit, n, notes):
    _, lo, hi = wilson(k_hit, n)   # returns (proportion, lo, hi)
    return dict(metric=metric, query_set=qs, definition=DEFN, stage=STAGE,
                k=K, value=round(k_hit / n, 6), n=n, ci_lo=lo, ci_hi=hi,
                cluster_ci_lo="", cluster_ci_hi="",
                notes=f"{k_hit}/{n}. Wilson interval. {notes}")


def main() -> None:
    t = tally()
    rows = []
    prov = ("Re-marked by experiments/metrics_lib.py from the 23 Aug runs at "
            "commit 302e1f8 (runs/2026-08-23_0353_302e1f8, "
            "runs/2026-08-23_0408_302e1f8). One variable changed: "
            "intervention off (baseline) vs on (both).")

    for v in VARIANTS:
        for m in MODES:
            h, n = t[(v, m)]
            rows.append(row(f"retrieved_{m}", v, h, n, prov))

    # the two conflict variants pooled -- the figure to quote
    for m in MODES:
        h = sum(t[(v, m)][0] for v in VARIANTS[:2])
        n = sum(t[(v, m)][1] for v in VARIANTS[:2])
        rows.append(row(f"retrieved_{m}", "conflict_pooled", h, n,
                        "HEADLINE. conflict_bns_named + conflict_ipc_named: "
                        "the questions where the named code and the conduct "
                        "date point to different laws. " + prov))

    # all three variants pooled -- recorded so it is never mistaken for the
    # headline; must equal recall_at_k_both_rows in retrieval_metrics.csv
    for m in MODES:
        h = sum(t[(v, m)][0] for v in VARIANTS)
        n = sum(t[(v, m)][1] for v in VARIANTS)
        rows.append(row(f"retrieved_{m}", "all_variants_pooled", h, n,
                        "NOT THE HEADLINE. Includes agree_control, which holds "
                        "every baseline hit; quoting this hides that the "
                        "baseline scored zero on the conflicts. " + prov))

    pd.DataFrame(rows).to_csv(OUT, index=False)
    print(f"wrote {OUT.relative_to(ROOT)}  ({len(rows)} rows)\n")
    print(f"{'query_set':22} {'baseline':>14} {'both':>14}")
    for qs in VARIANTS + ("conflict_pooled", "all_variants_pooled"):
        b = next(r for r in rows if r["query_set"] == qs and r["metric"] == "retrieved_baseline")
        o = next(r for r in rows if r["query_set"] == qs and r["metric"] == "retrieved_both")
        fb = f"{round(b['value']*b['n'])}/{b['n']} {b['value']:.1%}"
        fo = f"{round(o['value']*o['n'])}/{o['n']} {o['value']:.1%}"
        print(f"{qs:22} {fb:>14} {fo:>14}")


if __name__ == "__main__":
    main()
