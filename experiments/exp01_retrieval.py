"""exp01 -- RETRIEVAL METRICS.  Wave 2, Subagent 1.

WHAT THIS COMPUTES
    Recall@k, Precision@k, MRR@k and nDCG@k for k in {1,3,5,10,15}, per query
    set and pooled, at all three retrieval stages (raw_15, reranked_15,
    filtered_n), plus the two answer-level correctness definitions.

THREE THINGS A READER MUST KNOW BEFORE USING THIS TABLE

  1. `cited` and `grounded` DO NOT VARY WITH k OR STAGE.
     They are properties of the ANSWER the model produced, not of the ranked
     list. Fabricating a value per (stage, k) for them would put 15 identical
     numbers in the table and invite a reviewer to read them as 15
     measurements. They are reported ONCE per query set with `stage` and `k`
     left EMPTY.

  2. RANK-ORDER METRICS ARE PRIMARY AT raw_15.
     Entity reranking deliberately reorders the same 15 chunks by entity
     match, destroying score order. MRR and nDCG at `reranked_15` therefore
     measure the rerank policy, not the retriever. Both are reported; the
     `notes` column says which is which. filtered_n is a truncation of
     reranked_15, so it can only lose rank mass, never gain it.

  3. "RANK" HAS TWO MEANINGS AND BOTH ARE REPORTED.
     metrics_lib.ranked_sections() DROPS chunks that carry no section_number
     (preamble, split continuations, demoted footnotes). Only 118 of the 621
     raw_15 lists have all 15 chunks carrying one; the rest lose 1-14. Dropping
     them COMPRESSES rank positions: a gold chunk sitting at retrieved position
     5 is reported at rank 3. So

       recall_at_k / mrr_at_k / ndcg_at_k
           the metrics_lib convention -- rank among chunks that HAVE a section
           number. This is what correctness_label() computes and what the two
           external anchors (9/120 layman, 327/617 pooled) were set under. It
           is the shared ruler every other Wave-2 agent is using, so it is the
           primary series here.

       recall_at_k_positional / mrr_at_k_positional / ndcg_at_k_positional
           rank among chunks AS RETRIEVED. Section-less chunks keep their slot
           as an empty string, which same_section() can never match. This is
           what a reader assumes "the gold section was in the top 5" means,
           because a section-less chunk still occupies one of the 5 slots the
           language model is shown.

     At k=15 the two are IDENTICAL by construction -- dropping items cannot
     change membership of a whole list. Below k=15 the compressed convention is
     OPTIMISTIC, and on the layman set at k=5 it is optimistic by a FACTOR OF
     TWO (0.100 vs 0.050). Any k<15 number taken from this table must say which
     convention it used.

  4. GOLD IS NOT ALWAYS A SINGLE SECTION.
     525 of 617 labelled rows carry one gold section, 88 carry two, 4 carry
     three. Two recall definitions therefore exist and BOTH are reported:
       recall_at_k                  binary per query -- was ANY gold section
                                    retrieved in the top k. This is the
                                    definition metrics_lib.correctness_label
                                    uses and the one the GATE value 327/617
                                    was established under. It is a proportion
                                    OF QUERIES, so wilson() applies.
       recall_at_k_fraction_of_gold metrics_lib.recall_at_k verbatim -- the
                                    FRACTION of that query's gold sections
                                    found. Identical to the above on the 525
                                    single-gold rows; lower elsewhere. A mean,
                                    not a proportion, so bootstrap only.

INTERVALS
    Wilson (ci_lo/ci_hi)          proportions of queries: recall_at_k, and
                                  positive_rate for cited/grounded.
    Cluster bootstrap on pair_id  everything that is a mean rather than a
    (cluster_ci_lo/cluster_ci_hi) proportion: precision, MRR, nDCG,
                                  fraction-of-gold recall. 10,000 resamples,
                                  SEED=20260901, resampling SITUATIONS not
                                  rows, because 3-4 phrasings of one situation
                                  are not independent observations.
    Which method produced which interval is stated in `notes` on every row.

EVERY METRIC COMES FROM experiments/metrics_lib.py. Nothing is reimplemented.
ZERO API calls. Reads only; writes only results/retrieval_metrics.csv.

Run:  ./venv/Scripts/python.exe experiments/exp01_retrieval.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.metrics_lib import (  # noqa: E402
    SEED, N_BOOT, STAGES, load_logs, load_stages, ranked_sections,
    correctness_label, recall_at_k, precision_at_k, reciprocal_rank,
    ndcg_at_k, wilson, cluster_bootstrap,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "retrieval_metrics.csv"

KS = [1, 3, 5, 10, 15]

# The 3 legacy criminal_* rows and the 4 unlabelled SMOKE rows get no query-set
# row of their own; the exclusion is recorded in the output.
REPORT_SETS = ["generated_retrieval", "paired_recodification",
               "paired_dated_conflict", "layman_situation"]

_COMPRESSED = ("RANK CONVENTION: metrics_lib.ranked_sections() -- rank among "
               "chunks that carry a section_number; section-less chunks are "
               "dropped, which compresses ranks and is OPTIMISTIC for k<15. "
               "Identical to the positional variant at k=15.")
_POSITIONAL = ("RANK CONVENTION: positional -- rank among chunks AS RETRIEVED, "
               "section-less chunks keeping their slot as an unmatchable empty "
               "string. This is what 'in the top k' means to a reader. "
               "Identical to the metrics_lib variant at k=15.")

# metric name -> (description, is_a_proportion_of_queries, rank convention note)
METRICS = {
    "recall_at_k":
        ("share of QUERIES with >=1 gold section in the top k", True, _COMPRESSED),
    "recall_at_k_positional":
        ("share of QUERIES with >=1 gold section in the top k", True, _POSITIONAL),
    "recall_at_k_fraction_of_gold":
        ("mean FRACTION of a query's gold sections found in the top k", False,
         _COMPRESSED),
    "precision_at_k":
        ("mean share of the top k that are gold", False, _COMPRESSED),
    "mrr_at_k":
        ("mean 1/(rank of first gold hit) within the top k; 0 if absent", False,
         _COMPRESSED),
    "mrr_at_k_positional":
        ("mean 1/(rank of first gold hit) within the top k; 0 if absent", False,
         _POSITIONAL),
    "ndcg_at_k":
        ("mean 1/log2(rank+1) of the first gold hit within the top k", False,
         _COMPRESSED),
    "ndcg_at_k_positional":
        ("mean 1/log2(rank+1) of the first gold hit within the top k", False,
         _POSITIONAL),
}

STAGE_NOTES = {
    "raw_15": "PRIMARY for rank-order metrics -- Qdrant score order, untouched",
    "reranked_15": "same 15 chunks reordered by entity match; rank order here "
                   "reflects the rerank policy, NOT the retriever",
    "filtered_n": "what actually reached the language model after "
                  "max(top-0.15,0.35) with >=3 forced through",
}

DEFN_NOTES = {
    "cited": "the gold section appears among the answer's citations",
    "grounded": "EVERY citation in the answer was supported "
                "(ungrounded_rate == 0) -- the strict definition",
}


# ---------------------------------------------------------------- per-row

def positional_sections(chunks: list[dict]) -> list[str]:
    """ranked_sections() WITHOUT the drop: every retrieved chunk keeps its slot.

    A chunk with no section_number becomes "", and normalise_section("") == ""
    makes same_section() return False for it against anything -- so it can
    never be counted as a hit, it only occupies the rank position it actually
    occupied. Canonicalisation of the ones that DO have a section number is
    still metrics_lib.ranked_sections(), called on the single-chunk list, so
    the identity rule is not duplicated here.
    """
    return [ranked_sections([c])[0] if c.get("section_number") else ""
            for c in chunks]


def build() -> pd.DataFrame:
    """One row per (query row x stage) with every metric precomputed.

    Wide rather than long so that a SINGLE cluster bootstrap per
    (query_set, stage) can produce intervals for all 25 columns from the same
    10,000 resamples -- identical draws, identical seed, and 15 bootstrap runs
    instead of 375.
    """
    logs = load_logs()
    stages = load_stages()

    rows = []
    for r in logs.to_dict("records"):
        gold = r.get("expected_sections") or []
        if not len(gold):
            continue                       # the 4 unlabelled SMOKE rows
        st = stages.get(r["req_id"])
        if st is None:
            continue
        for stage in STAGES:
            chunks = st.get(stage, [])
            ranked = ranked_sections(chunks)
            positional = positional_sections(chunks)
            rec = {
                "req_id": r["req_id"],
                "query_id": r["query_id"],
                "query_set": r["query_set"],
                "pair_id": r["pair_id"],
                "intervention": r["intervention"],
                "stage": stage,
                "n_gold": len(gold),
                "n_ranked": len(ranked),
                "n_chunks": len(chunks),
                # answer-level, constant across stage and k. Carried on every
                # stage row only so one frame serves both; never reported
                # per stage.
                "cited": correctness_label(r, "cited"),
                "grounded": correctness_label(r, "grounded"),
            }
            for k in KS:
                # metrics_lib rank convention (section-less chunks dropped)
                rec["recall_at_k@%d" % k] = correctness_label(
                    {**r, "_stage": stage}, "retrieved@k", k, stages)
                rec["recall_at_k_fraction_of_gold@%d" % k] = recall_at_k(ranked, gold, k)
                rec["precision_at_k@%d" % k] = precision_at_k(ranked, gold, k)
                rec["mrr_at_k@%d" % k] = reciprocal_rank(ranked[:k], gold)
                rec["ndcg_at_k@%d" % k] = ndcg_at_k(ranked, gold, k)
                # positional convention (section-less chunks keep their slot)
                rec["recall_at_k_positional@%d" % k] = int(
                    recall_at_k(positional, gold, k) > 0.0)
                rec["mrr_at_k_positional@%d" % k] = reciprocal_rank(positional[:k], gold)
                rec["ndcg_at_k_positional@%d" % k] = ndcg_at_k(positional, gold, k)
            rows.append(rec)

    df = pd.DataFrame(rows)
    df["_cluster"] = df["query_set"].astype(str) + "|" + df["pair_id"].astype(str)
    return df


# ---------------------------------------------------------------- bootstrap

def harvest_bootstrap(d: pd.DataFrame, cols: list[str], cluster_col: str):
    """95% cluster-bootstrap intervals for MANY column means at once.

    metrics_lib.cluster_bootstrap() draws the resamples. `stat_fn` is called
    once per resample with the resampled frame; it records every column's mean
    into `harvest` and returns one of them, so that cluster_bootstrap's own
    return value can be checked against the harvested copy. Nothing about the
    resampling, the seed or the interval rule is reimplemented -- the identical
    10,000 draws are simply read for 25 columns instead of 1.

    Returns {col: (point, lo, hi)}.
    """
    harvest: list[np.ndarray] = []
    vals = d[cols].to_numpy(dtype=float)
    frame = pd.DataFrame({"_i": np.arange(len(d)),
                          cluster_col: d[cluster_col].values})

    def stat_fn(x: pd.DataFrame) -> float:
        m = vals[x["_i"].values].mean(axis=0)
        harvest.append(m)
        return float(m[0])

    point0, lo0, hi0 = cluster_bootstrap(frame, stat_fn, cluster_col, N_BOOT, SEED)

    assert len(harvest) == N_BOOT + 1, (
        "harvest length %d != N_BOOT+1 -- cluster_bootstrap rejected some "
        "resamples, so the harvested percentiles are not the returned ones"
        % len(harvest))
    boot = np.vstack(harvest[1:])
    lo = np.percentile(boot, 2.5, axis=0)
    hi = np.percentile(boot, 97.5, axis=0)
    point = vals.mean(axis=0)

    # Self-check: the harvested interval for column 0 must be bit-identical to
    # the one cluster_bootstrap returned for that same column.
    assert (abs(point[0] - point0) < 1e-12 and abs(lo[0] - lo0) < 1e-12
            and abs(hi[0] - hi0) < 1e-12), (
        "harvested interval for %s (%.12f,%.12f,%.12f) != cluster_bootstrap's "
        "(%.12f,%.12f,%.12f)" % (cols[0], point[0], lo[0], hi[0],
                                 point0, lo0, hi0))
    return {c: (float(point[i]), float(lo[i]), float(hi[i]))
            for i, c in enumerate(cols)}


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


# ---------------------------------------------------------------- anchors

def check_anchors(df: pd.DataFrame) -> dict:
    """The two values Wave 1 and the GATE established. Asserted, not eyeballed.

    A disagreement is a FINDING, not something to adjust to.
    """
    lay = df[(df["query_set"] == "layman_situation") & (df["stage"] == "filtered_n")]
    lay_k, lay_n = int(lay["recall_at_k@15"].sum()), len(lay)
    pooled = df[df["stage"] == "raw_15"]
    pool_k, pool_n = int(pooled["recall_at_k@15"].sum()), len(pooled)

    assert (lay_k, lay_n) == (9, 120), (
        "ANCHOR FAILED: layman recall@15 at filtered_n is %d/%d; Wave 1 "
        "established 9/120 = 0.075. STOP and report." % (lay_k, lay_n))
    assert (pool_k, pool_n) == (327, 617), (
        "ANCHOR FAILED: pooled recall@15 at raw_15 is %d/%d; the GATE "
        "established 327/617. STOP and report." % (pool_k, pool_n))
    return {"layman_filtered_15": (lay_k, lay_n),
            "pooled_raw_15": (pool_k, pool_n)}


# ---------------------------------------------------------------- main

def main():
    df = build()
    anchors = check_anchors(df)

    one_all = df[df["stage"] == "raw_15"]
    n_multi = int((one_all["n_gold"] > 1).sum())
    n_single = int((one_all["n_gold"] == 1).sum())

    metric_cols = ["%s@%d" % (m, k) for m in METRICS for k in KS]

    out = []
    # The four reported sets cluster on pair_id. Pooled clusters on
    # query_set|pair_id, because one pair_id ("P_murder") occurs in more than
    # one query set and those are not the same situation.
    groups = [(qs, df[df["query_set"] == qs], "pair_id") for qs in REPORT_SETS]
    groups.append(("ALL", df, "_cluster"))

    for qs, dq, cluster_col in groups:
        if not len(dq):
            continue
        for stage in STAGES:
            d = dq[dq["stage"] == stage]
            if not len(d):
                continue
            boot = harvest_bootstrap(d, metric_cols, cluster_col)
            n = len(d)
            for metric, (mnote, is_prop, rnote) in METRICS.items():
                for k in KS:
                    col = "%s@%d" % (metric, k)
                    point, blo, bhi = boot[col]
                    wlo = whi = ""
                    if is_prop:
                        kk = int(round(point * n))
                        _, wlo, whi = wilson(kk, n)
                        ci_note = ("ci_lo/ci_hi = Wilson (proportion of "
                                   "queries, k=%d); cluster_ci = cluster "
                                   "bootstrap on %s, %d resamples, seed %d"
                                   % (kk, cluster_col, N_BOOT, SEED))
                    else:
                        ci_note = ("ci_lo/ci_hi EMPTY -- this is a mean, not a "
                                   "proportion of queries, so Wilson does not "
                                   "apply; cluster_ci = cluster bootstrap on "
                                   "%s, %d resamples, seed %d"
                                   % (cluster_col, N_BOOT, SEED))
                    out.append(row(
                        metric, qs, "retrieved@k", stage, k, point, n,
                        wlo, whi, blo, bhi,
                        "%s. STAGE: %s. %s %s"
                        % (mnote, STAGE_NOTES[stage], rnote, ci_note)))

        # ---- answer-level definitions: NOT a function of stage or k
        one = dq[dq["stage"] == "raw_15"]        # exactly one row per query
        for definition in ("cited", "grounded"):
            kk, n = int(one[definition].sum()), len(one)
            p, lo, hi = wilson(kk, n)
            _, clo, chi = cluster_bootstrap(
                one[[cluster_col, definition]],
                lambda x, _c=definition: float(x[_c].mean()),
                cluster_col, N_BOOT, SEED)
            out.append(row(
                "positive_rate", qs, definition, "", "", p, n, lo, hi, clo, chi,
                "%s. stage and k are EMPTY BY DESIGN: this is a property of "
                "the ANSWER, not of the ranked list, so it does not vary with "
                "k or with retrieval stage; reporting it per (stage,k) would "
                "place 15 copies of one measurement in this table. k=%d. "
                "ci_lo/ci_hi = Wilson; cluster_ci = cluster bootstrap on %s, "
                "%d resamples, seed %d."
                % (DEFN_NOTES[definition], kk, cluster_col, N_BOOT, SEED)))

    # ---- the paired_dated_conflict condition mix, flagged explicitly
    pdc = df[df["query_set"] == "paired_dated_conflict"]
    for cond in sorted(pdc["intervention"].unique()):
        for stage in STAGES:
            d = pdc[(pdc["intervention"] == cond) & (pdc["stage"] == stage)]
            kk, n = int(d["recall_at_k@15"].sum()), len(d)
            p, lo, hi = wilson(kk, n)
            out.append(row(
                "recall_at_k_%s_rows" % cond, "paired_dated_conflict",
                "retrieved@k", stage, 15, p, n, lo, hi, "", "",
                "SPLIT OF THE SET ABOVE, NOT AN EXTRA SET. "
                "paired_dated_conflict's 197 rows are 99 queries under "
                "intervention='baseline' plus 98 of the SAME queries under "
                "intervention='both'. The main rows for this set pool both "
                "conditions. k=%d. Wilson interval." % kk))

    # ---- provenance
    logs_all = load_logs()
    excl = logs_all[~logs_all["query_set"].isin(REPORT_SETS)]
    out.append(row("rows_analysed", "ALL", "", "", "", len(one_all), len(one_all),
                   "", "", "", "",
                   "labelled query rows joined to experiments/stages.jsonl. "
                   "621 loaded, 4 dropped for carrying no gold (SMOKE). The 3 "
                   "legacy criminal_* rows DO carry gold and sit inside the "
                   "pooled ALL figure but get no query-set row of their own; "
                   "that is why ALL n=617 while the four reported sets sum "
                   "to 614."))
    out.append(row("rows_excluded", "ALL", "", "", "", len(excl), len(logs_all),
                   "", "", "", "",
                   "rows whose query_set is not one of the four reported sets"))
    out.append(row("gold_single_section", "ALL", "", "", "", n_single, len(one_all),
                   "", "", "", "",
                   "queries with exactly ONE gold section. Precision@k = "
                   "Recall@k / k, and nDCG@k is a monotone function of "
                   "reciprocal rank, ONLY on these."))
    out.append(row("gold_multi_section", "ALL", "", "", "", n_multi, len(one_all),
                   "", "", "", "",
                   "queries with 2 or 3 gold sections, where the two recall "
                   "definitions can differ"))
    full = int((one_all["n_ranked"] == one_all["n_chunks"]).sum())
    out.append(row("chunks_all_carry_section_number", "ALL", "retrieved@k",
                   "raw_15", "", full, len(one_all), "", "", "", "",
                   "queries whose raw_15 list has a section_number on EVERY "
                   "chunk. On the rest, ranked_sections() drops chunks and "
                   "compresses rank positions, which is why recall_at_k and "
                   "recall_at_k_positional differ for k<15 and agree at k=15."))
    out.append(row("anchor_layman_filtered_recall15", "layman_situation",
                   "retrieved@k", "filtered_n", 15,
                   anchors["layman_filtered_15"][0] / anchors["layman_filtered_15"][1],
                   anchors["layman_filtered_15"][1], "", "", "", "",
                   "ANCHOR ASSERTED IN-SCRIPT: %d/%d; Wave 1 established "
                   "9/120 = 0.075" % anchors["layman_filtered_15"]))
    out.append(row("anchor_pooled_raw_recall15", "ALL", "retrieved@k", "raw_15", 15,
                   anchors["pooled_raw_15"][0] / anchors["pooled_raw_15"][1],
                   anchors["pooled_raw_15"][1], "", "", "", "",
                   "ANCHOR ASSERTED IN-SCRIPT: %d/%d; the GATE established "
                   "327/617" % anchors["pooled_raw_15"]))

    res = pd.DataFrame(out, columns=["metric", "query_set", "definition",
                                     "stage", "k", "value", "n", "ci_lo",
                                     "ci_hi", "cluster_ci_lo",
                                     "cluster_ci_hi", "notes"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(OUT, index=False)

    # ---- console
    print("rows analysed: %d queries x %d stages = %d"
          % (len(one_all), len(STAGES), len(df)))
    print("gold sections per query: 1 -> %d, >1 -> %d" % (n_single, n_multi))
    print("\nANCHORS (asserted in-script):")
    print("  layman filtered_n recall@15 = %d/%d   (Wave 1: 9/120)"
          % anchors["layman_filtered_15"])
    print("  pooled  raw_15    recall@15 = %d/%d  (GATE:   327/617)"
          % anchors["pooled_raw_15"])

    print("\nHEADLINE -- Recall@15 [95% Wilson], share of queries with >=1 gold")
    print("  %-24s %5s  %-22s %-22s %-22s"
          % ("query_set", "n", "raw_15", "reranked_15", "filtered_n"))
    print("  " + "-" * 98)
    for qs, dq, _c in groups:
        cells = []
        for stage in STAGES:
            d = dq[dq["stage"] == stage]
            p, lo, hi = wilson(int(d["recall_at_k@15"].sum()), len(d))
            cells.append("%.3f [%.3f, %.3f]" % (p, lo, hi))
        print("  %-24s %5d  %-22s %-22s %-22s"
              % (qs, len(dq[dq["stage"] == "raw_15"]), cells[0], cells[1], cells[2]))

    print("\nRecall@k at raw_15 (primary stage)")
    print("  %-24s %5s %7s %7s %7s %7s %7s"
          % ("query_set", "n", "k=1", "k=3", "k=5", "k=10", "k=15"))
    for qs, dq, _c in groups:
        d = dq[dq["stage"] == "raw_15"]
        print("  %-24s %5d %7.3f %7.3f %7.3f %7.3f %7.3f"
              % (qs, len(d), *[d["recall_at_k@%d" % k].mean() for k in KS]))

    print("\nRANK CONVENTION SENSITIVITY -- Recall@k at raw_15")
    print("  metrics_lib (section-less chunks DROPPED) vs positional (kept)")
    print("  %-24s %5s %-15s %-15s %-15s %-15s %-15s"
          % ("query_set", "n", "k=1", "k=3", "k=5", "k=10", "k=15"))
    for qs, dq, _c in groups:
        d = dq[dq["stage"] == "raw_15"]
        cells = ["%.3f / %.3f" % (d["recall_at_k@%d" % k].mean(),
                                  d["recall_at_k_positional@%d" % k].mean())
                 for k in KS]
        print("  %-24s %5d %-15s %-15s %-15s %-15s %-15s"
              % (qs, len(d), cells[0], cells[1], cells[2], cells[3], cells[4]))
    print("  (identical at k=15 by construction; the gap below k=15 is the "
          "optimism)")

    print("\nMRR@15 -- raw_15 is PRIMARY; the rerank destroys score order")
    print("  %-24s %10s %10s %10s"
          % ("query_set", "raw_15", "reranked_15", "filtered_n"))
    for qs, dq, _c in groups:
        cells = [dq[dq["stage"] == s]["mrr_at_k@15"].mean() for s in STAGES]
        pos = [dq[dq["stage"] == s]["mrr_at_k_positional@15"].mean() for s in STAGES]
        print("  %-24s %10.4f %10.4f %10.4f   (positional: %.4f %.4f %.4f)"
              % (qs, cells[0], cells[1], cells[2], pos[0], pos[1], pos[2]))

    print("\nnDCG@15 -- same three stages")
    print("  %-24s %10s %10s %10s"
          % ("query_set", "raw_15", "reranked_15", "filtered_n"))
    for qs, dq, _c in groups:
        cells = [dq[dq["stage"] == s]["ndcg_at_k@15"].mean() for s in STAGES]
        print("  %-24s %10.4f %10.4f %10.4f" % (qs, cells[0], cells[1], cells[2]))

    print("\nANSWER-LEVEL definitions (no stage, no k -- they do not vary)")
    print("  %-24s %5s %8s %8s" % ("query_set", "n", "cited", "grounded"))
    for qs, dq, _c in groups:
        one = dq[dq["stage"] == "raw_15"]
        print("  %-24s %5d %8.4f %8.4f"
              % (qs, len(one), one["cited"].mean(), one["grounded"].mean()))

    print("\nwrote %s  (%d rows)" % (OUT, len(res)))


if __name__ == "__main__":
    main()
