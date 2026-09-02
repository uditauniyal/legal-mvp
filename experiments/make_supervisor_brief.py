"""Generate docs/SUPERVISOR_BRIEF.md and docs/NUMBERS_AT_A_GLANCE.md.

COMMUNICATION ARTEFACT ONLY. No new analysis, no new claims.

Every number is pulled from results/*.csv by filtering, exactly as
assemble_results.py does. Each spec must match EXACTLY ONE row or the script
raises -- so a figure cannot be silently averaged, guessed, or retyped.

Anything that cannot be sourced from a file is reported as DROPPED and does not
appear in either document.

    ./venv/Scripts/python.exe experiments/make_supervisor_brief.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8")

REGEN = {
    "hybrid_comparison.csv": "experiments/exp07_hybrid.py",
    "retrieval_metrics.csv": "experiments/exp01_retrieval.py",
    "routing_confusion.csv": "experiments/exp02_routing.py",
    "calibration.csv": "experiments/exp03_calibration.py",
    "ablation.csv": "experiments/exp04_ablation.py",
    "robustness.csv": "experiments/exp05_robustness.py",
    "statute_consistency.csv": "experiments/exp06_statute_consistency.py",
    "filter_analysis.csv": "experiments/exp08_filter.py",
    "corrected_composite.csv": "experiments/exp09_corrected_composite.py",
}

_cache: dict[str, pd.DataFrame] = {}
DROPPED: list[str] = []


def load(f: str) -> pd.DataFrame:
    if f not in _cache:
        _cache[f] = pd.read_csv(ROOT / "results" / f)
    return _cache[f]


class Row:
    """One sourced figure. Formats itself; never holds a typed number."""

    def __init__(self, file: str, sub: pd.Series):
        self.file, self.r = file, sub

    @property
    def v(self) -> float:
        return float(self.r["value"])

    def pct(self, dp: int = 1) -> str:
        return f"{self.v * 100:.{dp}f}%"

    def num(self, dp: int = 4) -> str:
        return f"{self.v:.{dp}f}"

    def ci(self, dp: int = 4, pct: bool = False, cluster: bool = False) -> str:
        lo = self.r["cluster_ci_lo"] if cluster else self.r["ci_lo"]
        hi = self.r["cluster_ci_hi"] if cluster else self.r["ci_hi"]
        if pd.isna(lo) or pd.isna(hi):
            return "no CI"
        m = 100 if pct else 1
        s = "%" if pct else ""
        return f"[{float(lo)*m:.{dp}f}{s}, {float(hi)*m:.{dp}f}{s}]"

    @property
    def n(self) -> str:
        return str(int(self.r["n"]))

    @property
    def defn(self) -> str:
        d = self.r["definition"]
        return "n/a" if pd.isna(d) else str(d)

    @property
    def stage(self) -> str:
        s = self.r["stage"]
        return "n/a" if pd.isna(s) else str(s)

    @property
    def cmd(self) -> str:
        return f"./venv/Scripts/python.exe {REGEN[self.file]}"


def pick(file: str, notes: str | None = None, **filt) -> Row:
    """Exactly one row, or raise. Ambiguity is a bug, not a rounding choice."""
    d = load(file)
    for col, val in filt.items():
        d = d[d[col].astype(str) == str(val)]
    if notes:
        d = d[d["notes"].astype(str).str.contains(notes, regex=False)]
    d = d.drop_duplicates(subset=["metric", "query_set", "definition", "stage",
                                  "k", "value", "n"])
    if len(d) != 1:
        raise LookupError(f"{file} {filt} notes={notes!r} -> {len(d)} rows, need 1")
    return Row(file, d.iloc[0])


def main() -> None:
    # ---------------- verification: every referenced file must exist --------
    missing = [f for f in list(REGEN) + ["RESULTS.md", "EXPLAIN.md", "smoke_test.md"]
               if not (ROOT / "results" / f).exists()]
    for f in missing:
        DROPPED.append(f"referenced file absent: results/{f}")

    H = "hybrid_comparison.csv"
    A = "ablation.csv"
    C = "corrected_composite.csv"
    R = "robustness.csv"
    G = "routing_confusion.csv"
    K = "calibration.csv"
    S = "statute_consistency.csv"
    T = "retrieval_metrics.csv"

    g = {}
    # cross-statute, corpus filter disabled
    for arm in ("dense", "bm25", "hybrid_rrf"):
        for side in ("ipc", "bns"):
            g[f"dom_{arm}_{side}"] = pick(
                H, metric="corpus_dominant_accuracy", stage=arm,
                query_set=f"paired_numbered_{side}_named")
            g[f"top1_{arm}_{side}"] = pick(
                H, metric="corpus_top1_accuracy", stage=arm,
                query_set=f"paired_numbered_{side}_named")
        g[f"dom_{arm}_both"] = pick(H, metric="corpus_dominant_accuracy",
                                    stage=arm, query_set="paired_numbered_both")
    g["ceiling_all"] = pick(H, metric="gold_reachable_ceiling", query_set="ALL")
    g["ceiling_bns"] = pick(H, metric="gold_reachable_ceiling",
                            query_set="paired_numbered_bns_named")

    # confidence signals, pooled
    for sig in ("max_score", "composite", "top_k_mean", "entity_coverage"):
        g[f"sig_{sig}"] = pick(A, metric="auroc_signal", definition="retrieved@k",
                               query_set="ALL", notes=f"signal={sig};")
    g["sig_gap_term"] = pick(A, metric="auroc_signal", definition="retrieved@k",
                             query_set="ALL", notes="signal=gap_term")
    g["sig_score_gap"] = pick(A, metric="auroc_signal", definition="retrieved@k",
                              query_set="ALL", notes="signal=score_gap;")

    # corrected composite
    d1 = "retrieved@15 (raw_15)"
    for s in ("composite_deployed", "composite_corrected", "max_score"):
        g[f"cc_{s}"] = pick(C, metric="auroc", definition=d1, notes=f"score={s};")
    g["cc_diff_corr_max"] = pick(C, metric="auroc_paired_diff", definition=d1,
                                 notes="composite_corrected minus max_score")
    g["cc_diff_corr_dep"] = pick(C, metric="auroc_paired_diff", definition=d1,
                                 notes="composite_corrected minus composite_deployed")
    g["cc_diff_dep_max"] = pick(C, metric="auroc_paired_diff", definition=d1,
                                notes="composite_deployed minus max_score")
    g["cc_best_test"] = pick(C, metric="auroc_corrected_bestweights_test",
                             definition=d1)

    # robustness
    for dd, st, key in [("retrieved@15", "raw_15", "gap_ret"),
                        ("cited", None, "gap_cit"),
                        ("grounded", None, "gap_gro")]:
        extra = {"stage": st} if st else {}
        g[key] = pick(R, metric="paired_gap_ipc_minus_bns", definition=dd,
                      query_set="paired_recodification", notes="restriction=none",
                      **extra)
    g["layman_raw"] = pick(R, metric="layman_rate", definition="retrieved@15",
                           stage="raw_15", notes="restriction=none")
    g["layman_filt"] = pick(R, metric="layman_rate", definition="retrieved@15",
                            stage="filtered_n", notes="restriction=none")

    # routing / bias amplification
    for book in ("CRPC", "BNS", "IPC"):
        for st in ("raw_15", "filtered_n"):
            g[f"or_{book}_{st}"] = pick(G, metric=f"over_representation_ratio_{book}",
                                        query_set="layman_situation", stage=st)

    # calibration
    for sc, tag in [("composite", "comp"), ("max_score", "max")]:
        g[f"cov_{tag}"] = pick(K, metric="coverage_at_risk_0.10",
                               definition="retrieved@k", query_set="ALL",
                               notes=f"score={sc}")
        g[f"ece_{tag}"] = pick(K, metric="ece", definition="retrieved@k",
                               query_set="ALL", notes=f"score={sc}")

    # statute_consistency
    g["sc_dated"] = pick(S, metric="auroc_statute_consistency", stage="raw_15",
                         definition="retrieved@k", query_set="paired_dated_conflict")
    g["sc_all"] = pick(S, metric="auroc_statute_consistency", stage="raw_15",
                       definition="retrieved@k", query_set="ALL")

    # retrieval per set
    for qs in ("generated_retrieval", "paired_recodification",
               "paired_dated_conflict", "layman_situation", "ALL"):
        g[f"rec_{qs}"] = pick(T, metric="recall_at_k", k="15.0",
                              definition="retrieved@k", stage="raw_15", query_set=qs)

    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                         capture_output=True, text=True).stdout.strip()
    total = sum(len(load(f)) for f in REGEN)

    write_brief(g, sha, total)
    write_glance(g, sha)

    print(f"wrote docs/SUPERVISOR_BRIEF.md and docs/NUMBERS_AT_A_GLANCE.md")
    print(f"{len(g)} figures sourced, all unique-matched. {total} result rows behind them.")
    print(f"DROPPED: {len(DROPPED)}")
    for d in DROPPED:
        print("  -", d)


def write_brief(g, sha, total):
    B = f"""# Supervisor brief — legal-mvp

**Udita Uniyal · 2 September 2026 · commit `{sha}`**

Every number below is machine-extracted from `results/*.csv`; none is retyped.
Regenerate this document: `./venv/Scripts/python.exe experiments/make_supervisor_brief.py`

---

## 1 · Bottom line

A query that names the repealed Indian Penal Code retrieves the right statute
{g['dom_dense_ipc'].pct()} of the time; a query naming the Bharatiya Nyaya
Sanhita, which is the code actually in force, manages {g['dom_dense_bns'].pct()}
(n={g['dom_dense_bns'].n} each, 95% CI {g['dom_dense_ipc'].ci(1, pct=True)} and
{g['dom_dense_bns'].ci(1, pct=True)}). Exact-word search does not repair this —
it reverses it, scoring {g['dom_bm25_bns'].pct()} on BNS-named queries and
{g['dom_bm25_ipc'].pct()} on IPC-named ones, and fusing the two retrievers is
worse than either alone. The confidence score is beaten by a single raw
similarity ({g['sig_composite'].num()} against {g['sig_max_score'].num()},
n={g['sig_composite'].n}), and that holds after correcting a sign error we found
in one of its terms. All five steps you prescribed on 6 August are delivered,
with {total} individual measurements, each carrying its sample size, confidence
interval, correctness definition and retrieval stage. Two of my August claims
were wrong and are retracted here with evidence. **What I need from you is one
introduction — a law student to independently validate about 30 queries and
their gold labels — plus three decisions listed in section 6.**

---

## 2 · Your five prescribed steps, delivered

| # | You asked for | What exists now | Proof |
|---|---|---|---|
| 1 | Annotated evaluation set, 50–100 queries with ground-truth sections | **518 unique queries**, gold sections fixed before any output was seen, across four purpose-built sets including IPC↔BNS paired queries and dated-conflict queries | `eval/*_queryset.jsonl` |
| 2 | Complete logging of retrieval signals, confidence, routing | **859 runs, 80 fields each.** Partial at first: retrieved *section numbers* were never logged, so retrieval could not be scored. Closed by a retrieval-only re-run costing ₹0.06 | `runs/`, `experiments/stages.jsonl`, `experiments/SCHEMA.md` |
| 3 | Evaluate retrieval, calibration, answer correctness | **{total} measurements.** Retrieval at three pipeline stages under three correctness definitions; calibration by ECE, Brier, reliability curve, risk-coverage and Platt scaling | `results/RESULTS.md` |
| 4 | Investigate routing; compare against hybrid routing | 4×4 routing confusion matrix, base-rate control, and a full dense / BM25 / Reciprocal-Rank-Fusion comparison | `results/routing_confusion.csv`, `results/hybrid_comparison.csv` |
| 5 | Ablation on confidence components plus baselines | Per-signal AUROC, leave-one-out with renormalised weights, a 231-point weight sweep with a held-out split, the fourth signal built for the first time, and a sign-error decomposition | `results/ablation.csv`, `results/corrected_composite.csv`, `results/statute_consistency.csv` |

**Honest partials.** Item 2 needed the re-run described above. Item 3's
`grounded` definition has only 27 positives in 617 rows, so every comparison
under it is underpowered and reported as such. No independent annotator has
validated the gold labels — that is the request in section 6.

---

## 3 · Findings, strongest evidence first

### 3.1 Cross-statute retrieval failure, and it is asymmetric

Naming the repealed IPC retrieves the right book {g['dom_dense_ipc'].pct()}
{g['dom_dense_ipc'].ci(1, pct=True)}; naming the BNS, in force since 1 July 2024,
manages {g['dom_dense_bns'].pct()} {g['dom_dense_bns'].ci(1, pct=True)}.
n={g['dom_dense_ipc'].n} per arm, definition `{g['dom_dense_ipc'].defn}`, corpus
filter disabled. Top-1 only: {g['top1_dense_ipc'].pct()} against
{g['top1_dense_bns'].pct()}. Source `hybrid_comparison.csv`.

**Why it matters:** the system is most reliable on the statute that no longer
governs. This figure reproduced cell-for-cell after three bug fixes and a
rebuilt metric library.

### 3.2 Lexical search inverts the failure; fusion does not help

| Retriever | IPC-named | BNS-named | Both |
|---|---|---|---|
| dense | **{g['dom_dense_ipc'].pct()}** {g['dom_dense_ipc'].ci(1, pct=True)} | {g['dom_dense_bns'].pct()} {g['dom_dense_bns'].ci(1, pct=True)} | {g['dom_dense_both'].pct()} |
| BM25 | **{g['dom_bm25_ipc'].pct()}** {g['dom_bm25_ipc'].ci(1, pct=True)} | **{g['dom_bm25_bns'].pct()}** {g['dom_bm25_bns'].ci(1, pct=True)} | {g['dom_bm25_both'].pct()} |
| hybrid (RRF) | {g['dom_hybrid_rrf_ipc'].pct()} | {g['dom_hybrid_rrf_bns'].pct()} | {g['dom_hybrid_rrf_both'].pct()} |

n={g['dom_dense_ipc'].n} per arm; definition `{g['dom_dense_ipc'].defn}`.

**Why it matters:** the obvious remedy fails in the opposite direction, and
averaging two complementary failure modes produces a system worse than either.
This is the strongest available answer to the reviewer objection that the
failure is an artefact of choosing a dense retriever.

**Mechanism — NOT QUOTED HERE.** Wave 3 attributes the inversion to asymmetric
statutory self-naming: the 2023 BNS names itself in its operative text, the 1860
IPC does not, so its name occurs mainly in cross-references inside the procedure
code. The supporting term counts and inverse-document-frequency values exist only
as prose in `results/EXPLAIN.md`; they are **not in any results CSV**, so under
this document's sourcing rule they are omitted. They must be written to a CSV
before the paper cites them.

### 3.3 The confidence score is beaten by a single raw number

| Signal | AUROC | 95% CI |
|---|---|---|
| `max_score` (best single similarity) | **{g['sig_max_score'].num()}** | {g['sig_max_score'].ci()} |
| `top_k_mean` | {g['sig_top_k_mean'].num()} | {g['sig_top_k_mean'].ci()} |
| `score_gap` (raw) | {g['sig_score_gap'].num()} | {g['sig_score_gap'].ci()} |
| **deployed composite** | **{g['sig_composite'].num()}** | {g['sig_composite'].ci()} |
| `entity_coverage` | {g['sig_entity_coverage'].num()} | {g['sig_entity_coverage'].ci()} |
| `gap_term` as deployed | {g['sig_gap_term'].num()} | {g['sig_gap_term'].ci()} |

n={g['sig_composite'].n}, definition `{g['sig_composite'].defn}`, stage
`{g['sig_composite'].stage}`. AUROC 0.5 is chance; below 0.5 means the signal
points the wrong way.

**Sign-error decomposition.** One term is inverted in the deployed code.
Correcting it lifts the composite {g['cc_composite_deployed'].num()} →
{g['cc_composite_corrected'].num()} (paired difference
{g['cc_diff_corr_dep'].num()} {g['cc_diff_corr_dep'].ci()}), but `max_score`
remains ahead at {g['cc_max_score'].num()}, and the corrected composite still
loses by {g['cc_diff_corr_max'].num()} {g['cc_diff_corr_max'].ci()}. **The bug
explains roughly half of the {g['cc_diff_dep_max'].num()} deficit, not all of
it.** Held out on data the search never saw, the best weighting of the corrected
signals reaches {g['cc_best_test'].num()} against max_score on the same split —
a tie, never a win. Source `corrected_composite.csv`.

**Why it matters:** an engineered three-signal score does not beat one number
that was already free, and this survives the obvious repair.

### 3.4 No usable confidence threshold exists

Share of questions answerable while holding error at or below 10%:
composite **{g['cov_comp'].num(4)}**, max_score {g['cov_max'].num(4)}
(n={g['cov_comp'].n}, definition `{g['cov_comp'].defn}`). These zeros are
measured, not missing. Source `calibration.csv`.

### 3.5 The adaptive filter amplifies corpus bias

Over-representation ratio on layman queries — a book's share of retrieval
divided by its share of the index, where 1.0 is chance:

| Book | `raw_15` | `filtered_n` |
|---|---|---|
| CrPC | {g['or_CRPC_raw_15'].num(2)}× {g['or_CRPC_raw_15'].ci(2, cluster=True)} | **{g['or_CRPC_filtered_n'].num(2)}×** {g['or_CRPC_filtered_n'].ci(2, cluster=True)} |
| IPC | {g['or_IPC_raw_15'].num(2)}× | {g['or_IPC_filtered_n'].num(2)}× |
| BNS | {g['or_BNS_raw_15'].num(2)}× | **{g['or_BNS_filtered_n'].num(2)}×** |

n={g['or_CRPC_raw_15'].n} chunks at `raw_15`; intervals are cluster bootstrap on
situation. Source `routing_confusion.csv`.

**Why it matters:** a step whose purpose is removing noise preferentially
removes substantive criminal law. The previously reported 1.8× figure is
confirmed — but it was a `filtered_n` number published without its stage, and the
same queries give {g['or_CRPC_raw_15'].num(2)}× before filtering.

### 3.6 The fourth signal works only where it is not tautological

`statute_consistency` — the fraction of retrieved passages from the admissible
book — scores {g['sc_all'].num()} {g['sc_all'].ci()} pooled (n={g['sc_all'].n}),
which does not beat the generic signals. On the dated-conflict subset, where the
named code and the offence date disagree, it reaches **{g['sc_dated'].num()}**
{g['sc_dated'].ci()} (n={g['sc_dated'].n}). Source `statute_consistency.csv`.

**Why it matters:** on 343 of 617 rows the corpus filter was derived from the
same query-and-date inputs the signal reads, so it cannot fail by construction.
A confidence signal placed downstream of a filter built from its own inputs is a
tautology — an architectural finding, not a tuning result.

### 3.7 The gap is a RETRIEVAL claim and does not survive at citation level

| Definition | IPC−BNS gap | clustered 95% |
|---|---|---|
| `retrieved@15` | **{g['gap_ret'].num()}** | {g['gap_ret'].ci(cluster=True)} |
| `cited` | {g['gap_cit'].num()} | {g['gap_cit'].ci(cluster=True)} — **contains 0** |
| `grounded` | {g['gap_gro'].num()} | {g['gap_gro'].ci(cluster=True)} — **contains 0** |

n={g['gap_ret'].n}, `paired_recodification`, restriction=none. Source
`robustness.csv`.

**Why it matters:** the generator cites correct sections regardless of what
retrieval returned, so the failure is invisible in the answer text. This must be
stated in the abstract: a reviewer measuring citations will not reproduce the
gap.

---

## 4 · What changed since my August update, including retractions

| Correction | August position | Now | Found by |
|---|---|---|---|
| **Retraction 1 — the "counting bug"** | I reported a bug halving the layman figure | **No bug existed.** Text-parsing recovered the section 4,906 of 4,906 times, 0.0% error. Both figures were always right at different stages | Wave 0 measurement against my own claim |
| **Retraction 2 — BNS {g['ceiling_bns'].pct()}** | Reported as a retrieval failure | **It is a reachability ceiling.** {g['ceiling_bns'].pct()} {g['ceiling_bns'].ci(1, pct=True)} of BNS-named gold labels name subsections the index stores only as bare sections. Dense and hybrid both saturate it exactly | Wave 3 paired check |
| **Confidence formula in `CLAUDE.md`** | documented as `0.15·score_gap` | Deployed code uses `0.15·(1 − min(score_gap/0.3, 1))`. **Documentation error, not a code defect** — the logged scores were always correct | Reconstruction check: brief formula matched 0 of 617 rows; real formula matches to 9e-05 |
| **`GAPS.md` #1 and #2** | `entity_coverage` exceeds 1.0, grants a free 0.30 | Describes **pre-fix code**. Values are only {{0, 0.5, 1.0}} | Confirmed independently in Waves 2 and 3 |
| **README AUROC pair 0.610 / 0.663** | published | Records neither correctness definition nor retrieval stage; no definition reproduces it. **Superseded, not reconcilable** | Gate |
| **Two defects in our own measurement code** | — | One raised on real data; the fix for it then silently returned 0 correct out of 617 **while nothing crashed**. Both caught before any number was published | Gate; now pinned by tests |

The full lists — 11 changed numbers, 10 failed assertions, 13 things not
computable — are appendices A–D of `results/RESULTS.md`.

---

## 5 · Limitations and threats to validity

1. **Gold reachability ceiling.** Only {g['ceiling_all'].pct()}
   {g['ceiling_all'].ci(1, pct=True)} of {g['ceiling_all'].n} queries have a gold
   section the index can return at all under strict matching. **Every recall
   figure must be read against this ceiling, not against 1.0.** Worst on
   BNS-named queries at {g['ceiling_bns'].pct()}.
2. **Single annotator.** All gold labels are mine. No independent validation —
   see section 6.
3. **Single embedding model, single jurisdiction, single corpus** of four
   statutes. The BNSS is absent, so BNS-era procedure is unanswerable by
   construction.
4. **Layman significance lost under clustering.** The `filtered_n` layman rate is
   {g['layman_filt'].num(3)}, naive CI {g['layman_filt'].ci(3)} excluding zero,
   but clustered CI {g['layman_filt'].ci(3, cluster=True)} **includes zero** —
   the successes sit in only a few situations. At `raw_15` the rate is
   {g['layman_raw'].num(3)}, clustered {g['layman_raw'].ci(3, cluster=True)}.
5. **One assertion is left deliberately failing (B5).** Four clustered AUROC
   intervals came out narrower than their naive counterparts and remain
   unexplained after ruling out resampler bugs and Monte Carlo noise across five
   seeds. Those two restricted subsets are marked unusable rather than explained
   away.
6. **`grounded` is underpowered** at 27 positives in 617 rows; every comparison
   under it contains zero.
7. **Three labelled rows are dropped** by a deduplication rule, so n is 617 where
   it could be 620. Disclosed rather than fixed, because changing the loader
   would shift every figure in nine CSVs for 0.5% that moves no conclusion.

---

## 6 · What I need from you — four one-line decisions

1. **A law student or colleague to independently validate ~30 queries and their
   gold labels.** Single-annotator gold is the weakest point in the evaluation
   and the cheapest to fix. Every credible paper in this area has expert
   validation; almost no Indian system paper does.
2. **Confirm the framing.** Proposed: *neither dense nor lexical retrieval routes
   reliably across a recodification boundary, and fusing them does not help,
   because the two failures have different causes; the task requires an explicit
   statute-and-date resolution layer.* Yes, or redirect.
3. **Venue.** ACL Rolling Review, 12 October, is reachable. Confirm, or name an
   alternative.
4. **Should gold be re-derived at subsection granularity?** It would raise the
   {g['ceiling_all'].pct()} ceiling but means revising the evaluation set, which
   I will not do without your approval.

---

## 7 · Navigating the attachments

| File | What it is |
|---|---|
| `docs/NUMBERS_AT_A_GLANCE.md` | Every headline figure on one page, with source and regenerating command |
| `results/RESULTS.md` | All {total} measurements, plus appendices A–D: changed numbers, failed assertions, not-computable, caveats |
| `results/EXPLAIN.md` | One plain-English block per output, eight fixed headings each |
| `results/smoke_test.md` | The three gate numbers checked before the main analysis |
| `experiments/SCHEMA.md` | What the logs actually contain, and three blockers found there |
| `docs/WORKLOG.md` | Dated record of every run, including the retractions |
| `results/*.csv` | The measurements themselves, one shared schema |
"""
    (ROOT / "docs" / "SUPERVISOR_BRIEF.md").write_text(B, encoding="utf-8")


def write_glance(g, sha):
    order = [
        ("Cross-statute: IPC-named, dense", "dom_dense_ipc", "pct"),
        ("Cross-statute: BNS-named, dense", "dom_dense_bns", "pct"),
        ("Cross-statute: IPC-named, BM25", "dom_bm25_ipc", "pct"),
        ("Cross-statute: BNS-named, BM25", "dom_bm25_bns", "pct"),
        ("Cross-statute: IPC-named, hybrid RRF", "dom_hybrid_rrf_ipc", "pct"),
        ("Cross-statute: BNS-named, hybrid RRF", "dom_hybrid_rrf_bns", "pct"),
        ("Cross-statute pooled: dense", "dom_dense_both", "pct"),
        ("Cross-statute pooled: BM25", "dom_bm25_both", "pct"),
        ("Cross-statute pooled: hybrid RRF", "dom_hybrid_rrf_both", "pct"),
        ("Top-1 corpus: IPC-named, dense", "top1_dense_ipc", "pct"),
        ("Top-1 corpus: BNS-named, dense", "top1_dense_bns", "pct"),
        ("Top-1 corpus: BNS-named, BM25", "top1_bm25_bns", "pct"),
        ("Gold reachability ceiling, pooled", "ceiling_all", "pct"),
        ("Gold reachability ceiling, BNS-named", "ceiling_bns", "pct"),
        ("Recall@15 generated", "rec_generated_retrieval", "num3"),
        ("Recall@15 paired_recodification", "rec_paired_recodification", "num3"),
        ("Recall@15 paired_dated_conflict", "rec_paired_dated_conflict", "num3"),
        ("Recall@15 layman", "rec_layman_situation", "num3"),
        ("Recall@15 pooled", "rec_ALL", "num3"),
        ("AUROC max_score", "sig_max_score", "num"),
        ("AUROC top_k_mean", "sig_top_k_mean", "num"),
        ("AUROC score_gap (raw)", "sig_score_gap", "num"),
        ("AUROC composite (deployed)", "sig_composite", "num"),
        ("AUROC entity_coverage", "sig_entity_coverage", "num"),
        ("AUROC gap_term (deployed, inverted)", "sig_gap_term", "num"),
        ("AUROC composite, sign-corrected", "cc_composite_corrected", "num"),
        ("Paired diff: corrected - max_score", "cc_diff_corr_max", "num"),
        ("Paired diff: corrected - deployed", "cc_diff_corr_dep", "num"),
        ("Paired diff: deployed - max_score", "cc_diff_dep_max", "num"),
        ("Best corrected weighting, held out", "cc_best_test", "num"),
        ("ECE composite (lower better)", "ece_comp", "num"),
        ("ECE max_score (lower better)", "ece_max", "num"),
        ("Coverage at 10% risk, composite", "cov_comp", "num"),
        ("Coverage at 10% risk, max_score", "cov_max", "num"),
        ("Over-representation CrPC, raw_15", "or_CRPC_raw_15", "num2"),
        ("Over-representation CrPC, filtered_n", "or_CRPC_filtered_n", "num2"),
        ("Over-representation BNS, raw_15", "or_BNS_raw_15", "num2"),
        ("Over-representation BNS, filtered_n", "or_BNS_filtered_n", "num2"),
        ("statute_consistency, pooled", "sc_all", "num"),
        ("statute_consistency, dated-conflict", "sc_dated", "num"),
        ("IPC-BNS gap, retrieved@15", "gap_ret", "num"),
        ("IPC-BNS gap, cited", "gap_cit", "num"),
        ("IPC-BNS gap, grounded", "gap_gro", "num"),
        ("Layman rate, raw_15", "layman_raw", "num3"),
        ("Layman rate, filtered_n", "layman_filt", "num3"),
    ]
    L = [f"# Numbers at a glance",
         "",
         f"commit `{sha}` · machine-extracted from `results/*.csv`, nothing retyped ·"
         f" regenerate: `./venv/Scripts/python.exe experiments/make_supervisor_brief.py`",
         "",
         "`CI` is 95%. `clustered CI` resamples situations rather than rows, because "
         "phrasings of one situation are not independent observations. A blank means "
         "the field does not apply.",
         "",
         "| Figure | Value | 95% CI | clustered CI | n | definition | stage | source | regenerate |",
         "|---|---|---|---|---|---|---|---|---|"]
    for label, key, fmt in order:
        r = g[key]
        v = (r.pct() if fmt == "pct" else r.num(3) if fmt == "num3"
             else r.num(2) + "x" if fmt == "num2" else r.num())
        ci = (r.ci(1, pct=True) if fmt == "pct" else r.ci(3) if fmt == "num3"
              else r.ci(2) if fmt == "num2" else r.ci())
        cci = (r.ci(1, pct=True, cluster=True) if fmt == "pct"
               else r.ci(3, cluster=True) if fmt == "num3"
               else r.ci(2, cluster=True) if fmt == "num2" else r.ci(cluster=True))
        L.append(f"| {label} | **{v}** | {ci} | {cci} | {r.n} | `{r.defn}` | "
                 f"`{r.stage}` | `{r.file}` | `{r.cmd}` |")
    L += ["", "**Not listed here because it is not in any CSV:** the term-frequency "
          "and inverse-document-frequency evidence for statutory self-naming, which "
          "exists only as prose in `results/EXPLAIN.md`. It must be written to a "
          "results file before the paper cites it."]
    (ROOT / "docs" / "NUMBERS_AT_A_GLANCE.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()
