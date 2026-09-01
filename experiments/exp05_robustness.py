"""exp05 -- ROBUSTNESS: definition sensitivity, CLUSTERING, and stability.

Wave 2, Subagent 5.  This is the adversarial experiment: its job is to try to
break the other four subagents' headline numbers before a reviewer does.

WHAT IT ASKS, IN PLAIN TERMS

  (a) DEFINITION SENSITIVITY.  "Correct" has three meanings in this project
      (retrieved@15 / cited / grounded) and they disagree wildly -- 327, 538
      and 27 positives on the same 617 queries.  A conclusion that holds under
      one meaning and dies under another is not a conclusion, it is an
      artefact of a labelling choice.  Every core analysis is therefore run
      under ALL THREE.  None is ever picked as "the" definition.

  (b) CLUSTERING.  Three phrasings of the SAME legal situation are not three
      independent observations.  They share a gold section, a topic and a
      vocabulary, so they succeed and fail together.  Counting them as three
      facts overstates how much evidence there is, and every confidence
      interval comes out narrower than the data supports.  Every headline
      value is therefore reported twice, side by side: NAIVE (rows resampled
      independently) and CLUSTERED (whole situations resampled, via
      metrics_lib.cluster_bootstrap on `pair_id`).

  (c) STABILITY.  Four restrictions of the data, asking each time whether the
      headline conclusions survive.

HOW "NAIVE" IS COMPUTED, AND WHY IT MATTERS THAT IT IS THIS WAY
    The naive interval is NOT a Wilson interval.  It is the SAME
    cluster_bootstrap() call, with the cluster column set to a per-row unique
    id -- so each "cluster" is one row and the resample degenerates to an
    ordinary row bootstrap.  Identical code path, identical seed, identical
    number of resamples.  The ONLY thing that varies between the naive and
    the clustered column is the definition of a cluster.  If the naive
    interval were a Wilson interval instead, the naive-vs-clustered width
    ratio would confound "clustering" with "bootstrap vs closed form", and the
    ratio would mean nothing.  check05 asserts the Wilson interval and the
    naive bootstrap agree anyway, which is the evidence that this substitution
    is sound.

A WARNING ABOUT DIFFERENCE STATISTICS -- READ BEFORE INTERPRETING THE CSV
    Clustering WIDENS an interval when the clustered rows are positively
    correlated and the statistic is an AVERAGE OVER them (the layman rate,
    the AUROCs).  That is the usual case and the one the reviewer objection is
    about.

    It does the OPPOSITE for a WITHIN-cluster difference.  On the paired set
    each `pair_id` contributes exactly one IPC-numbered row and one BNS-
    numbered row, so IPC-minus-BNS is a difference measured within situations.
    A naive row bootstrap breaks that pairing and pays for the between-
    situation variance twice; a cluster bootstrap keeps each situation's two
    rows together and that variance cancels.  So the clustered interval on the
    GAP is legitimately NARROWER.  This is pairing, not a bug -- but it is
    flagged loudly in the output and in check05 rather than left implicit,
    because "clustered is narrower" is otherwise exactly what a clustering bug
    looks like.

EVERY METRIC COMES FROM experiments/metrics_lib.py.  Nothing is reimplemented.
ZERO API calls.  Reads only; writes only results/robustness.csv.

Run:  ./venv/Scripts/python.exe experiments/exp05_robustness.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from core.citations import extract_provisions                       # noqa: E402
from experiments.metrics_lib import (                               # noqa: E402
    N_BOOT, SEED, STAGES, auroc_bootstrap_ci, cluster_bootstrap,
    correctness_label, load_logs, load_stages, paired_bootstrap_auroc_diff,
    same_section, wilson,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "robustness.csv"

CLUSTER_COL = "pair_id"
ROW_COL = "_row_id"          # per-row unique id -> cluster bootstrap == row bootstrap

COLUMNS = ["metric", "query_set", "definition", "stage", "k", "value", "n",
           "ci_lo", "ci_hi", "cluster_ci_lo", "cluster_ci_hi", "notes"]

ROWS: list[dict] = []
FLAGS: list[str] = []        # loud warnings, printed at the end


def emit(metric, query_set, definition, stage, k, value, n,
         ci=(None, None), cci=(None, None), notes=""):
    """One CSV row.  Empty is written for anything not measured -- never a
    plausible-looking placeholder."""
    ROWS.append({
        "metric": metric, "query_set": query_set, "definition": definition,
        "stage": stage or "", "k": "" if k is None else k,
        "value": value, "n": n,
        "ci_lo": ci[0], "ci_hi": ci[1],
        "cluster_ci_lo": cci[0], "cluster_ci_hi": cci[1],
        "notes": notes,
    })


# ------------------------------------------------------------------ data

def build_frame() -> pd.DataFrame:
    """The 617 gold-labelled rows, with one correctness column per definition.

    `cited` uses the POST-FIX citation parser (538 positives), re-parsed from
    answer text exactly as experiments/gate_smoke.py does, because
    load_logs()'s `cited` field was written by the pre-fix parser (533).
    """
    df = load_logs()
    stages = load_stages()

    scheme = {}
    for f in (ROOT / "eval").glob("*_queryset.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("query_id"):
                    scheme[r["query_id"]] = r.get("numbering_scheme")
    df["numbering_scheme"] = df["query_id"].map(scheme)

    texts = {}
    for f in (ROOT / "runs").rglob("queries.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("req_id"):
                    texts[r["req_id"]] = ((r.get("answer") or {}).get("answer_text")) or ""

    lab = df[df["expected_sections"].map(len) > 0].copy().reset_index(drop=True)

    cited_new = lab["req_id"].map(
        lambda rid: [f"{p.statute or ''} {p.number}".strip()
                     for p in extract_provisions(texts.get(rid, ""))
                     if p.kind == "section"])
    lab["lab_cited"] = [
        int(any(same_section(g, c) for g in gs for c in cs))
        for gs, cs in zip(lab["expected_sections"], cited_new)]
    lab["lab_grounded"] = [correctness_label(r, "grounded") for _, r in lab.iterrows()]
    for stage in STAGES:
        lab["lab_retrieved_" + stage] = [
            correctness_label({**r, "_stage": stage}, "retrieved@k", k=15, stages=stages)
            for _, r in lab.iterrows()]

    lab[ROW_COL] = np.arange(len(lab))
    return lab


# the three correctness definitions, as (csv definition label, stage, column)
DEFN_SPECS = [
    ("retrieved@15", "raw_15", "lab_retrieved_raw_15"),
    ("retrieved@15", "reranked_15", "lab_retrieved_reranked_15"),
    ("retrieved@15", "filtered_n", "lab_retrieved_filtered_n"),
    ("cited", "", "lab_cited"),
    ("grounded", "", "lab_grounded"),
]
# the three headline definitions (one stage each) used for the stability sweep
HEADLINE_SPECS = [
    ("retrieved@15", "raw_15", "lab_retrieved_raw_15"),
    ("cited", "", "lab_cited"),
    ("grounded", "", "lab_grounded"),
]


# ------------------------------------------------------------------ helpers

def width(lo, hi):
    if lo is None or hi is None or any(np.isnan([lo, hi])):
        return float("nan")
    return hi - lo


# A ratio this close to 1.0 is inside percentile-bootstrap noise on a discrete
# statistic and is not treated as evidence that clustering narrowed anything.
NARROWING_TOL = 1.02


def ratio_note(nlo, nhi, clo, chi, extra=""):
    """naive width / clustered width, plus its inverse, plus a loud flag when
    clustering NARROWS.

    DIRECTION, stated explicitly because getting it backwards is easy and was
    in fact the first bug in this file:

        width_ratio  = naive width / clustered width   (the brief's ratio)
        design_effect = clustered width / naive width  (the usual name)

    Clustering normally WIDENS, so the expected picture is
        width_ratio < 1  and  design_effect > 1.
    width_ratio > 1 means the clustered interval came out NARROWER, which for
    an average over positively-correlated rows should be impossible and is
    flagged rather than smoothed over.
    """
    wn, wc = width(nlo, nhi), width(clo, chi)
    if np.isnan(wn) or np.isnan(wc) or wc == 0 or wn == 0:
        r = float("nan")
        parts = ["width_ratio=NOT MEASURED", "design_effect=NOT MEASURED"]
    else:
        r = wn / wc
        parts = ["width_ratio=%.3f" % r, "design_effect=%.3f" % (wc / wn)]
        if r < 1.0:
            parts.append("clustered WIDER (expected)")
        elif r > NARROWING_TOL:
            parts.append("clustered NARROWER -- see FLAG")
        else:
            parts.append("equal within bootstrap noise")
    if extra:
        parts.append(extra)
    return r, "; ".join(parts)


def both_intervals(df: pd.DataFrame, stat_fn):
    """(point, naive lo/hi, clustered lo/hi).  Same call, two cluster columns."""
    p_n, nlo, nhi = cluster_bootstrap(df, stat_fn, ROW_COL, n_boot=N_BOOT, seed=SEED)
    p_c, clo, chi = cluster_bootstrap(df, stat_fn, CLUSTER_COL, n_boot=N_BOOT, seed=SEED)
    assert abs(p_n - p_c) < 1e-12, "point estimate must not depend on the cluster column"
    return p_n, (nlo, nhi), (clo, chi)


def rate_of(col):
    def f(d):
        return float(d[col].mean()) if len(d) else float("nan")
    return f


def gap_of(col):
    """IPC rate minus BNS rate, within one frame.  Returns nan if an arm is
    empty in a resample (cluster_bootstrap drops those draws)."""
    def f(d):
        i = d[d["numbering_scheme"] == "IPC"][col]
        b = d[d["numbering_scheme"] == "BNS"][col]
        if not len(i) or not len(b):
            return float("nan")
        return float(i.mean() - b.mean())
    return f


def flag(msg):
    FLAGS.append(msg)
    print("  !! FLAG: " + msg)


# ------------------------------------------------------------------ (a) counts

def part_a_counts(lab):
    print("=" * 78)
    print("(a) DEFINITION SENSITIVITY -- positive counts on the same 617 rows")
    print("=" * 78)
    n = len(lab)
    for defn, stage, col in DEFN_SPECS:
        k = int(lab[col].sum())
        p, lo, hi = wilson(k, n)
        emit("positive_count", "all", defn, stage,
             15 if defn.startswith("retrieved") else None,
             k, n, (lo, hi), (None, None),
             "Wilson interval on the RATE in ci_lo/ci_hi; value is the COUNT; "
             "cited = post-fix parser")
        print("  %-14s %-12s %4d/%d   %5.1f%%  [%.1f, %.1f]"
              % (defn, stage, k, n, p * 100, lo * 100, hi * 100))
    print()


# ------------------------------------------------------------------ analyses

def analysis_paired_gap(lab, restriction="none", specs=DEFN_SPECS):
    """CORE ANALYSIS 1 -- the IPC-vs-BNS retrieval gap on the paired set."""
    paired = lab[lab["query_set"] == "paired_recodification"]
    for defn, stage, col in specs:
        sub = paired[paired["numbering_scheme"].isin(["IPC", "BNS"])]
        if len(sub) == 0:
            emit("paired_gap_ipc_minus_bns", "paired_recodification", defn, stage, 15,
                 "NOT MEASURED", 0, notes="restriction=" + restriction + "; no rows")
            continue
        for arm in ("IPC", "BNS"):
            a = sub[sub["numbering_scheme"] == arm]
            if not len(a):
                continue
            pt, nci, cci = both_intervals(a, rate_of(col))
            r, note = ratio_note(nci[0], nci[1], cci[0], cci[1])
            nclust = a[CLUSTER_COL].nunique()
            extra = ""
            if nclust == len(a):
                extra = ("one row per cluster in this arm -- clustering is a NO-OP here "
                         "by construction, so the two intervals agree to RNG noise; ")
            emit("paired_rate_" + arm.lower(), "paired_recodification", defn, stage, 15,
                 round(pt, 6), len(a), nci, cci,
                 "restriction=%s; clusters=%d; %s%s" % (restriction, nclust, extra, note))
        pt, nci, cci = both_intervals(sub, gap_of(col))
        r, note = ratio_note(nci[0], nci[1], cci[0], cci[1])
        emit("paired_gap_ipc_minus_bns", "paired_recodification", defn, stage, 15,
             round(pt, 6), len(sub), nci, cci,
             "restriction=%s; clusters=%d; WITHIN-cluster difference -- clustering is "
             "expected to NARROW; %s" % (restriction, sub[CLUSTER_COL].nunique(), note))
        sig_n = nci[0] is not None and not np.isnan(nci[0]) and nci[0] > 0
        sig_c = cci[0] is not None and not np.isnan(cci[0]) and cci[0] > 0
        if sig_n != sig_c:
            flag("paired gap [%s/%s] restriction=%s: significance CHANGES between naive "
                 "(lo>0: %s) and clustered (lo>0: %s)"
                 % (defn, stage, restriction, sig_n, sig_c))


def analysis_layman_rate(lab, restriction="none", specs=DEFN_SPECS):
    """CORE ANALYSIS 2 -- the layman retrieval rate."""
    lay = lab[lab["query_set"] == "layman_situation"]
    for defn, stage, col in specs:
        if not len(lay):
            emit("layman_rate", "layman_situation", defn, stage, 15,
                 "NOT MEASURED", 0, notes="restriction=" + restriction + "; no rows")
            continue
        pt, nci, cci = both_intervals(lay, rate_of(col))
        r, note = ratio_note(nci[0], nci[1], cci[0], cci[1])
        emit("layman_rate", "layman_situation", defn, stage, 15,
             round(pt, 6), len(lay), nci, cci,
             "restriction=%s; clusters=%d; %s"
             % (restriction, lay[CLUSTER_COL].nunique(), note))
        if not np.isnan(r) and r > NARROWING_TOL:
            flag("layman rate [%s/%s] restriction=%s: clustered interval NARROWER than "
                 "naive (width_ratio %.3f) -- this is an AVERAGE over clustered rows "
                 "and should have WIDENED" % (defn, stage, restriction, r))


def analysis_auroc(lab, restriction="none", specs=HEADLINE_SPECS):
    """CORE ANALYSIS 3 -- composite vs max_score, paired on the same queries."""
    for defn, stage, col in specs:
        ok = lab[lab["composite"].notna() & lab["max_score"].notna()]
        y = ok[col].to_numpy()
        if len(set(y.tolist())) < 2:
            for m in ("auroc_composite", "auroc_max_score",
                      "auroc_diff_composite_minus_max"):
                emit(m, "all", defn, stage, None, "NOT MEASURED", len(y),
                     notes="restriction=%s; only one class present" % restriction)
            continue
        a, b = ok["composite"].to_numpy(), ok["max_score"].to_numpy()
        cid = ok[CLUSTER_COL].to_numpy()
        nclust = len(np.unique(cid))
        for name, s in (("auroc_composite", a), ("auroc_max_score", b)):
            pt, nlo, nhi = auroc_bootstrap_ci(s, y, n_boot=N_BOOT, seed=SEED)
            _, clo, chi = auroc_bootstrap_ci(s, y, n_boot=N_BOOT, seed=SEED,
                                             cluster_ids=cid)
            r, note = ratio_note(nlo, nhi, clo, chi)
            emit(name, "all", defn, stage, None, round(pt, 6), len(y),
                 (nlo, nhi), (clo, chi),
                 "restriction=%s; positives=%d; clusters=%d; %s"
                 % (restriction, int(y.sum()), nclust, note))
            if not np.isnan(r) and r > NARROWING_TOL:
                flag("%s [%s/%s] restriction=%s: clustered interval NARROWER than naive "
                     "(width_ratio %.3f) -- unexpected for an average over clustered rows"
                     % (name, defn, stage, restriction, r))
        dn = paired_bootstrap_auroc_diff(a, b, y, n_boot=N_BOOT, seed=SEED)
        dc = paired_bootstrap_auroc_diff(a, b, y, n_boot=N_BOOT, seed=SEED,
                                         cluster_ids=cid)
        r, note = ratio_note(dn["ci_lo"], dn["ci_hi"], dc["ci_lo"], dc["ci_hi"])
        emit("auroc_diff_composite_minus_max", "all", defn, stage, None,
             round(dn["diff"], 6), len(y),
             (dn["ci_lo"], dn["ci_hi"]), (dc["ci_lo"], dc["ci_hi"]),
             "restriction=%s; clusters=%d; p_naive=%.4f; p_clustered=%.4f; %s"
             % (restriction, nclust, dn["p_two_sided"], dc["p_two_sided"], note))
        sig_n, sig_c = dn["ci_hi"] < 0, dc["ci_hi"] < 0
        if sig_n != sig_c:
            flag("AUROC diff [%s/%s] restriction=%s: the claim 'composite is WORSE than "
                 "max_score' is %s naively but %s once clustered"
                 % (defn, stage, restriction,
                    "SUPPORTED" if sig_n else "NOT supported",
                    "SUPPORTED" if sig_c else "NOT supported"))


# ------------------------------------------------------------------ (c) restrictions

def one_per_cluster(lab):
    """Strictest independence assumption: one row per situation, seeded pick.

    A seeded random pick rather than 'first by query_id', because the variants
    are stored in a fixed order and taking the first would always take the same
    variant type (e.g. always the IPC-numbered phrasing), which is a
    systematically different query, not a random one.
    """
    rng = np.random.default_rng(SEED)
    keep = []
    for _, idx in sorted(lab.groupby(CLUSTER_COL, sort=True).indices.items()):
        keep.append(int(rng.choice(np.sort(idx))))
    return lab.iloc[sorted(keep)].copy()


def main():
    lab = build_frame()
    n_all = len(lab)
    print("loaded %d gold-labelled rows, %d distinct %s clusters\n"
          % (n_all, lab[CLUSTER_COL].nunique(), CLUSTER_COL))

    # -------- provenance / verification of the exclusions the brief asserts
    print("=" * 78)
    print("EXCLUSIONS AS FOUND (verifying, not assuming)")
    print("=" * 78)
    raw = load_logs()
    unlab = raw[raw["expected_sections"].map(len) == 0]
    crim = lab[lab["query_set"].astype(str).str.startswith("criminal")]
    print("  rows loaded (deduped)              %d" % len(raw))
    print("  unlabelled, dropped by gold filter %d  -> %s"
          % (len(unlab), list(unlab["query_id"])))
    print("  legacy criminal_* rows STILL IN    %d  -> %s"
          % (len(crim), list(crim["query_id"])))
    print("  rows with null %s                %d" % (CLUSTER_COL, lab[CLUSTER_COL].isna().sum()))
    emit("n_rows_loaded", "all", "", "", None, len(raw), len(raw),
         notes="after load_logs() dedupe on (query_id, intervention)")
    emit("n_rows_unlabelled_dropped", "all", "", "", None, len(unlab), len(raw),
         notes="no expected_sections; ids=" + "|".join(map(str, unlab["query_id"])))
    emit("n_rows_legacy_criminal", "all", "", "", None, len(crim), n_all,
         notes="legacy criminal_* rows PRESENT in the 617 -- NOT excluded as assumed; "
               "ids=" + "|".join(map(str, crim["query_id"])))
    if len(crim):
        flag("the %d legacy criminal_* rows are NOT already excluded from the 617 -- "
             "they carry gold labels and survive the gold filter (ids %s); they also "
             "all share pair_id 'P_murder' across two different query_sets"
             % (len(crim), list(crim["query_id"])))
    print()

    part_a_counts(lab)

    # -------- (b) full naive-vs-clustered on the unrestricted data
    print("=" * 78)
    print("(b) CLUSTERING -- naive vs clustered, unrestricted (restriction=none)")
    print("=" * 78)
    analysis_paired_gap(lab, "none")
    analysis_layman_rate(lab, "none")
    analysis_auroc(lab, "none")
    print("  done\n")

    # -------- (c) stability restrictions
    restrictions = [
        ("exclude_legacy_criminal",
         lab[~lab["query_set"].astype(str).str.startswith("criminal")]),
        ("exclude_entity_default_used",
         lab[lab["entity_default_used"] != True]),          # noqa: E712
        ("exclude_filter_applied_null",
         lab[lab["filter_applied"].notna()]),
        ("one_variant_per_pair_id", one_per_cluster(lab)),
    ]
    print("=" * 78)
    print("(c) STABILITY RESTRICTIONS")
    print("=" * 78)
    for name, sub in restrictions:
        sub = sub.copy()
        print("  %-32s n=%-5d clusters=%d" % (name, len(sub), sub[CLUSTER_COL].nunique()))
        emit("n_rows_after_restriction", "all", "", "", None, len(sub), n_all,
             notes="restriction=%s; clusters=%d; dropped=%d"
                   % (name, sub[CLUSTER_COL].nunique(), n_all - len(sub)))
        analysis_paired_gap(sub, name, HEADLINE_SPECS)
        analysis_layman_rate(sub, name, HEADLINE_SPECS)
        analysis_auroc(sub, name, HEADLINE_SPECS)
    print()

    out = pd.DataFrame(ROWS, columns=COLUMNS)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    print("=" * 78)
    print("FLAGS RAISED: %d" % len(FLAGS))
    for f in FLAGS:
        print("  !! " + f)
    print("=" * 78)
    print("wrote %s  (%d rows)" % (OUT, len(out)))


if __name__ == "__main__":
    main()
