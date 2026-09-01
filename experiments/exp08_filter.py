"""exp08 -- ADAPTIVE FILTER ANALYSIS.  Wave 1, Subagent 2.

WHAT THIS IS, AND WHAT IT IS EMPHATICALLY NOT
    This is ANALYSIS, not tuning. The deployed retrieval filter is

        threshold = max(top_score - 0.15, 0.35)      keep chunk if score >= threshold
                                                     with >=3 chunks forced through

    and it stays exactly as it is. Nothing in this file writes to
    agents/retriever.py or to any production path. What it does is re-apply a
    filter to ALREADY-RETRIEVED chunks stored in experiments/stages.jsonl and
    ask what WOULD have survived under a different absolute floor. That is a
    counterfactual over stored data, not a re-run and not a configuration
    change. The deployed 0.35 was frozen before any score was logged, and
    keeping it frozen is what lets these numbers be read as a measurement of
    the system rather than a result of tuning against the test set.

THREE QUESTIONS
    (a) For every query whose gold section was in raw_15 but NOT in
        filtered_n: what score did the gold chunk have, at what rank, what was
        top_score, what threshold cut it.
    (b) The threshold has two arms. Which one was BINDING on each cut --
        the relative arm (top_score - 0.15) or the absolute floor (0.35)?
    (c) Counterfactual sweep over floors {0.35 deployed, 0.30, 0.25, 0.20,
        none}, holding the relative arm and the >=3 rule fixed. Recall AND
        the mean number of chunks that would reach the language model,
        because a recall number without its chunk-count is half a result.

PAIRED CHECK
    Layman filtered_n recall is computed twice by independent routes --
    once from the filter reconstructed here, once from the Stage C chunk list
    stored by Wave 0's rerun_stages.py -- and asserted equal. See check_paired().

EVERY METRIC COMES FROM experiments/metrics_lib.py. Nothing is reimplemented.
ZERO API calls. Reads only; writes only results/filter_analysis.csv.

Run:  ./venv/Scripts/python.exe experiments/exp08_filter.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.metrics_lib import (  # noqa: E402
    SEED, N_BOOT, load_logs, load_stages, ranked_sections, recall_at_k,
    same_section, wilson, cluster_bootstrap,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "filter_analysis.csv"

ADAPTIVE_DROP = 0.15          # the relative arm, as deployed
DEPLOYED_FLOOR = 0.35         # the absolute arm, as deployed -- NOT changed anywhere
MIN_FORCED = 3                # >=3 chunks forced through regardless

# floor value -> label used in the `notes` column
FLOORS = [
    (0.35, "floor=0.35 (deployed)"),
    (0.30, "floor=0.30"),
    (0.25, "floor=0.25"),
    (0.20, "floor=0.20"),
    (None, "floor=none (relative arm only)"),
]

# query sets carrying enough rows to report. The 3 legacy criminal_* rows and
# the 4 SMOKE rows without gold are excluded and the exclusion is recorded.
REPORT_SETS = ["generated_retrieval", "paired_recodification",
               "paired_dated_conflict", "layman_situation"]


# ---------------------------------------------------------------- filter

def apply_filter(reranked, floor):
    """Re-apply the deployed adaptive filter with the absolute floor swapped.

    Identical arithmetic to agents/retriever.py and to Wave 0's
    rerun_stages.py, with ONE substitution: the constant 0.35 becomes `floor`
    (None means the floor is removed entirely and only the relative arm acts).
    Returns (kept_chunks, threshold).
    """
    if not reranked:
        return [], float("nan")
    top = max(c["score"] for c in reranked)
    rel = top - ADAPTIVE_DROP
    thr = rel if floor is None else max(rel, floor)
    kept = [c for c in reranked if c["score"] >= thr]
    if len(kept) < MIN_FORCED and len(reranked) >= MIN_FORCED:
        kept = reranked[:MIN_FORCED]
    return kept, thr


def gold_hit(chunks, gold):
    return recall_at_k(ranked_sections(chunks), gold, len(chunks)) > 0.0


def best_gold_chunk(chunks, gold):
    """(1-based rank, chunk) of the FIRST gold-matching chunk in list order.

    'First' = best-ranked. A gold section can occur in several chunks; the one
    that matters for whether the filter cut it is the best-scoring one, which
    in raw_15 (score order) is the earliest.
    """
    for i, c in enumerate(chunks, 1):
        sn, corpus = c.get("section_number"), c.get("corpus")
        if not sn:
            continue
        cand = f"{corpus} {sn}"
        if any(same_section(g, cand) for g in gold):
            return i, c
    return None, None


# ---------------------------------------------------------------- build

def build():
    logs = load_logs()
    stages = load_stages()

    rows = []
    for r in logs.to_dict("records"):
        st = stages.get(r["req_id"])
        gold = r.get("expected_sections") or []
        if st is None or not len(gold):
            continue
        raw, rer, storedC = st["raw_15"], st["reranked_15"], st["filtered_n"]
        if not rer:
            continue

        rec = {
            "req_id": r["req_id"],
            "query_id": r["query_id"],
            "query_set": r["query_set"],
            "pair_id": r["pair_id"],
            "gold": gold,
            "n_raw": len(raw),
            "top_score": max(c["score"] for c in rer),
            "in_raw15": gold_hit(raw, gold),
            "in_reranked15": gold_hit(rer, gold),
            "in_storedC": gold_hit(storedC, gold),
            "len_storedC": len(storedC),
        }
        for floor, label in FLOORS:
            kept, thr = apply_filter(rer, floor)
            key = "none" if floor is None else "%.2f" % floor
            rec["hit@" + key] = gold_hit(kept, gold)
            rec["nchunks@" + key] = len(kept)
            rec["thr@" + key] = thr
            if floor == DEPLOYED_FLOOR:
                rec["deployed_n_kept"] = len(kept)

        # per-cut detail, measured on the DEPLOYED filter only
        rank_raw, ch_raw = best_gold_chunk(raw, gold)
        rank_rer, ch_rer = best_gold_chunk(rer, gold)
        rec["gold_rank_raw"] = rank_raw
        rec["gold_rank_reranked"] = rank_rer
        rec["gold_score"] = ch_raw["score"] if ch_raw else np.nan
        rec["gold_corpus"] = ch_raw["corpus"] if ch_raw else None
        rec["threshold_deployed"] = rec["thr@0.35"]
        rec["relative_arm"] = rec["top_score"] - ADAPTIVE_DROP
        rec["binding_arm"] = ("absolute_floor"
                              if DEPLOYED_FLOOR > rec["relative_arm"]
                              else "relative")
        rows.append(rec)

    return pd.DataFrame(rows)


# ---------------------------------------------------------------- paired check

def check_paired(df):
    """Re-derive a headline value by an INDEPENDENT route and assert agreement.

    Route 1: the filter reconstructed in apply_filter() at the deployed floor.
    Route 2: the Stage C chunk list that Wave 0's rerun_stages.py wrote into
             experiments/stages.jsonl -- a separate implementation, run at a
             different time, against the live Qdrant collection.

    A disagreement would mean one of the two is not the deployed filter, which
    would invalidate every counterfactual below. It is asserted, not eyeballed.
    """
    out = {}
    for qs in REPORT_SETS + ["ALL"]:
        d = df if qs == "ALL" else df[df["query_set"] == qs]
        if not len(d):
            continue
        route1 = float(d["hit@0.35"].mean())
        route2 = float(d["in_storedC"].mean())
        out[qs] = (route1, route2, len(d))
        assert abs(route1 - route2) < 1e-12, (
            "PAIRED CHECK FAILED on %s: reconstructed filter recall %.6f != "
            "stored Stage C recall %.6f (n=%d). The reconstructed filter is "
            "not the deployed filter. STOP." % (qs, route1, route2, len(d))
        )
    mismatch = int((df["deployed_n_kept"] != df["len_storedC"]).sum())
    assert mismatch == 0, (
        "PAIRED CHECK FAILED: %d rows differ in Stage C length" % mismatch)
    out["_len_mismatch"] = mismatch
    return out


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


def prop_rows(metric, qs, definition, stage, k, d, col, notes):
    """A proportion with a Wilson interval AND a pair_id cluster bootstrap."""
    kk, nn = int(d[col].sum()), len(d)
    p, lo, hi = wilson(kk, nn)
    cl_lo = cl_hi = ""
    if nn and d["pair_id"].notna().all():
        _, cl_lo, cl_hi = cluster_bootstrap(
            d, lambda x: float(x[col].mean()), "pair_id", N_BOOT, SEED)
    return row(metric, qs, definition, stage, k, p, nn, lo, hi, cl_lo, cl_hi,
               "%s; k=%d" % (notes, kk))


def main():
    df = build()
    paired = check_paired(df)

    out = []
    for qs in REPORT_SETS:
        d = df[df["query_set"] == qs]
        if not len(d):
            continue
        n_all = len(d)

        # ---- anchors: recall at each stage, deployed configuration
        out.append(prop_rows("recall_gold_section", qs, "retrieved@k", "raw_15",
                             15, d, "in_raw15",
                             "gold section present among Qdrant's 15"))
        out.append(prop_rows("recall_gold_section", qs, "retrieved@k",
                             "reranked_15", 15, d, "in_reranked15",
                             "same 15, entity-reordered"))

        # ---- (a) what the filter cut
        inraw = d[d["in_raw15"]]
        cuts = inraw[~inraw["hit@0.35"]]
        n_in, n_cut = len(inraw), len(cuts)
        p, lo, hi = wilson(n_cut, n_in)
        out.append(row("filter_cut_rate", qs, "retrieved@k",
                       "raw_15->filtered_n", 15, p, n_in, lo, hi, "", "",
                       "gold in raw_15 but absent from filtered_n; k=%d; "
                       "denominator = queries whose gold was in raw_15" % n_cut))
        out.append(row("filter_cut_count", qs, "retrieved@k",
                       "raw_15->filtered_n", 15, n_cut, n_all, "", "", "", "",
                       "absolute count of cuts; n = all gold-labelled queries in set"))
        out.append(row("recall_lost_pp", qs, "retrieved@k",
                       "raw_15->filtered_n", 15,
                       100.0 * (d["in_raw15"].mean() - d["hit@0.35"].mean()),
                       n_all, "", "", "", "",
                       "percentage POINTS of recall lost, raw_15 -> filtered_n, "
                       "deployed floor"))

        if n_cut:
            detail = [
                ("gold_score", "cut_gold_score",
                 "score of the best-ranked gold chunk in raw_15"),
                ("gold_rank_raw", "cut_gold_rank_raw",
                 "1-based rank of that chunk in raw_15"),
                ("gold_rank_reranked", "cut_gold_rank_reranked",
                 "its 1-based rank after entity rerank"),
                ("top_score", "cut_top_score", "top_score of the query"),
                ("threshold_deployed", "cut_threshold",
                 "max(top_score-0.15, 0.35), the value that cut it"),
            ]
            for col, name, note in detail:
                v = pd.to_numeric(cuts[col], errors="coerce")
                for stat, fn in (("mean", v.mean), ("median", v.median),
                                 ("min", v.min), ("max", v.max)):
                    out.append(row(name + "_" + stat, qs, "retrieved@k",
                                   "raw_15->filtered_n", 15, fn(), n_cut,
                                   "", "", "", "", "%s; %s" % (stat, note)))

            # ---- (b) which arm was binding on each cut
            for arm, label in (("absolute_floor", "binding_arm_floor"),
                               ("relative", "binding_arm_relative")):
                kk = int((cuts["binding_arm"] == arm).sum())
                p, lo, hi = wilson(kk, n_cut)
                out.append(row(label, qs, "retrieved@k", "raw_15->filtered_n",
                               15, p, n_cut, lo, hi, "", "",
                               "binding arm = %s; k=%d; denominator = cuts; "
                               "the floor binds iff 0.35 > top_score-0.15" % (arm, kk)))
        else:
            out.append(row("filter_cut_detail", qs, "retrieved@k",
                           "raw_15->filtered_n", 15, "", 0, "", "", "", "",
                           "NOT MEASURED -- no cuts in this query set"))

        # ---- (c) counterfactual sweep
        for floor, label in FLOORS:
            key = "none" if floor is None else "%.2f" % floor
            out.append(prop_rows(
                "counterfactual_recall", qs, "retrieved@k", "filtered_n", "",
                d, "hit@" + key,
                "COUNTERFACTUAL re-applied to stored chunks; deployed config "
                "unchanged; relative arm and >=3 rule held fixed; " + label))
            col = "nchunks@" + key
            _, cl_lo, cl_hi = cluster_bootstrap(
                d, lambda x, _c=col: float(x[_c].mean()), "pair_id", N_BOOT, SEED)
            out.append(row("counterfactual_mean_chunks", qs, "retrieved@k",
                           "filtered_n", "", d[col].mean(), n_all, "", "",
                           cl_lo, cl_hi,
                           "COST SIDE: mean chunks reaching the LLM; %s; "
                           "ci_lo/ci_hi empty -- Wilson is for proportions, "
                           "not means" % label))

    # ---- provenance / exclusions
    excl = df[~df["query_set"].isin(REPORT_SETS)]
    out.append(row("rows_analysed", "ALL", "", "", "", len(df), len(df),
                   "", "", "", "",
                   "joined logs x stages, gold label present; %d rows excluded "
                   "(query_set not one of the four reported sets)" % len(excl)))
    out.append(row("paired_check_agreement", "ALL", "retrieved@k", "filtered_n",
                   "", 1.0, len(df), "", "", "", "",
                   "1.0 = reconstructed-filter recall EQUALS stored Stage C "
                   "recall on every query set to 1e-12, and Stage C lengths "
                   "match on every row"))

    res = pd.DataFrame(out, columns=["metric", "query_set", "definition",
                                     "stage", "k", "value", "n", "ci_lo",
                                     "ci_hi", "cluster_ci_lo",
                                     "cluster_ci_hi", "notes"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(OUT, index=False)

    # ---- console summary
    print("rows analysed: %d   excluded: %d" % (len(df), len(excl)))
    print("\nPAIRED CHECK (reconstructed filter vs stored Stage C):")
    for qs, v in paired.items():
        if str(qs).startswith("_"):
            continue
        print("  %-24s route1=%.4f  route2=%.4f  n=%d  AGREE"
              % (qs, v[0], v[1], v[2]))

    print("\n(a) WHAT THE FILTER CUT  [gold in raw_15, absent from filtered_n]")
    for qs in REPORT_SETS:
        d = df[df["query_set"] == qs]
        inraw = d[d["in_raw15"]]
        cuts = inraw[~inraw["hit@0.35"]]
        print("  %-24s n=%3d  in_raw15=%3d  cuts=%3d  lost=%.1f pp"
              % (qs, len(d), len(inraw), len(cuts),
                 100.0 * (d["in_raw15"].mean() - d["hit@0.35"].mean())))
        if len(cuts):
            print("      gold_score  mean=%.4f median=%.4f min=%.4f max=%.4f"
                  % (cuts["gold_score"].mean(), cuts["gold_score"].median(),
                     cuts["gold_score"].min(), cuts["gold_score"].max()))
            print("      gold_rank_raw mean=%.2f median=%.1f  |  top_score mean=%.4f"
                  "  |  threshold mean=%.4f"
                  % (cuts["gold_rank_raw"].mean(), cuts["gold_rank_raw"].median(),
                     cuts["top_score"].mean(), cuts["threshold_deployed"].mean()))

    print("\n(b) BINDING ARM among cuts:")
    for qs in REPORT_SETS:
        d = df[df["query_set"] == qs]
        inraw = d[d["in_raw15"]]
        cuts = inraw[~inraw["hit@0.35"]]
        if not len(cuts):
            print("  %-24s no cuts" % qs)
            continue
        kf = int((cuts["binding_arm"] == "absolute_floor").sum())
        p, lo, hi = wilson(kf, len(cuts))
        pr, lor, hir = wilson(len(cuts) - kf, len(cuts))
        print("  %-24s cuts=%3d  floor=%3d (%.3f, CI %.3f-%.3f)  "
              "relative=%3d (%.3f, CI %.3f-%.3f)"
              % (qs, len(cuts), kf, p, lo, hi, len(cuts) - kf, pr, lor, hir))

    print("\n(c) COUNTERFACTUAL SWEEP  recall [95%% Wilson] / mean chunks to LLM")
    print("  %-24s %4s %-24s %-24s %-24s %-24s %-24s"
          % ("query_set", "n", "0.35 (deployed)", "0.30", "0.25", "0.20", "none"))
    for qs in REPORT_SETS:
        d = df[df["query_set"] == qs]
        cells = []
        for floor, _ in FLOORS:
            key = "none" if floor is None else "%.2f" % floor
            p, lo, hi = wilson(int(d["hit@" + key].sum()), len(d))
            cells.append("%.3f[%.3f-%.3f]/%.1f"
                         % (p, lo, hi, d["nchunks@" + key].mean()))
        print("  %-24s %4d %-24s %-24s %-24s %-24s %-24s"
              % (qs, len(d), cells[0], cells[1], cells[2], cells[3], cells[4]))
        rp, rlo, rhi = wilson(int(d["in_raw15"].sum()), len(d))
        print("  %-24s      raw_15 ceiling = %.3f [%.3f-%.3f]"
              % ("", rp, rlo, rhi))

    print("\nwrote %s  (%d rows)" % (OUT, len(res)))


if __name__ == "__main__":
    main()
