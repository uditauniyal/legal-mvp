"""check11 -- independent checks on results/intervention.csv. Halts on any failure.

Route 1, recount without the shared marking function: read each run's ranked
sections straight from experiments/stages.jsonl and compare against gold with
same_section, inline. If this disagrees with exp11, correctness_label is not
doing what exp11 assumes.

Route 2, agree with a file exp11 did not produce: the 'both' rows pooled over
all three variants must equal recall_at_k_both_rows in
results/retrieval_metrics.csv (written by exp01 on 1 September), and the
baseline must equal that file's pooled dated-conflict count minus its 'both'
count.

Route 3, the design invariants: every agree_control gold is the same in both
modes, and n per variant is 33 except where a row was deliberately dropped.

    ./venv/Scripts/python.exe experiments/check11_intervention_check.py
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

from experiments.metrics_lib import (load_logs, load_stages,  # noqa: E402
                                     ranked_sections, same_section)

FAIL = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail else ""))
    if not ok:
        FAIL.append(name)


def main() -> None:
    out = pd.read_csv(ROOT / "results" / "intervention.csv")
    got = {(r.metric, r.query_set): (round(r.value * r.n), int(r.n))
           for r in out.itertuples()}

    # ---- route 1: inline recount -------------------------------------------
    var = {}
    for line in (ROOT / "eval" / "paired_dated_queryset.jsonl").read_text(
            encoding="utf-8").splitlines():
        if line.strip():
            q = json.loads(line)
            var[q["query_id"]] = q["variant"]
    logs = load_logs()
    st = load_stages()
    d = logs[logs["query_set"] == "paired_dated_conflict"]
    t = defaultdict(lambda: [0, 0])
    for r in d.to_dict("records"):
        ranked = ranked_sections(st[r["req_id"]]["raw_15"])[:15]
        gold = list(r["expected_sections"])
        hit = int(any(same_section(g, s) for g in gold for s in ranked))
        t[(var[r["query_id"]], r["intervention"])][0] += hit
        t[(var[r["query_id"]], r["intervention"])][1] += 1
    print("route 1 -- inline recount, bypassing correctness_label")
    for (v, m), (h, n) in sorted(t.items()):
        check(f"{v}/{m}", got[(f"retrieved_{m}", v)] == (h, n),
              f"exp11 {got[(f'retrieved_{m}', v)]} vs recount {(h, n)}")

    # ---- route 2: agree with retrieval_metrics.csv ------------------------
    print("route 2 -- agreement with results/retrieval_metrics.csv (exp01)")
    rm = pd.read_csv(ROOT / "results" / "retrieval_metrics.csv")
    both = rm[(rm.metric == "recall_at_k_both_rows") & (rm.stage == "raw_15")].iloc[0]
    pooled = rm[(rm.metric == "recall_at_k") & (rm.query_set == "paired_dated_conflict")
                & (rm.stage == "raw_15") & (rm.k == 15)].iloc[0]
    hb, nb = round(both.value * both.n), int(both.n)
    hp, np_ = round(pooled.value * pooled.n), int(pooled.n)
    check("pooled 'both' == recall_at_k_both_rows",
          got[("retrieved_both", "all_variants_pooled")] == (hb, nb),
          f"{got[('retrieved_both', 'all_variants_pooled')]} vs {(hb, nb)}")
    check("pooled baseline == pooled minus both",
          got[("retrieved_baseline", "all_variants_pooled")] == (hp - hb, np_ - nb),
          f"{got[('retrieved_baseline', 'all_variants_pooled')]} vs {(hp - hb, np_ - nb)}")

    # ---- route 3: design invariants ---------------------------------------
    print("route 3 -- design invariants")
    check("conflict baseline is zero in both directions",
          got[("retrieved_baseline", "conflict_bns_named")][0] == 0
          and got[("retrieved_baseline", "conflict_ipc_named")][0] == 0)
    check("control unchanged by the intervention",
          got[("retrieved_baseline", "agree_control")][0]
          == got[("retrieved_both", "agree_control")][0])
    ns = sorted(n for (metric, qs), (hits, n) in got.items()
                if qs not in ("conflict_pooled", "all_variants_pooled"))
    check("every per-variant n is 33, or 32 for the one deliberately dropped row "
          "(D0094, intervention=both)", set(ns) <= {32, 33}, f"n values {sorted(set(ns))}")

    print()
    if FAIL:
        print(f"FAILED: {len(FAIL)} -- {FAIL}")
        raise SystemExit(1)
    print("ALL CHECKS PASS")


if __name__ == "__main__":
    main()
