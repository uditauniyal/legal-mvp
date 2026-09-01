"""exp04 -- CONFIDENCE ABLATION.  Wave 2, Subagent 4.

WHAT THIS IS, AND WHAT IT IS EMPHATICALLY NOT
    This is ANALYSIS, not tuning. The deployed confidence score is

        gap_penalty = min(score_gap / 0.3, 1.0)
        composite   = 0.55*top_k_mean + 0.15*(1.0 - gap_penalty) + 0.30*entity_coverage

    (agents/retriever.py:137-142) and the tier thresholds are HIGH >= 0.55,
    MEDIUM >= 0.38. Those five constants were frozen in February 2026, before
    a single retrieval score had ever been logged, which is precisely why the
    numbers below can be read as a measurement of the system rather than as a
    result of tuning against the evaluation set. NOTHING HERE CHANGES THEM.
    This file writes exactly one artefact, results/ablation.csv, and touches
    no production path.

    What it does instead is recompute alternative weightings OFFLINE from the
    three signals that were logged on every query, and report what those
    weightings WOULD have scored. Reporting a counterfactual is not adopting
    it.

THE FORMULA IS NOT WHAT THE BRIEF SAID -- read this before the results
    The task brief described the composite as

        0.55*top_k_mean + 0.15*score_gap + 0.30*entity_coverage

    That formula does NOT reproduce the logged composite. On all 617 labelled
    rows it is wrong, by up to 0.148 and by 0.091 on average. The deployed
    formula transforms the gap first:

        contribution of the gap = 0.15 * (1 - min(score_gap/0.3, 1.0))

    i.e. the deployed system treats a SMALL gap as evidence of confidence
    ("consistent relevance", retriever.py:98) and pays out the full 0.15 for
    it. With that transform the reconstruction matches the logged composite to
    9.0e-05 on every row, which is exactly the 4-decimal rounding floor.
    check04_ablation_check.py asserts this independently.

    Consequence for the ablation. The quantity that ACTUALLY enters the blend
    is not `score_gap` but `gap_term = 1 - min(score_gap/0.3, 1)`. Both are
    reported in part (a). Parts (b) and (c) operate on the three quantities
    that are genuinely blended -- top_k_mean, gap_term, entity_coverage --
    because only then does the weighting (0.55, 0.15, 0.30) reproduce the
    deployed composite exactly, which is what makes "remove one signal" and
    "move the weights" meaningful comparisons against it.

THREE QUESTIONS, AND THEY ARE DIFFERENT QUESTIONS
    (a) PER-SIGNAL AUROC. Does each signal, on its own, separate correct
        queries from incorrect ones? Plus a PAIRED bootstrap of each signal
        against the composite -- paired because both are measured on the same
        617 queries, and eyeballing two overlapping intervals is a weaker and
        different test than testing the difference directly.

    (b) LEAVE-ONE-OUT. Drop one signal from the blend, renormalise the two
        survivors to sum to 1.0, and ask what the reduced composite scores.
        THIS IS A DIFFERENT QUESTION FROM (a). (a) asks "does this signal
        carry information by itself"; (b) asks "does removing it hurt the
        combination". A signal can be useless alone and still help in
        combination (it corrects the others' mistakes), and a signal can look
        informative alone and still be dead weight in combination (it is
        redundant with a stronger signal). Neither answer implies the other.

        NOTE ON RENORMALISATION AND AUROC. Renormalising is done because the
        brief specifies it and because it keeps the reduced score on a
        comparable 0-1 scale. It does not change the AUROC by itself: AUROC
        is a rank statistic, and multiplying every score by the same positive
        constant leaves every rank untouched. What changes the AUROC is the
        removal of the term, not the rescaling of what is left.

    (c) WEIGHT SWEEP over the simplex in 0.05 steps (231 weightings). Reports
        the argmax and, critically, whether the argmax drives any signal to
        zero. Because the sweep picks the best of 231 candidates on the same
        data it then reports, the winning AUROC is OPTIMISTICALLY BIASED --
        so it is also reported under a 60/40 stratified split, weights chosen
        on train, AUROC read off test only, with the deployed 55/15/30
        evaluated on that same test half for a like-for-like comparison.

PAIRED CHECK -- experiments/check04_ablation_check.py
    Reconstructs the composite from the raw server logs by a route that
    shares no code with this file (no load_logs, no metrics_lib) and asserts
    agreement row by row.

EVERY METRIC COMES FROM experiments/metrics_lib.py. Nothing is reimplemented,
AUROC least of all. ZERO API calls. Reads only; writes only results/ablation.csv.

Run:  ./venv/Scripts/python.exe experiments/exp04_ablation.py
"""
from __future__ import annotations

import itertools
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.metrics_lib import (  # noqa: E402
    SEED, N_BOOT, load_logs, load_stages, correctness_label,
    auroc, auroc_bootstrap_ci, paired_bootstrap_auroc_diff,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "ablation.csv"

# --- the deployed constants. READ, NEVER WRITTEN. -----------------------
W_DEPLOYED = (0.55, 0.15, 0.30)      # top_k_mean, gap_term, entity_coverage
GAP_NORM = 0.3                        # retriever.py:137, min(gap/0.3, 1.0)
COMPONENTS = ("top_k_mean", "gap_term", "entity_coverage")

SWEEP_STEP = 0.05
TRAIN_FRAC = 0.60

# reported in the `definition` column, with the stage each one is measured at
DEFS = [
    ("retrieved@k", "raw_15", 15),
    ("cited", "", ""),
    ("grounded", "", ""),
]

# per-query-set breakdown is reported for this definition only
PRIMARY_DEF = "retrieved@k"
REPORT_SETS = ["generated_retrieval", "paired_recodification",
               "paired_dated_conflict", "layman_situation"]


# ---------------------------------------------------------------- loading

def build():
    """Labelled rows, the three blended components, and the three label sets."""
    logs = load_logs()
    stages = load_stages()

    n_all = len(logs)
    lab = logs[logs["expected_sections"].map(lambda x: len(x or []) > 0)]
    lab = lab.reset_index(drop=True)

    f = lambda c: pd.to_numeric(lab[c], errors="coerce").values
    top_k_mean = f("top_k_mean")
    score_gap = f("score_gap")
    entity_coverage = f("entity_coverage")
    composite_logged = f("composite")
    max_score = f("max_score")

    # the gap AS IT ENTERS THE BLEND -- see the module docstring
    gap_term = 1.0 - np.minimum(score_gap / GAP_NORM, 1.0)

    signals = {
        "top_k_mean": top_k_mean,
        "score_gap": score_gap,
        "gap_term": gap_term,
        "entity_coverage": entity_coverage,
        "composite": composite_logged,
        "max_score": max_score,
    }
    comp_mat = np.column_stack([top_k_mean, gap_term, entity_coverage])

    # labels. retrieved@k is read at raw_15 -- what Qdrant returned, before
    # the rerank and before the adaptive filter.
    recs = lab.to_dict("records")
    for r in recs:
        r["_stage"] = "raw_15"
    labels = {
        "retrieved@k": np.array([correctness_label(r, "retrieved@k", k=15, stages=stages)
                                 for r in recs], int),
        "cited": np.array([correctness_label(r, "cited") for r in recs], int),
        "grounded": np.array([correctness_label(r, "grounded") for r in recs], int),
    }

    meta = {
        "n_logs": n_all,
        "n_labelled": len(lab),
        "n_dropped_unlabelled": n_all - len(lab),
        "rows_before_dedupe": logs.attrs.get("rows_before_dedupe"),
        "in_stages": int(lab["req_id"].isin(stages.keys()).sum()),
        "n_entity_default": int(lab["entity_default_used"].astype(bool).sum()),
    }
    return lab, signals, comp_mat, labels, meta


def blend(comp_mat, w):
    """Weighted sum of the three components, capped at 1.0 exactly as
    retriever.py:145 caps it. The cap never binds on this data (the maximum
    logged composite is 0.8339) but it is kept so the reconstruction is the
    deployed arithmetic and not a paraphrase of it."""
    return np.minimum(comp_mat @ np.asarray(w, float), 1.0)


def renormalise(w, drop_idx):
    """Zero one weight and rescale the survivors to sum to 1.0.

    Worked example, the one in the brief: dropping score_gap leaves 0.55 and
    0.30, which sum to 0.85; 0.55/0.85 = 0.647 and 0.30/0.85 = 0.353.
    """
    w = list(w)
    w[drop_idx] = 0.0
    s = sum(w)
    return tuple(x / s for x in w)


def simplex(step=SWEEP_STEP):
    """Every (w1, w2, w3) on a `step` grid with w_i >= 0 and sum == 1.0.

    At step 0.05 there are C(22,2) = 231 of them. Built in integer units of
    the step so no floating-point sum ever fails the == 1.0 test.
    """
    n = int(round(1.0 / step))
    out = []
    for a, b in itertools.product(range(n + 1), repeat=2):
        c = n - a - b
        if c >= 0:
            out.append((a * step, b * step, c * step))
    return out


def stratified_split(y, frac=TRAIN_FRAC, seed=SEED):
    """60/40 split that preserves the positive rate in both halves.

    STRATIFIED means the split is done separately within the positives and
    within the negatives, so both halves carry roughly the same proportion of
    correct queries. With `grounded` at 27 positives out of 617, an unstratified
    split could easily hand one half almost no positives at all, and AUROC is
    undefined without both classes present.
    """
    rng = np.random.default_rng(seed)
    tr, te = [], []
    for cls in (0, 1):
        idx = np.flatnonzero(y == cls)
        rng.shuffle(idx)
        cut = int(round(frac * len(idx)))
        tr.append(idx[:cut])
        te.append(idx[cut:])
    return np.sort(np.concatenate(tr)), np.sort(np.concatenate(te))


# ---------------------------------------------------------------- reporting

def _fmt(v):
    if v is None or v == "":
        return ""
    try:
        fv = float(v)
    except (TypeError, ValueError):
        return v
    return "" if np.isnan(fv) else round(fv, 6)


def row(metric, query_set, definition, stage, k, value, n,
        ci_lo="", ci_hi="", cci_lo="", cci_hi="", notes=""):
    return {
        "metric": metric, "query_set": query_set, "definition": definition,
        "stage": stage, "k": k, "value": _fmt(value), "n": n,
        "ci_lo": _fmt(ci_lo), "ci_hi": _fmt(ci_hi),
        "cluster_ci_lo": _fmt(cci_lo), "cluster_ci_hi": _fmt(cci_hi),
        "notes": notes,
    }


def wfmt(w):
    return "/".join("%.3f" % x for x in w)


# ---------------------------------------------------------------- main

def main():
    t0 = time.time()
    lab, signals, comp_mat, labels, meta = build()
    n = meta["n_labelled"]
    cluster_ids = lab["pair_id"].values
    n_clusters = len(np.unique(cluster_ids))
    qs_col = lab["query_set"].values

    out = []

    # ================================================================
    # RECONSTRUCTION -- the paired check, run inline as well as in check04
    # ================================================================
    recon = blend(comp_mat, W_DEPLOYED)
    logged = signals["composite"]
    dev = np.abs(recon - logged)
    max_dev, mean_dev = float(dev.max()), float(dev.mean())

    # the formula the brief stated, for contrast
    brief = np.minimum(0.55 * signals["top_k_mean"] + 0.15 * signals["score_gap"]
                       + 0.30 * signals["entity_coverage"], 1.0)
    brief_dev = np.abs(brief - logged)

    print("=" * 78)
    print("RECONSTRUCTION OF THE LOGGED COMPOSITE")
    print("  deployed formula  0.55*top_k_mean + 0.15*(1-min(gap/0.3,1)) + 0.30*ec")
    print("      max |recon - logged| = %.8f   mean = %.8f   rows over 1e-3 = %d"
          % (max_dev, mean_dev, int((dev > 1e-3).sum())))
    print("  brief's formula   0.55*top_k_mean + 0.15*score_gap + 0.30*ec")
    print("      max |recon - logged| = %.8f   mean = %.8f   rows over 1e-3 = %d"
          % (brief_dev.max(), brief_dev.mean(), int((brief_dev > 1e-3).sum())))
    print("=" * 78)

    TOL = 2e-4      # 4-dp rounding on four separate logged quantities
    assert max_dev < TOL, (
        "PAIRED CHECK FAILED: the logged composite is NOT reproduced by the "
        "deployed formula read from agents/retriever.py. max deviation %.6f "
        "on %d rows. This would mean the logged composite came from some "
        "other arithmetic. STOP -- do not adjust the formula to match."
        % (max_dev, n))

    out.append(row("composite_reconstruction_max_abs_dev", "ALL", "", "", "",
                   max_dev, n, "", "", "", "",
                   "PAIRED CHECK: 0.55*top_k_mean + 0.15*(1-min(score_gap/0.3,1)) "
                   "+ 0.30*entity_coverage vs the LOGGED composite, per row. "
                   "Agrees to the 4-dp rounding floor on all %d rows." % n))
    out.append(row("composite_reconstruction_max_abs_dev_brief_formula", "ALL",
                   "", "", "", float(brief_dev.max()), n, "", "", "", "",
                   "SAME rows under the formula the task brief stated "
                   "(0.15*score_gap, untransformed). DOES NOT RECONSTRUCT -- "
                   "mean deviation %.4f, %d of %d rows off by more than 1e-3."
                   % (brief_dev.mean(), int((brief_dev > 1e-3).sum()), n)))

    # ================================================================
    # provenance
    # ================================================================
    out.append(row("rows_analysed", "ALL", "", "", "", n, n, "", "", "", "",
                   "load_logs() returned %d deduplicated rows (%d before "
                   "dedupe); %d dropped for having no gold section; %d of the "
                   "%d have stage records; %d clusters by pair_id"
                   % (meta["n_logs"], meta["rows_before_dedupe"],
                      meta["n_dropped_unlabelled"], meta["in_stages"], n,
                      n_clusters)))
    for dname, stage, k in DEFS:
        pos = int(labels[dname].sum())
        out.append(row("positives", "ALL", dname, stage, k, pos, n, "", "", "", "",
                       "count of label==1; prevalence %.4f" % (pos / n)))
    out.append(row("entity_coverage_default_used", "ALL", "", "", "",
                   meta["n_entity_default"] / n, n, "", "", "", "",
                   "fraction of queries where NO entity was extracted and "
                   "entity_coverage fell back to the neutral constant "
                   "ENTITY_NEUTRAL=0.5; k=%d" % meta["n_entity_default"]))
    ec = signals["entity_coverage"]
    out.append(row("entity_coverage_distinct_values", "ALL", "", "", "",
                   len(np.unique(ec)), n, "", "", "", "",
                   "entity_coverage takes only these values on this data: %s "
                   "-- it is effectively a three-level flag, not a continuous "
                   "signal. Max is 1.0: the >1.0 defect described in the brief "
                   "does NOT appear in these logs."
                   % ", ".join("%.2f" % v for v in np.unique(ec))))

    # ================================================================
    # (a) PER-SIGNAL AUROC + PAIRED DIFFERENCE AGAINST THE COMPOSITE
    # ================================================================
    SIGNAL_NOTE = {
        "top_k_mean": "signal=top_k_mean; mean of the top-5 similarity scores; "
                      "enters the blend at weight 0.55",
        "score_gap": "signal=score_gap; RAW logged gap, top-1 minus top-5 "
                     "similarity; NOT what enters the blend -- see gap_term",
        "gap_term": "signal=gap_term = 1-min(score_gap/0.3,1); THIS is the "
                    "quantity the deployed composite blends at weight 0.15; "
                    "high when the gap is SMALL",
        "entity_coverage": "signal=entity_coverage; fraction of query entities "
                           "found in the top-5 chunk text, 0.5 when none was "
                           "extracted; enters the blend at weight 0.30",
        "composite": "signal=composite; the DEPLOYED score, weights 0.55/0.15/0.30",
        "max_score": "signal=max_score; the single best similarity score; NOT "
                     "part of the composite -- reported as the reference point",
    }
    print("\n(a) PER-SIGNAL AUROC   [95%% percentile bootstrap, N_BOOT=%d, seed=%d]"
          % (N_BOOT, SEED))
    for dname, stage, k in DEFS:
        y = labels[dname]
        print("  --- definition=%s  positives=%d/%d" % (dname, int(y.sum()), n))
        for sname, s in signals.items():
            p, lo, hi = auroc_bootstrap_ci(s, y, N_BOOT, SEED)
            cl_lo = cl_hi = ""
            if dname == PRIMARY_DEF:
                _, cl_lo, cl_hi = auroc_bootstrap_ci(s, y, N_BOOT, SEED,
                                                     cluster_ids=cluster_ids)
            out.append(row("auroc_signal", "ALL", dname, stage, k, p, n,
                           lo, hi, cl_lo, cl_hi, SIGNAL_NOTE[sname]))
            print("      %-16s AUROC %.4f  [%.4f, %.4f]%s"
                  % (sname, p, lo, hi,
                     "  cluster [%.4f, %.4f]" % (cl_lo, cl_hi) if cl_lo != "" else ""))

        for sname, s in signals.items():
            if sname == "composite":
                continue
            d = paired_bootstrap_auroc_diff(s, signals["composite"], y, N_BOOT, SEED)
            out.append(row("auroc_diff_vs_composite", "ALL", dname, stage, k,
                           d["diff"], n, d["ci_lo"], d["ci_hi"], "", "",
                           "PAIRED bootstrap, same %d queries: AUROC(%s) - "
                           "AUROC(composite); p_two_sided=%.4f; %s"
                           % (n, sname, d["p_two_sided"],
                              "DIFFERENT from composite" if d["ci_lo"] * d["ci_hi"] > 0
                              else "interval spans 0")))
            print("      diff %-16s vs composite %+.4f [%+.4f, %+.4f] p=%.4f"
                  % (sname, d["diff"], d["ci_lo"], d["ci_hi"], d["p_two_sided"]))

    # per-query-set, primary definition only
    print("\n(a2) PER-QUERY-SET, definition=%s" % PRIMARY_DEF)
    y = labels[PRIMARY_DEF]
    for qs in REPORT_SETS:
        m = qs_col == qs
        nq, pos = int(m.sum()), int(y[m].sum())
        if not nq or pos == 0 or pos == nq:
            out.append(row("auroc_signal", qs, PRIMARY_DEF, "raw_15", 15, "", nq,
                           "", "", "", "",
                           "NOT MEASURED -- AUROC is undefined when one class is "
                           "absent (n=%d, positives=%d)" % (nq, pos)))
            continue
        cells = []
        for sname, s in signals.items():
            p, lo, hi = auroc_bootstrap_ci(s[m], y[m], N_BOOT, SEED)
            out.append(row("auroc_signal", qs, PRIMARY_DEF, "raw_15", 15, p, nq,
                           lo, hi, "", "",
                           SIGNAL_NOTE[sname] + "; positives=%d" % pos))
            cells.append("%s %.3f" % (sname[:9], p))
        print("   %-24s n=%3d pos=%3d  %s" % (qs, nq, pos, "  ".join(cells)))

    # ================================================================
    # (b) LEAVE-ONE-OUT
    # ================================================================
    print("\n(b) LEAVE-ONE-OUT   [renormalised to sum 1.0; DIFFERENT question from (a)]")
    for dname, stage, k in DEFS:
        y = labels[dname]
        full = blend(comp_mat, W_DEPLOYED)
        a_full = auroc(full, y)
        print("  --- definition=%s   full composite AUROC %.4f" % (dname, a_full))
        for i, cname in enumerate(COMPONENTS):
            w = renormalise(W_DEPLOYED, i)
            red = blend(comp_mat, w)
            p, lo, hi = auroc_bootstrap_ci(red, y, N_BOOT, SEED)
            cl_lo = cl_hi = ""
            if dname == PRIMARY_DEF:
                _, cl_lo, cl_hi = auroc_bootstrap_ci(red, y, N_BOOT, SEED,
                                                     cluster_ids=cluster_ids)
            kept = [(COMPONENTS[j], w[j]) for j in range(3) if j != i]
            out.append(row("auroc_loo", "ALL", dname, stage, k, p, n,
                           lo, hi, cl_lo, cl_hi,
                           "LEAVE-ONE-OUT drop=%s; surviving weights "
                           "renormalised to sum 1.0: %s; weighting=%s"
                           % (cname, ", ".join("%s=%.3f" % kv for kv in kept),
                              wfmt(w))))
            d = paired_bootstrap_auroc_diff(red, full, y, N_BOOT, SEED)
            out.append(row("auroc_diff_loo_vs_full", "ALL", dname, stage, k,
                           d["diff"], n, d["ci_lo"], d["ci_hi"], "", "",
                           "PAIRED bootstrap: AUROC(composite without %s) - "
                           "AUROC(full deployed composite); p_two_sided=%.4f; "
                           "positive means DROPPING THE SIGNAL HELPED; %s"
                           % (cname, d["p_two_sided"],
                              "differs from full" if d["ci_lo"] * d["ci_hi"] > 0
                              else "interval spans 0")))
            print("      drop %-16s -> %s  AUROC %.4f [%.4f, %.4f]   diff %+.4f "
                  "[%+.4f, %+.4f] p=%.4f"
                  % (cname, wfmt(w), p, lo, hi, d["diff"], d["ci_lo"],
                     d["ci_hi"], d["p_two_sided"]))

    out.append(row("loo_renormalisation_effect_on_auroc", "ALL", "", "", "",
                   0.0, n, "", "", "", "",
                   "AUROC is a RANK statistic, so rescaling every score by the "
                   "same positive constant cannot change it. Renormalising the "
                   "surviving weights therefore moves the AUROC by exactly 0. "
                   "What moves it is the REMOVAL of the term. Renormalisation "
                   "is kept because the brief specifies it and because it keeps "
                   "the reduced score on a 0-1 scale comparable to the deployed "
                   "one, which does matter for the tier thresholds."))

    # ================================================================
    # (c) WEIGHT SWEEP
    # ================================================================
    grid = simplex(SWEEP_STEP)
    print("\n(c) WEIGHT SWEEP over %d weightings, step %.2f, w1+w2+w3=1.0"
          % (len(grid), SWEEP_STEP))
    print("    ANALYSIS ONLY. The deployed weighting stays 0.55/0.15/0.30.")
    out.append(row("sweep_n_weightings", "ALL", "", "", "", len(grid), n,
                   "", "", "", "",
                   "every (w1,w2,w3) on a %.2f grid with w_i>=0 summing to 1.0; "
                   "order is (top_k_mean, gap_term, entity_coverage)" % SWEEP_STEP))

    for dname, stage, k in DEFS:
        y = labels[dname]
        scores = {w: blend(comp_mat, w) for w in grid}
        aur = {w: auroc(scores[w], y) for w in grid}
        best = max(grid, key=lambda w: aur[w])
        a_best = aur[best]
        a_dep = auroc(blend(comp_mat, W_DEPLOYED), y)
        n_close = int(sum(1 for w in grid if a_best - aur[w] <= 0.005))

        p, lo, hi = auroc_bootstrap_ci(scores[best], y, N_BOOT, SEED)
        out.append(row("auroc_sweep_argmax", "ALL", dname, stage, k, p, n,
                       lo, hi, "", "",
                       "ARGMAX of %d weightings, chosen and evaluated on the "
                       "SAME %d rows -- OPTIMISTICALLY BIASED, treat as an "
                       "upper bound; weighting=%s (top_k_mean/gap_term/"
                       "entity_coverage); ANALYSIS ONLY, deployed weighting "
                       "unchanged at %s"
                       % (len(grid), n, wfmt(best), wfmt(W_DEPLOYED))))
        out.append(row("auroc_deployed_weighting", "ALL", dname, stage, k,
                       a_dep, n, "", "", "", "",
                       "the deployed 0.55/0.15/0.30, same rows, for comparison "
                       "with the argmax above; identical to auroc_signal/"
                       "composite by construction"))
        out.append(row("sweep_argmax_gain_over_deployed", "ALL", dname, stage, k,
                       a_best - a_dep, n, "", "", "", "",
                       "AUROC(argmax) - AUROC(deployed), IN-SAMPLE and therefore "
                       "an upper bound on any real gain; see the test-half rows"))
        d = paired_bootstrap_auroc_diff(scores[best], blend(comp_mat, W_DEPLOYED),
                                        y, N_BOOT, SEED)
        out.append(row("auroc_diff_sweep_argmax_vs_deployed", "ALL", dname, stage,
                       k, d["diff"], n, d["ci_lo"], d["ci_hi"], "", "",
                       "PAIRED bootstrap; p_two_sided=%.4f; the interval does "
                       "NOT correct for the argmax having been selected on "
                       "these same rows, so it is anti-conservative"
                       % d["p_two_sided"]))
        for j, cname in enumerate(COMPONENTS):
            out.append(row("sweep_argmax_weight", "ALL", dname, stage, k,
                           best[j], n, "", "", "", "",
                           "signal=%s; weight the ARGMAX assigns it; %s"
                           % (cname,
                              "AT ZERO -- the sweep drops this signal entirely"
                              if best[j] == 0.0 else
                              "at or below one grid step of zero" if best[j] <= SWEEP_STEP
                              else "non-zero")))
        out.append(row("sweep_n_within_0.005_of_argmax", "ALL", dname, stage, k,
                       n_close, len(grid), "", "", "", "",
                       "how FLAT the surface is: %d of %d weightings score "
                       "within 0.005 AUROC of the best. A flat surface means "
                       "the argmax is barely distinguishable from its "
                       "neighbours and should not be read as 'the' answer."
                       % (n_close, len(grid))))

        # ---- train/test, the honest number
        tr, te = stratified_split(y, TRAIN_FRAC, SEED)
        y_tr, y_te = y[tr], y[te]
        if y_tr.sum() in (0, len(y_tr)) or y_te.sum() in (0, len(y_te)):
            out.append(row("auroc_sweep_argmax_test", "ALL", dname, stage, k, "",
                           len(te), "", "", "", "",
                           "NOT MEASURED -- a split half held only one class"))
            continue
        a_tr = {w: auroc(scores[w][tr], y_tr) for w in grid}
        best_tr = max(grid, key=lambda w: a_tr[w])
        a_test = auroc(scores[best_tr][te], y_te)
        a_dep_test = auroc(blend(comp_mat, W_DEPLOYED)[te], y_te)
        p2, lo2, hi2 = auroc_bootstrap_ci(scores[best_tr][te], y_te, N_BOOT, SEED)

        out.append(row("auroc_sweep_argmax_train", "ALL", dname, stage, k,
                       a_tr[best_tr], len(tr), "", "", "", "",
                       "train half only; weights SELECTED here; weighting=%s; "
                       "%d positives of %d; 60/40 stratified split, seed=%d"
                       % (wfmt(best_tr), int(y_tr.sum()), len(tr), SEED)))
        out.append(row("auroc_sweep_argmax_test", "ALL", dname, stage, k,
                       a_test, len(te), lo2, hi2, "", "",
                       "THE HONEST NUMBER: weighting=%s chosen on the train "
                       "half, AUROC read off the TEST half only; %d positives "
                       "of %d; 60/40 stratified, seed=%d"
                       % (wfmt(best_tr), int(y_te.sum()), len(te), SEED)))
        out.append(row("auroc_deployed_weighting_test", "ALL", dname, stage, k,
                       a_dep_test, len(te), "", "", "", "",
                       "the deployed 0.55/0.15/0.30 on the SAME test half, so "
                       "the comparison is like-for-like"))
        out.append(row("sweep_argmax_gain_over_deployed_test", "ALL", dname,
                       stage, k, a_test - a_dep_test, len(te), "", "", "", "",
                       "AUROC(train-selected weighting) - AUROC(deployed), TEST "
                       "HALF ONLY. This is the number to quote for 'what "
                       "retuning would actually have bought'. In-sample gain "
                       "was %+.4f." % (a_best - a_dep)))
        for j, cname in enumerate(COMPONENTS):
            out.append(row("sweep_argmax_weight_train", "ALL", dname, stage, k,
                           best_tr[j], len(tr), "", "", "", "",
                           "signal=%s; weight the TRAIN-selected argmax assigns "
                           "it; train half, 60/40 stratified" % cname))

        print("  --- definition=%s" % dname)
        print("      argmax (in-sample) %s  AUROC %.4f [%.4f, %.4f]  vs deployed "
              "%.4f  gain %+.4f" % (wfmt(best), a_best, lo, hi, a_dep, a_best - a_dep))
        print("      flatness: %d/%d weightings within 0.005 of the best"
              % (n_close, len(grid)))
        print("      argmax (train %d) %s -> TEST n=%d AUROC %.4f  deployed on "
              "test %.4f  gain %+.4f"
              % (len(tr), wfmt(best_tr), len(te), a_test, a_dep_test,
                 a_test - a_dep_test))
        zero = [COMPONENTS[j] for j in range(3) if best[j] == 0.0]
        print("      argmax puts AT ZERO: %s" % (", ".join(zero) if zero else "nothing"))

    # ---- secondary sweep: what if the gap were NOT sign-inverted?
    print("\n(c2) SECONDARY SWEEP with the RAW score_gap in place of gap_term")
    comp_raw = np.column_stack([signals["top_k_mean"], signals["score_gap"],
                                signals["entity_coverage"]])
    for dname, stage, k in DEFS:
        y = labels[dname]
        aur = {w: auroc(np.minimum(comp_raw @ np.asarray(w), 1.0), y) for w in grid}
        best = max(grid, key=lambda w: aur[w])
        out.append(row("auroc_sweep_argmax_rawgap", "ALL", dname, stage, k,
                       aur[best], n, "", "", "", "",
                       "SECONDARY, in-sample: the same sweep with the RAW "
                       "score_gap substituted for the deployed gap_term, i.e. "
                       "the gap NOT sign-inverted; weighting=%s (top_k_mean/"
                       "score_gap/entity_coverage). Reported because the "
                       "deployed transform treats a small gap as good and the "
                       "data says the opposite. ANALYSIS ONLY."
                       % wfmt(best)))
        print("      %-14s argmax %s  AUROC %.4f" % (dname, wfmt(best), aur[best]))

    # ================================================================
    res = pd.DataFrame(out, columns=["metric", "query_set", "definition",
                                     "stage", "k", "value", "n", "ci_lo",
                                     "ci_hi", "cluster_ci_lo",
                                     "cluster_ci_hi", "notes"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(OUT, index=False)
    print("\nwrote %s  (%d rows)   elapsed %.1fs" % (OUT, len(res), time.time() - t0))


if __name__ == "__main__":
    main()
