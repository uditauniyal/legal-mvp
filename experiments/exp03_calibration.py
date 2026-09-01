"""exp03 -- CALIBRATION OF THE CONFIDENCE SCORE.  Wave 2, Subagent 3.

WHAT THIS ASKS
    When the system says 0.72, is it right 72% of the time?

    That question only makes sense for a number that CLAIMS to be a
    probability. This system's `composite` does not. It is

        composite = 0.55*top_k_mean + 0.15*score_gap + 0.30*entity_coverage

    a weighted blend of cosine similarities and a coverage ratio. Nothing in
    that formula estimates P(correct). So every calibration number below is
    measuring a gap that the score never promised to close. That is not a
    reason to skip the measurement -- it is the reason to REPORT it, because
    the score is nonetheless displayed to a user and thresholded into
    HIGH/MEDIUM/LOW tiers as though it meant something probabilistic.

    See results/_explain_w2_s3.md section 5 for how to state this in the paper
    without either overclaiming or hiding it.

WHAT IS COMPUTED
    For TWO scores -- `composite` (the deployed blend) and `max_score` (the
    raw top cosine similarity, the simplest possible baseline) --
    under ALL THREE correctness definitions:

        reliability bins    quantile (equal-mass), 10 bins
        ECE                 with a 95% bootstrap CI, iid AND pair-clustered
        Brier               with a 95% bootstrap CI, iid AND pair-clustered
        risk-coverage       AURC, and coverage achievable at 10% risk
        Platt scaling       60/40 STRATIFIED split, ECE before/after,
                            evaluated ON THE TEST HALF ONLY

    Reporting post-scaling ECE on the data the scaler was fitted on would be
    circular -- the fit minimises exactly the miscalibration you would then
    report. The train half is used to fit and is never scored.

WHAT IS NOT CHANGED
    The 55/15/30 weights and the 0.55/0.38 tier thresholds are NOT touched,
    read only. They were fixed in February 2026, before a single retrieval
    score had ever been logged, which is why the numbers here can be read as a
    measurement of the system rather than a result of tuning against the
    evaluation set. Nothing in this file writes to any production path.

PAIRED CHECK
    experiments/check03_calibration_check.py re-derives ECE, Brier and
    coverage@10%-risk by independent routes and asserts agreement.

EVERY METRIC COMES FROM experiments/metrics_lib.py. Nothing is reimplemented.
The bootstrap is metrics_lib.cluster_bootstrap() in both modes: with a
unique-per-row cluster column it IS the ordinary iid row bootstrap; with
pair_id it resamples situations. No second bootstrap was written.

ZERO API calls. Reads runs/ and experiments/stages.jsonl; writes only
results/calibration.csv and results/reliability_diagram.png.

Run:  ./venv/Scripts/python.exe experiments/exp03_calibration.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")            # no display on this machine
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.metrics_lib import (  # noqa: E402
    SEED, N_BOOT, load_logs, load_stages, correctness_label,
    reliability_bins, ece, brier, platt_scale,
    risk_coverage_curve, aurc, coverage_at_risk, cluster_bootstrap,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_CSV = ROOT / "results" / "calibration.csv"
OUT_PNG = ROOT / "results" / "reliability_diagram.png"

N_BINS = 10
BINNING = "quantile"          # equal-mass; stated in the figure caption
RISK_LEVEL = 0.10
TRAIN_FRAC = 0.60             # 60/40, stratified on the label

SCORES = ["composite", "max_score"]

# (definition, k, stage-label recorded in the `stage` column, note)
#
# `stage` means: the pipeline stage at which the LABEL is defined.
#   retrieved@k -> raw_15, the stage the gate established its 327 positives on
#   cited/grounded -> the answer stage; there is no retrieval stage for them
# The SCORE is always the deployed pipeline's confidence, in every row.
DEFS = [
    ("retrieved@k", 15, "raw_15",
     "gold section among Qdrant's top 15, before rerank or filter"),
    ("cited", "", "answer",
     "gold section appears among the answer's citations"),
    ("grounded", "", "answer",
     "every citation in the answer was supported (ungrounded_rate == 0)"),
]


# ---------------------------------------------------------------- data

def build():
    """The 617 gold-labelled rows, with a 0/1 label per definition."""
    logs = load_logs()
    stages = load_stages()

    d = logs[logs["expected_sections"].apply(len) > 0].reset_index(drop=True)
    recs = d.to_dict("records")

    for definition, k, stage, _ in DEFS:
        col = "y_" + definition.replace("@", "_at_")
        kk = k if k != "" else 10
        d[col] = [
            correctness_label({**r, "_stage": stage if stage != "answer"
                               else "filtered_n"}, definition, kk, stages)
            for r in recs
        ]

    # A cluster id that is unique per row. cluster_bootstrap() over this is
    # exactly the ordinary iid row bootstrap -- clusters of size one. Doing it
    # this way means ONE bootstrap implementation exists in this project.
    d["_row_id"] = np.arange(len(d))
    return d


def ycol(definition):
    return "y_" + definition.replace("@", "_at_")


# ---------------------------------------------------------------- split

def stratified_split(labels, train_frac=TRAIN_FRAC, seed=SEED):
    """60/40 split that PRESERVES the positive rate in both halves.

    Stratified = the positives and the negatives are each split 60/40
    separately, then recombined. Without it, a random split of a set with 27
    positives out of 617 can easily hand the test half almost no positives at
    all, and ECE on a half with no positives is meaningless.

    Returns (train_idx, test_idx) as integer arrays.
    """
    y = np.asarray(labels, int)
    rng = np.random.default_rng(seed)
    tr, te = [], []
    for cls in (0, 1):
        idx = np.flatnonzero(y == cls)
        rng.shuffle(idx)
        cut = int(round(train_frac * len(idx)))
        tr.append(idx[:cut])
        te.append(idx[cut:])
    return np.sort(np.concatenate(tr)), np.sort(np.concatenate(te))


# ---------------------------------------------------------------- reporting

def _fmt(v):
    if v is None or v == "":
        return ""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    return "" if np.isnan(f) else round(f, 6)


def row(metric, query_set, definition, stage, k, value, n,
        ci_lo="", ci_hi="", cci_lo="", cci_hi="", notes=""):
    return {
        "metric": metric, "query_set": query_set, "definition": definition,
        "stage": stage, "k": k, "value": _fmt(value), "n": n,
        "ci_lo": _fmt(ci_lo), "ci_hi": _fmt(ci_hi),
        "cluster_ci_lo": _fmt(cci_lo), "cluster_ci_hi": _fmt(cci_hi),
        "notes": notes,
    }


def boot_both(d, stat_fn):
    """(point, iid_lo, iid_hi, cluster_lo, cluster_hi).

    Two intervals, deliberately. The iid one treats all 617 rows as
    independent; they are not -- 617 rows cover 177 pair_ids, i.e. the same
    situation reappears under several phrasings and under two date
    conditions. The pair-clustered interval resamples situations and is the
    one to quote. Reporting both makes the difference visible instead of
    arguing about it.
    """
    point, lo, hi = cluster_bootstrap(d, stat_fn, "_row_id", N_BOOT, SEED)
    _, clo, chi = cluster_bootstrap(d, stat_fn, "pair_id", N_BOOT, SEED)
    return point, lo, hi, clo, chi


# ---------------------------------------------------------------- main

def main():
    d = build()
    n_all = len(d)
    out = []

    print("rows: %d gold-labelled (of %d loaded, deduplicated)" % (n_all, n_all))
    print("pair_id clusters: %d" % d["pair_id"].nunique())
    print()

    # ---- provenance and the label counts this whole file rests on
    out.append(row("n_rows_analysed", "ALL", "", "", "", n_all, n_all,
                   "", "", "", "",
                   "load_logs() gold-labelled rows; already deduplicated by "
                   "the loader; %d pair_id clusters"
                   % d["pair_id"].nunique()))
    for definition, k, stage, note in DEFS:
        pos = int(d[ycol(definition)].sum())
        out.append(row("n_positives", "ALL", definition, stage, k, pos, n_all,
                       "", "", "", "",
                       "base rate = %.4f; %s" % (pos / n_all, note)))
        print("positives  %-12s stage=%-8s  %3d / %d  (base rate %.4f)"
              % (definition, stage, pos, n_all, pos / n_all))
    print()

    # ---- per (score, definition)
    for score in SCORES:
        s_note = ("deployed composite = 0.55*top_k_mean + 0.15*score_gap + "
                  "0.30*entity_coverage" if score == "composite"
                  else "raw top cosine similarity from Qdrant, no blending")
        for definition, k, stage, dnote in DEFS:
            y = d[ycol(definition)].values
            s = d[score].values
            base = "score=%s (%s)" % (score, s_note)

            # ---- reliability bins, quantile
            b = reliability_bins(s, y, N_BINS, BINNING)
            for _, r in b.iterrows():
                out.append(row(
                    "reliability_bin_accuracy", "ALL", definition, stage, k,
                    r["accuracy"], int(r["n"]), "", "", "", "",
                    "%s; binning=%s(%d bins); bin=%d; edges=[%.4f,%.4f]; "
                    "mean_score=%.6f; gap=score-accuracy=%.6f"
                    % (base, BINNING, N_BINS, int(r["bin"]), r["lo"], r["hi"],
                       r["mean_score"], r["gap"])))

            # ---- ECE
            p, lo, hi, clo, chi = boot_both(
                d, lambda x, _s=score, _y=ycol(definition):
                ece(x[_s].values, x[_y].values, N_BINS, BINNING))
            out.append(row("ece", "ALL", definition, stage, k, p, n_all,
                           lo, hi, clo, chi,
                           "%s; binning=%s(%d bins); full sample, no split; "
                           "%d-resample percentile bootstrap, seed=%d; "
                           "ci_* iid rows, cluster_ci_* resamples pair_id"
                           % (base, BINNING, N_BINS, N_BOOT, SEED)))
            print("ECE    %-10s %-12s %.4f  [%.4f,%.4f] iid  "
                  "[%.4f,%.4f] clustered" % (score, definition, p, lo, hi, clo, chi))

            # ---- Brier
            p, lo, hi, clo, chi = boot_both(
                d, lambda x, _s=score, _y=ycol(definition):
                brier(x[_s].values, x[_y].values))
            out.append(row("brier", "ALL", definition, stage, k, p, n_all,
                           lo, hi, clo, chi,
                           "%s; mean squared error between score and outcome; "
                           "%d-resample percentile bootstrap, seed=%d; "
                           "ci_* iid rows, cluster_ci_* resamples pair_id"
                           % (base, N_BOOT, SEED)))
            print("Brier  %-10s %-12s %.4f  [%.4f,%.4f] iid  "
                  "[%.4f,%.4f] clustered" % (score, definition, p, lo, hi, clo, chi))

            # ---- risk-coverage
            out.append(row("aurc", "ALL", definition, stage, k,
                           aurc(s, y), n_all, "", "", "", "",
                           "%s; area under the risk-coverage curve, lower is "
                           "better; no CI computed (not requested)" % base))
            cov = coverage_at_risk(s, y, RISK_LEVEL)
            out.append(row("coverage_at_risk_%.2f" % RISK_LEVEL, "ALL",
                           definition, stage, k, cov, n_all, "", "", "", "",
                           "%s; largest fraction answerable while error rate "
                           "stays <= %.0f%%; 0.0 means NO threshold achieves "
                           "it" % (base, 100 * RISK_LEVEL)))
            rc = risk_coverage_curve(s, y)
            out.append(row("risk_at_full_coverage", "ALL", definition, stage,
                           k, float(rc["risk"].iloc[-1]), n_all, "", "", "", "",
                           "%s; error rate answering everything = 1 - base "
                           "rate; the number selective prediction must beat"
                           % base))
            print("RC     %-10s %-12s AURC=%.4f  cov@%.0f%%risk=%.4f  "
                  "risk@full=%.4f"
                  % (score, definition, aurc(s, y), 100 * RISK_LEVEL, cov,
                     rc["risk"].iloc[-1]))

            # ---- Platt, 60/40 stratified, scored on TEST only
            tr, te = stratified_split(y)
            n_te = len(te)
            pre = ece(s[te], y[te], N_BINS, BINNING)
            fitted = platt_scale(s[tr], y[tr], s[te])
            post = ece(fitted, y[te], N_BINS, BINNING)
            split_note = ("train n=%d (pos %d, rate %.4f); test n=%d "
                          "(pos %d, rate %.4f)"
                          % (len(tr), int(y[tr].sum()), y[tr].mean(),
                             n_te, int(y[te].sum()), y[te].mean()))
            for name, val, extra in (
                ("ece_test_pre_platt", pre,
                 "raw score used AS IF it were a probability"),
                ("ece_test_post_platt", post,
                 "after a two-parameter logistic fitted on the TRAIN half "
                 "only; scored on TEST only -- scoring on train would be "
                 "circular"),
                ("brier_test_pre_platt", brier(s[te], y[te]),
                 "raw score used AS IF it were a probability"),
                ("brier_test_post_platt", brier(fitted, y[te]),
                 "after Platt, TEST half only"),
            ):
                out.append(row(name, "ALL", definition, stage, k, val, n_te,
                               "", "", "", "",
                               "%s; split=60/40 stratified on the label, "
                               "seed=%d; %s; binning=%s(%d bins); %s"
                               % (base, SEED, split_note, BINNING, N_BINS,
                                  extra)))
            out.append(row("ece_test_platt_improvement", "ALL", definition,
                           stage, k, pre - post, n_te, "", "", "", "",
                           "%s; positive = Platt reduced ECE on the held-out "
                           "half; %s" % (base, split_note)))
            print("Platt  %-10s %-12s ECE_test pre=%.4f post=%.4f  "
                  "(test n=%d, pos=%d)"
                  % (score, definition, pre, post, n_te, int(y[te].sum())))
            print()

        # ---- supplementary: per query set, no CI
        for qs, dq in d.groupby("query_set"):
            if len(dq) < 20:
                continue
            for definition, k, stage, _ in DEFS:
                yq = dq[ycol(definition)].values
                sq = dq[score].values
                out.append(row("ece", qs, definition, stage, k,
                               ece(sq, yq, N_BINS, BINNING), len(dq),
                               "", "", "", "",
                               "score=%s; binning=%s(%d bins); SUPPLEMENTARY "
                               "per-query-set breakdown, no bootstrap CI"
                               % (score, BINNING, N_BINS)))
                out.append(row("brier", qs, definition, stage, k,
                               brier(sq, yq), len(dq), "", "", "", "",
                               "score=%s; SUPPLEMENTARY per-query-set "
                               "breakdown, no bootstrap CI" % score))

    res = pd.DataFrame(out, columns=["metric", "query_set", "definition",
                                     "stage", "k", "value", "n", "ci_lo",
                                     "ci_hi", "cluster_ci_lo",
                                     "cluster_ci_hi", "notes"])
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(OUT_CSV, index=False)
    print("wrote %s  (%d rows)" % (OUT_CSV, len(res)))

    make_figure(d)
    print("wrote %s" % OUT_PNG)


# ---------------------------------------------------------------- figure

def make_figure(d):
    n_all = len(d)
    fig, axes = plt.subplots(len(SCORES), len(DEFS), figsize=(15.0, 9.6))

    for i, score in enumerate(SCORES):
        for j, (definition, k, stage, _) in enumerate(DEFS):
            ax = axes[i][j]
            y = d[ycol(definition)].values
            s = d[score].values
            b = reliability_bins(s, y, N_BINS, BINNING)
            pos = int(y.sum())

            ax.plot([0, 1], [0, 1], ls="--", lw=1.0, color="0.45",
                    label="perfect calibration")
            ax.plot(b["mean_score"], b["accuracy"], marker="o", lw=1.6,
                    color="#1f4e79" if score == "composite" else "#a4501f",
                    label="observed")
            ax.axhline(y.mean(), ls=":", lw=1.0, color="0.6")

            # bin counts, offset alternately above/below so adjacent bins
            # (quantile binning puts them close together) stay readable
            for bi, (_, r) in enumerate(b.iterrows()):
                ax.annotate("%d" % int(r["n"]),
                            (r["mean_score"], r["accuracy"]),
                            textcoords="offset points",
                            xytext=(0, 8 if bi % 2 == 0 else -13),
                            ha="center", fontsize=7, color="0.25")

            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.set_aspect("equal")
            ax.grid(alpha=0.25, lw=0.5)
            ax.set_title("%s | %s @ %s\nECE=%.3f  Brier=%.3f  pos=%d/%d"
                         % (score, definition, stage,
                            ece(s, y, N_BINS, BINNING), brier(s, y),
                            pos, n_all), fontsize=9)
            if i == len(SCORES) - 1:
                ax.set_xlabel("claimed confidence (mean score in bin)",
                              fontsize=8)
            if j == 0:
                ax.set_ylabel("observed accuracy", fontsize=8)
            ax.tick_params(labelsize=7)
            if i == 0 and j == 0:
                ax.legend(fontsize=7, loc="upper left")

    caption = (
        "Reliability of the retrieval confidence score. Binning: QUANTILE "
        "(equal-mass), %d bins -- the scores cluster in ~0.35-0.87, so "
        "equal-width bins would leave most bins empty.\n"
        "Point labels are the number of queries in each bin. Dashed diagonal "
        "= perfect calibration; dotted horizontal = the base rate. "
        "n = %d gold-labelled queries (177 pair_id clusters), corpus of 4 "
        "statutory PDFs / 1,011 chunks.\n"
        "Stage: 'raw_15' = the gold section among Qdrant's top 15 before "
        "rerank or filter. 'answer' = label defined on the generated answer; "
        "the confidence score is the deployed pipeline's in every panel.\n"
        "CAVEAT, and it is the whole point: `composite` is a weighted sum of "
        "cosine similarities (0.55 top_k_mean + 0.15 score_gap + 0.30 "
        "entity_coverage). It never claimed to be a probability, so the "
        "distance from the diagonal is\nnot a broken promise -- it is the "
        "measurement of how far a similarity number is from being one. "
        "Weights and tier thresholds were frozen Feb 2026, before any score "
        "was logged, and are unchanged here."
        % (N_BINS, n_all))

    fig.suptitle("Reliability diagrams -- composite vs raw max_score, "
                 "three correctness definitions", fontsize=12, y=0.985)
    fig.text(0.012, 0.008, caption, fontsize=7.4, va="bottom", ha="left",
             linespacing=1.5)
    fig.tight_layout(rect=[0, 0.145, 1, 0.965])
    fig.savefig(OUT_PNG, dpi=170)
    plt.close(fig)


if __name__ == "__main__":
    main()
