"""Does the composite still lose to max_score once the gap sign is FIXED?

The deployed confidence score (agents/retriever.py:137-142) is

    gap_penalty = min(score_gap / 0.3, 1.0)
    confidence  = 0.55*top_k_mean + 0.15*(1.0 - gap_penalty) + 0.30*entity_coverage

The middle term is INVERTED: a large gap between the best and second-best
retrieved chunk is evidence of a clear winner, but the deployed form PENALISES
it. Measured alone that term scores AUROC 0.270 -- below 0.5, i.e. pointing the
wrong way -- while the raw gap scores 0.730.

So the Wave 2 finding, "the engineered composite loses to a single raw
similarity", might be an artefact of that one bug rather than a property of the
blend. This script settles it.

    Q1  corrected composite at the DEPLOYED weights 55/15/30, vs max_score
    Q2  corrected signals at their BEST weighting, vs max_score, held out
        (a selected maximum flatters itself, so Q2 is reported on a test split
         the weight search never saw)

NOTHING DEPLOYED IS CHANGED. This is analysis. The deployed formula, the
weights 55/15/30 and the tiers 0.55/0.38 all stand.

    ./venv/Scripts/python.exe experiments/exp09_corrected_composite.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from experiments.metrics_lib import (
    N_BOOT, SEED, auroc, auroc_bootstrap_ci, correctness_label, load_logs,
    load_stages, paired_bootstrap_auroc_diff,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "corrected_composite.csv"


def gap_penalty(score_gap: np.ndarray) -> np.ndarray:
    return np.minimum(score_gap / 0.3, 1.0)


def deployed(tkm, gap, ec):
    """Exactly agents/retriever.py, clamp and rounding included."""
    c = 0.55 * tkm + 0.15 * (1.0 - gap_penalty(gap)) + 0.30 * ec
    return np.round(np.minimum(c, 1.0), 4)


def corrected(tkm, gap, ec):
    """The same, with the gap term's sign fixed. Weights unchanged."""
    c = 0.55 * tkm + 0.15 * gap_penalty(gap) + 0.30 * ec
    return np.round(np.minimum(c, 1.0), 4)


def main() -> None:
    df = load_logs()
    stages = load_stages()
    df = df[df["expected_sections"].map(len) > 0].copy()
    df = df[df["top_k_mean"].notna() & df["score_gap"].notna()
            & df["entity_coverage"].notna() & df["max_score"].notna()].copy()

    tkm = df["top_k_mean"].to_numpy(float)
    gap = df["score_gap"].to_numpy(float)
    ec = df["entity_coverage"].to_numpy(float)
    mx = df["max_score"].to_numpy(float)
    logged = df["composite"].to_numpy(float)

    # ---- GATE: the reconstruction must reproduce the logged score ----------
    recon = deployed(tkm, gap, ec)
    dev = np.abs(recon - logged)
    print("=" * 76)
    print("RECONSTRUCTION CHECK -- if this fails, nothing below means anything")
    print("=" * 76)
    print(f"  rows                     {len(df)}")
    print(f"  max |recon - logged|     {dev.max():.3e}")
    print(f"  rows off by > 1e-3       {(dev > 1e-3).sum()}")
    if dev.max() > 1e-3:
        print("\n  RECONSTRUCTION FAILED. Stopping.")
        sys.exit(1)
    print("  PASS -- the deployed formula is reproduced.\n")

    corr = corrected(tkm, gap, ec)
    print(f"  corrected vs deployed: identical on "
          f"{(np.abs(corr - recon) < 1e-9).sum()} of {len(df)} rows "
          f"(they coincide only where gap_penalty == 0.5)\n")

    labels = {
        "retrieved@15 (raw_15)": np.array(
            [correctness_label({**r, "_stage": "raw_15"}, "retrieved@k", k=15,
                               stages=stages) for _, r in df.iterrows()]),
        "cited (logged)": np.array(
            [correctness_label(r, "cited") for _, r in df.iterrows()]),
        "grounded": np.array(
            [correctness_label(r, "grounded") for _, r in df.iterrows()]),
    }

    scores = {"composite_deployed": recon,
              "composite_corrected": corr,
              "max_score": mx}

    clusters = df["pair_id"].fillna("_none_").to_numpy()
    rows = []

    for dname, y in labels.items():
        print("=" * 76)
        print(f"{dname}    n={len(y)}   positives={int(y.sum())}")
        print("=" * 76)
        if len(set(y)) < 2:
            print("  SKIPPED -- only one class present\n")
            continue

        for sname, s in scores.items():
            pt, lo, hi = auroc_bootstrap_ci(s, y, n_boot=N_BOOT, seed=SEED)
            _, clo, chi = auroc_bootstrap_ci(s, y, n_boot=N_BOOT, seed=SEED,
                                             cluster_ids=clusters)
            print(f"  {sname:<22} AUROC {pt:.4f}  "
                  f"naive [{lo:.4f}, {hi:.4f}]  clustered [{clo:.4f}, {chi:.4f}]")
            rows.append(dict(metric="auroc", query_set="ALL", definition=dname,
                             stage="raw_15", k=15, value=pt, n=len(y),
                             ci_lo=lo, ci_hi=hi, cluster_ci_lo=clo,
                             cluster_ci_hi=chi,
                             notes=f"score={sname}; positives={int(y.sum())}"))

        print()
        for a, b in [("composite_corrected", "max_score"),
                     ("composite_corrected", "composite_deployed"),
                     ("composite_deployed", "max_score")]:
            d = paired_bootstrap_auroc_diff(scores[a], scores[b], y,
                                            n_boot=N_BOOT, seed=SEED)
            verdict = ("A WORSE" if d["ci_hi"] < 0 else
                       "A BETTER" if d["ci_lo"] > 0 else
                       "NO DIFFERENCE ESTABLISHED (interval contains 0)")
            print(f"  {a} - {b}:  {d['diff']:+.4f} "
                  f"[{d['ci_lo']:+.4f}, {d['ci_hi']:+.4f}]  p={d['p_two_sided']:.4f}"
                  f"   -> {verdict}")
            rows.append(dict(metric="auroc_paired_diff", query_set="ALL",
                             definition=dname, stage="raw_15", k=15,
                             value=d["diff"], n=len(y), ci_lo=d["ci_lo"],
                             ci_hi=d["ci_hi"], cluster_ci_lo="",
                             cluster_ci_hi="",
                             notes=f"{a} minus {b}; p={d['p_two_sided']:.4f}; {verdict}"))
        print()

    # ---- Q2: best weighting of the CORRECTED signals, held out -------------
    print("=" * 76)
    print("Q2  best weighting of the CORRECTED signals, 60/40 stratified split")
    print("    (a selected maximum flatters itself, so only the TEST value counts)")
    print("=" * 76)
    grid = [(a / 20, b / 20, 1 - a / 20 - b / 20)
            for a in range(21) for b in range(21 - a)]
    rng = np.random.default_rng(SEED)
    gp = gap_penalty(gap)

    for dname, y in labels.items():
        if len(set(y)) < 2:
            continue
        tr = np.zeros(len(y), bool)
        for cls in (0, 1):
            idx = np.where(y == cls)[0]
            tr[rng.choice(idx, int(round(0.6 * len(idx))), replace=False)] = True
        te = ~tr
        best, bw = -1.0, None
        for w in grid:
            v = auroc(w[0] * tkm[tr] + w[1] * gp[tr] + w[2] * ec[tr], y[tr])
            if v == v and v > best:
                best, bw = v, w
        test = auroc(bw[0] * tkm[te] + bw[1] * gp[te] + bw[2] * ec[te], y[te])
        mx_te = auroc(mx[te], y[te])
        d = paired_bootstrap_auroc_diff(
            bw[0] * tkm[te] + bw[1] * gp[te] + bw[2] * ec[te], mx[te], y[te],
            n_boot=N_BOOT, seed=SEED)
        print(f"  {dname}")
        print(f"    train argmax weights (tkm/gap/ec) = "
              f"{bw[0]:.2f}/{bw[1]:.2f}/{bw[2]:.2f}   train AUROC {best:.4f}")
        print(f"    TEST  n={te.sum()}  corrected {test:.4f}   max_score {mx_te:.4f}   "
              f"diff {d['diff']:+.4f} [{d['ci_lo']:+.4f}, {d['ci_hi']:+.4f}] "
              f"p={d['p_two_sided']:.4f}")
        rows.append(dict(metric="auroc_corrected_bestweights_test", query_set="ALL",
                         definition=dname, stage="raw_15", k=15, value=test,
                         n=int(te.sum()), ci_lo="", ci_hi="", cluster_ci_lo="",
                         cluster_ci_hi="",
                         notes=(f"train argmax {bw[0]:.2f}/{bw[1]:.2f}/{bw[2]:.2f}; "
                                f"train AUROC {best:.4f}; max_score on same test "
                                f"{mx_te:.4f}; paired diff {d['diff']:+.4f} "
                                f"[{d['ci_lo']:+.4f},{d['ci_hi']:+.4f}] "
                                f"p={d['p_two_sided']:.4f}")))
    print()

    cols = ["metric", "query_set", "definition", "stage", "k", "value", "n",
            "ci_lo", "ci_hi", "cluster_ci_lo", "cluster_ci_hi", "notes"]
    pd.DataFrame(rows)[cols].to_csv(OUT, index=False)
    print(f"wrote {OUT}  ({len(rows)} rows)")


if __name__ == "__main__":
    main()
