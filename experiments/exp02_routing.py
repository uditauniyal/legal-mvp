#!/usr/bin/env python3
"""exp02 -- ROUTING: where does a query actually land, and is that chance?

Wave 2, Subagent 2.  Output: results/routing_confusion.csv

    ./venv/Scripts/python.exe experiments/exp02_routing.py

THREE QUESTIONS, and why they are three and not one
---------------------------------------------------
(a) 4x4 CONFUSION MATRIX on the layman set.  Rows are the book the gold
    answer lives in; columns are the book the system actually read from.
    Off-diagonal mass is misrouting.

(b) 2x2 IPC/BNS on the paired recodification set, FROM THE LOGGED RUNS with
    the corpus filter exactly as it fired.  scripts/ablate_filter.py answers a
    DIFFERENT question -- it switches the filter off and asks whether the
    embeddings alone can tell the two codes apart (IPC 32/1 = 97.0%, BNS
    16/17 = 51.5%).  The numbers below are NOT a reproduction of those and are
    labelled `filter_as_recorded` everywhere so they cannot be mistaken for
    them.

(c) THE BASE-RATE CONTROL.  A book that occupies more of the index wins more
    often for free.  Retrieval share divided by index share is the
    OVER-REPRESENTATION RATIO; 1.0 is exactly what chance would give.  This is
    the control that makes the CrPC-dominance claim falsifiable.

TWO FILTERS, NEVER CONFLATED
    CORPUS FILTER          restricts Qdrant to one statute BEFORE retrieval.
                           Recorded in `retrieval.filter_applied`.
    ADAPTIVE SCORE FILTER  max(top_score - 0.15, 0.35), drops low scorers
                           AFTER retrieval.  This is the raw_15 -> filtered_n
                           step.

    stages.jsonl replays the RECORDED corpus filter, so all three of its
    stages are already corpus-restricted.  On the layman set that barely
    matters: 116 of 120 rows recorded filter_applied=None.

DEFINITION OF "WHICH BOOK THE SYSTEM WENT TO"
    The DOMINANT corpus among the retrieved chunks -- the book supplying the
    most chunks at that stage.  Chosen over "corpus of the top-1 chunk"
    because a single top hit is one embedding coin-flip, while the answer
    prompt is built from the whole retrieved set: dominance is what the model
    actually reads.  Ties are broken by the highest-scoring chunk among the
    tied books, and the number of ties is reported so the rule can be audited.

EVERY STATISTIC IS IMPORTED from experiments/metrics_lib.py.  Nothing is
reimplemented here.
"""

from __future__ import annotations

import collections
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from experiments.metrics_lib import (  # noqa: E402
    N_BOOT, SEED, STAGES, cluster_bootstrap, load_logs, load_stages, wilson,
)

CORPORA = ["IPC", "BNS", "CRPC", "CPA"]
OUT = ROOT / "results" / "routing_confusion.csv"

# The two query sets in scope.  3 legacy criminal_* rows and 4 unlabelled
# SMOKE rows are excluded by never being selected.
LAYMAN = "layman_situation"
PAIRED = "paired_recodification"


# ------------------------------------------------------------------ helpers

def dominant_corpus(chunks):
    """(book supplying the most chunks, was_it_a_tie).

    Tie -> the book owning the highest-scoring chunk among those tied.
    """
    if not chunks:
        return None, False
    counts = collections.Counter(c.get("corpus") for c in chunks)
    top = max(counts.values())
    tied = [k for k, v in counts.items() if v == top]
    if len(tied) == 1:
        return tied[0], False
    best, best_score = None, -float("inf")
    for c in chunks:
        if c.get("corpus") in tied and float(c.get("score", 0.0)) > best_score:
            best, best_score = c.get("corpus"), float(c.get("score", 0.0))
    return best, True


def index_shares():
    """Corpus counts over the whole Qdrant index -- the chance baseline.

    Read from Qdrant (READ-ONLY scroll) rather than from stages.jsonl,
    because stages.jsonl holds only chunks that were RETRIEVED.  Deriving the
    chance baseline from retrieval output would make the base-rate control
    circular -- it would compare retrieval against itself.  The index is a
    census, not a sample, so these counts carry no sampling error and the
    ratio's interval comes entirely from the retrieval side.
    """
    from clients.qdrant_client import COLLECTION, qdrant
    client = qdrant()
    counts, offset = collections.Counter(), None
    while True:
        pts, offset = client.scroll(collection_name=COLLECTION, limit=1000,
                                    offset=offset, with_payload=True,
                                    with_vectors=False)
        for p in pts:
            counts[(p.payload or {}).get("corpus")] += 1
        if offset is None:
            break
    total = sum(counts.values())
    return dict(counts), total, "qdrant:" + COLLECTION


ROWS = []


def emit(metric, query_set="", definition="", stage="", k="", value="", n="",
         ci_lo="", ci_hi="", cluster_ci_lo="", cluster_ci_hi="", notes=""):
    ROWS.append({
        "metric": metric, "query_set": query_set, "definition": definition,
        "stage": stage, "k": k, "value": value, "n": n,
        "ci_lo": ci_lo, "ci_hi": ci_hi,
        "cluster_ci_lo": cluster_ci_lo, "cluster_ci_hi": cluster_ci_hi,
        "notes": notes,
    })


def r(x, nd=4):
    if x is None:
        return ""
    x = float(x)
    return "" if np.isnan(x) else round(x, nd)


def hit_mean(d):
    return d["_hit"].mean() if len(d) else float("nan")


# ------------------------------------------------------------------ main

def main():
    df = load_logs()
    stages = load_stages()

    lay = df[df.query_set == LAYMAN].copy()
    par = df[df.query_set == PAIRED].copy()
    missing = [q for q in list(lay.req_id) + list(par.req_id) if q not in stages]
    if missing:
        raise SystemExit("STOP: %d req_ids absent from stages.jsonl" % len(missing))

    for st in STAGES:
        got, tie = zip(*(dominant_corpus(stages[q][st]) for q in lay.req_id))
        lay["got_" + st] = got
        lay["tie_" + st] = tie
        g2, t2 = zip(*(dominant_corpus(stages[q][st]) for q in par.req_id))
        par["got_" + st] = g2
        par["tie_" + st] = t2

    print("layman rows %d  situations %d" % (len(lay), lay.pair_id.nunique()))
    print("paired rows %d  pairs %d" % (len(par), par.pair_id.nunique()))
    print("layman CORPUS FILTER as recorded: %s"
          % lay.filter_applied.fillna("NONE").value_counts().to_dict())

    # ---------------------------------------------------------- (a) 4x4
    print("\n=== (a) 4x4 routing confusion, layman set ===")
    for st in ("raw_15", "filtered_n"):
        kcol = 15 if st == "raw_15" else ""
        ties = int(lay["tie_" + st].sum())
        emit("confusion_ties_broken_by_top_score", LAYMAN, "dominant_corpus",
             st, kcol, ties, len(lay),
             notes="rows where two or more books supplied an equal number of "
                   "chunks; broken by the highest-scoring chunk among them")
        tab = pd.crosstab(lay.expected_corpus, lay["got_" + st])
        tab = tab.reindex(index=CORPORA + ["EITHER", "BNSS"],
                          columns=CORPORA, fill_value=0).fillna(0).astype(int)
        print("\n-- stage %s (rows = gold book, cols = dominant retrieved book)"
              % st)
        print(tab.to_string())
        for want in CORPORA:
            for got in CORPORA:
                emit("confusion_expected%s_got%s" % (want, got), LAYMAN,
                     "dominant_corpus", st, kcol, int(tab.loc[want, got]),
                     int(tab.loc[want].sum()),
                     notes="cell count; 4x4 core matrix")
            sub = lay[lay.expected_corpus == want]
            kk = int((sub["got_" + st] == want).sum())
            nn = len(sub)
            p, lo, hi = wilson(kk, nn)
            _, clo, chi = cluster_bootstrap(
                sub.assign(_hit=(sub["got_" + st] == want).astype(int)),
                hit_mean, "pair_id", n_boot=N_BOOT, seed=SEED)
            emit("routing_accuracy_" + want, LAYMAN, "dominant_corpus", st,
                 kcol, r(p), nn, r(lo), r(hi), r(clo), r(chi),
                 notes="diagonal/row total = %d/%d; Wilson naive, clustered "
                       "bootstrap on pair_id (%d clusters, %d draws)"
                       % (kk, nn, sub.pair_id.nunique(), N_BOOT))
            print("   accuracy[%s] = %d/%d = %.1f%% [%.1f,%.1f] naive  "
                  "[%.1f,%.1f] clustered"
                  % (want, kk, nn, 100 * p, 100 * lo, 100 * hi,
                     100 * clo, 100 * chi))
        for want in ("EITHER", "BNSS"):
            if want == "EITHER":
                note = ("gold is either era (IPC or BNS both acceptable); "
                        "cannot be a confusion-matrix row, reported for "
                        "completeness")
            else:
                note = ("BNSS is NOT in the 1,899-chunk index at all -- every "
                        "one of these is unroutable by construction")
            for got in CORPORA:
                emit("confusionSUPP_expected%s_got%s" % (want, got), LAYMAN,
                     "dominant_corpus", st, kcol, int(tab.loc[want, got]),
                     int(tab.loc[want].sum()), notes=note)

    same = int((lay["got_raw_15"] == lay["got_filtered_n"]).sum())
    emit("confusion_stage_agreement_raw15_vs_filteredn", LAYMAN,
         "dominant_corpus", "raw_15|filtered_n", "", r(same / len(lay)),
         len(lay),
         notes="%d/%d layman queries get the same dominant book at both "
               "stages; does the picture change between stages?"
               % (same, len(lay)))
    print("\n   raw_15 vs filtered_n agreement: %d/%d = %.1f%%"
          % (same, len(lay), 100 * same / len(lay)))

    # ------------------------------------------- (b) 2x2 paired, filter ON
    print("\n=== (b) 2x2 IPC/BNS, paired_recodification, "
          "CORPUS FILTER AS RECORDED ===")
    print("    NOT a reproduction of scripts/ablate_filter.py (filter DISABLED).")
    numbered = par[par.variant.isin(["ipc_numbered", "bns_numbered"])].copy()
    print("    filter_applied here: %s"
          % numbered.filter_applied.fillna("NONE").value_counts().to_dict())
    for st in ("raw_15", "filtered_n"):
        kcol = 15 if st == "raw_15" else ""
        tab = pd.crosstab(numbered.expected_corpus, numbered["got_" + st])
        tab = tab.reindex(index=["IPC", "BNS"], columns=CORPORA,
                          fill_value=0).fillna(0).astype(int)
        print("\n-- stage %s" % st)
        print(tab.to_string())
        for want in ("IPC", "BNS"):
            for got in CORPORA:
                emit("pairedConfusion_expected%s_got%s" % (want, got), PAIRED,
                     "dominant_corpus|filter_as_recorded", st, kcol,
                     int(tab.loc[want, got]), int(tab.loc[want].sum()),
                     notes="corpus filter ON as logged; ablate_filter.py "
                           "measures the filter-OFF condition, a different "
                           "question")
            sub = numbered[numbered.expected_corpus == want]
            kk = int((sub["got_" + st] == want).sum())
            nn = len(sub)
            p, lo, hi = wilson(kk, nn)
            _, clo, chi = cluster_bootstrap(
                sub.assign(_hit=(sub["got_" + st] == want).astype(int)),
                hit_mean, "pair_id", n_boot=N_BOOT, seed=SEED)
            emit("paired_routing_accuracy_" + want, PAIRED,
                 "dominant_corpus|filter_as_recorded", st, kcol, r(p), nn,
                 r(lo), r(hi), r(clo), r(chi),
                 notes="%d/%d; the query NAMES %s. The CORPUS FILTER is ON, so "
                       "this measures the ROUTER's keyword lookup, not the "
                       "embeddings. scripts/ablate_filter.py with the filter "
                       "OFF gives IPC 97.0%% [84.7,99.5] and BNS 51.5%% "
                       "[35.2,67.5] -- a DIFFERENT condition; not a replication"
                       % (kk, nn, want))
            print("   accuracy[%s-named] = %d/%d = %.1f%% [%.1f,%.1f] naive  "
                  "[%.1f,%.1f] clustered"
                  % (want, kk, nn, 100 * p, 100 * lo, 100 * hi,
                     100 * clo, 100 * chi))

    # ------------------------------------------------- (c) BASE-RATE CONTROL
    print("\n=== (c) BASE-RATE CONTROL ===")
    counts, total, src = index_shares()
    print("    index source: %s, %d points" % (src, total))
    for c in CORPORA:
        emit("index_share_" + c, "", "share_of_index", "", "",
             r(counts.get(c, 0) / total), total,
             notes="%d/%d chunks; source %s; census, no sampling error"
                   % (counts.get(c, 0), total, src))

    # per-query chunk counts, so the bootstrap resamples QUERIES not chunks
    for st in STAGES:
        for c in CORPORA:
            lay["n_%s_%s" % (c, st)] = [
                sum(1 for ch in stages[q][st] if ch.get("corpus") == c)
                for q in lay.req_id]
        lay["n_tot_" + st] = [len(stages[q][st]) for q in lay.req_id]

    def make_share(corpus, stage):
        def share(d):
            t = d["n_tot_" + stage].sum()
            return d["n_%s_%s" % (corpus, stage)].sum() / t if t else float("nan")
        return share

    for st in STAGES:
        kcol = 15 if st in ("raw_15", "reranked_15") else ""
        tot_chunks = int(lay["n_tot_" + st].sum())
        print("\n-- layman retrieval share vs index share, stage %s "
              "(%d chunks from %d queries)" % (st, tot_chunks, len(lay)))
        print("   BOOK      INDEX  RETRIEVAL   RATIO      naive 95%"
              "        clustered 95%")
        for c in CORPORA:
            base = counts.get(c, 0) / total
            fn = make_share(c, st)
            pt, nlo, nhi = cluster_bootstrap(lay, fn, "query_id",
                                             n_boot=N_BOOT, seed=SEED)
            _, clo, chi = cluster_bootstrap(lay, fn, "pair_id",
                                            n_boot=N_BOOT, seed=SEED)
            emit("retrieval_share_" + c, LAYMAN, "share_of_retrieved_chunks",
                 st, kcol, r(pt), tot_chunks, r(nlo), r(nhi), r(clo), r(chi),
                 notes="denominator is CHUNKS (%d), not queries; naive CI "
                       "resamples the %d queries, clustered CI resamples the "
                       "%d situations" % (tot_chunks, len(lay),
                                          lay.pair_id.nunique()))
            emit("over_representation_ratio_" + c, LAYMAN,
                 "retrieval_share/index_share", st, kcol, r(pt / base),
                 tot_chunks, r(nlo / base), r(nhi / base),
                 r(clo / base), r(chi / base),
                 notes="index share %.4f held FIXED (census); 1.0 = exactly "
                       "chance; >1 = over-represented" % base)
            print("   %-6s %6.1f%%    %6.1f%%  %5.2fx   [%.2f,%.2f]"
                  "        [%.2f,%.2f]"
                  % (c, 100 * base, 100 * pt, pt / base, nlo / base,
                     nhi / base, clo / base, chi / base))

    # sensitivity: drop the layman rows where a CORPUS FILTER did fire
    unf = lay[lay.filter_applied.isna()]
    for st in ("raw_15", "filtered_n"):
        base = counts.get("CRPC", 0) / total
        fn = make_share("CRPC", st)
        pt, nlo, nhi = cluster_bootstrap(unf, fn, "query_id",
                                         n_boot=N_BOOT, seed=SEED)
        _, clo, chi = cluster_bootstrap(unf, fn, "pair_id",
                                        n_boot=N_BOOT, seed=SEED)
        emit("over_representation_ratio_CRPC_unfiltered_only", LAYMAN,
             "retrieval_share/index_share", st,
             15 if st == "raw_15" else "", r(pt / base),
             int(unf["n_tot_" + st].sum()), r(nlo / base), r(nhi / base),
             r(clo / base), r(chi / base),
             notes="sensitivity: the %d layman rows whose CORPUS FILTER fired "
                   "(CPA) are dropped, leaving %d rows with "
                   "filter_applied=None" % (len(lay) - len(unf), len(unf)))
        print("\n   CRPC ratio, filter=None rows only, %s: %.2fx [%.2f,%.2f] "
              "clustered  (%d queries)"
              % (st, pt / base, clo / base, chi / base, len(unf)))

    OUT.parent.mkdir(exist_ok=True)
    pd.DataFrame(ROWS, columns=[
        "metric", "query_set", "definition", "stage", "k", "value", "n",
        "ci_lo", "ci_hi", "cluster_ci_lo", "cluster_ci_hi", "notes",
    ]).to_csv(OUT, index=False, encoding="utf-8")
    print("\nwrote %s  (%d rows)" % (OUT, len(ROWS)))


if __name__ == "__main__":
    main()
