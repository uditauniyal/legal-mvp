# Supervisor brief — legal-mvp

**Udita Uniyal · 2 September 2026 · commit `69388f5`**

Every number below is machine-extracted from `results/*.csv`; none is retyped.
Regenerate this document: `./venv/Scripts/python.exe experiments/make_supervisor_brief.py`

---

## 1 · Bottom line

A query that names the repealed Indian Penal Code retrieves the right statute
97.0% of the time; a query naming the Bharatiya Nyaya
Sanhita, which is the code actually in force, manages 51.5%
(n=33 each, 95% CI [84.7%, 99.5%] and
[35.2%, 67.5%]). Exact-word search does not repair this —
it reverses it, scoring 97.0% on BNS-named queries and
0.0% on IPC-named ones, and fusing the two retrievers is
worse than either alone. The confidence score is beaten by a single raw
similarity (0.6631 against 0.7837,
n=617), and that holds after correcting a sign error we found
in one of its terms. All five steps you prescribed on 6 August are delivered,
with 2748 individual measurements, each carrying its sample size, confidence
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
| 3 | Evaluate retrieval, calibration, answer correctness | **2748 measurements.** Retrieval at three pipeline stages under three correctness definitions; calibration by ECE, Brier, reliability curve, risk-coverage and Platt scaling | `results/RESULTS.md` |
| 4 | Investigate routing; compare against hybrid routing | 4×4 routing confusion matrix, base-rate control, and a full dense / BM25 / Reciprocal-Rank-Fusion comparison | `results/routing_confusion.csv`, `results/hybrid_comparison.csv` |
| 5 | Ablation on confidence components plus baselines | Per-signal AUROC, leave-one-out with renormalised weights, a 231-point weight sweep with a held-out split, the fourth signal built for the first time, and a sign-error decomposition | `results/ablation.csv`, `results/corrected_composite.csv`, `results/statute_consistency.csv` |

**Honest partials.** Item 2 needed the re-run described above. Item 3's
`grounded` definition has only 27 positives in 617 rows, so every comparison
under it is underpowered and reported as such. No independent annotator has
validated the gold labels — that is the request in section 6.

---

## 3 · Findings, strongest evidence first

### 3.1 Cross-statute retrieval failure, and it is asymmetric

Naming the repealed IPC retrieves the right book 97.0%
[84.7%, 99.5%]; naming the BNS, in force since 1 July 2024,
manages 51.5% [35.2%, 67.5%].
n=33 per arm, definition `dominant_corpus_among_top15`, corpus
filter disabled. Top-1 only: 90.9% against
42.4%. Source `hybrid_comparison.csv`.

**Why it matters:** the system is most reliable on the statute that no longer
governs. This figure reproduced cell-for-cell after three bug fixes and a
rebuilt metric library.

### 3.2 Lexical search inverts the failure; fusion does not help

| Retriever | IPC-named | BNS-named | Both |
|---|---|---|---|
| dense | **97.0%** [84.7%, 99.5%] | 51.5% [35.2%, 67.5%] | 74.2% |
| BM25 | **0.0%** [0.0%, 10.4%] | **97.0%** [84.7%, 99.5%] | 48.5% |
| hybrid (RRF) | 45.5% | 78.8% | 62.1% |

n=33 per arm; definition `dominant_corpus_among_top15`.

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
| `max_score` (best single similarity) | **0.7837** | [0.7470, 0.8195] |
| `top_k_mean` | 0.7571 | [0.7188, 0.7939] |
| `score_gap` (raw) | 0.7298 | [0.6894, 0.7684] |
| **deployed composite** | **0.6631** | [0.6172, 0.7096] |
| `entity_coverage` | 0.5806 | [0.5376, 0.6232] |
| `gap_term` as deployed | 0.2702 | [0.2316, 0.3106] |

n=617, definition `retrieved@k`, stage
`raw_15`. AUROC 0.5 is chance; below 0.5 means the signal
points the wrong way.

**Sign-error decomposition.** One term is inverted in the deployed code.
Correcting it lifts the composite 0.6631 →
0.7207 (paired difference
0.0576 [0.0376, 0.0780]), but `max_score`
remains ahead at 0.7837, and the corrected composite still
loses by -0.0630 [-0.0946, -0.0325]. **The bug
explains roughly half of the -0.1207 deficit, not all of
it.** Held out on data the search never saw, the best weighting of the corrected
signals reaches 0.7631 against max_score on the same split —
a tie, never a win. Source `corrected_composite.csv`.

**Why it matters:** an engineered three-signal score does not beat one number
that was already free, and this survives the obvious repair.

### 3.4 No usable confidence threshold exists

Share of questions answerable while holding error at or below 10%:
composite **0.0000**, max_score 0.0486
(n=617, definition `retrieved@k`). These zeros are
measured, not missing. Source `calibration.csv`.

### 3.5 The adaptive filter amplifies corpus bias

Over-representation ratio on layman queries — a book's share of retrieval
divided by its share of the index, where 1.0 is chance:

| Book | `raw_15` | `filtered_n` |
|---|---|---|
| CrPC | 1.49× [1.22, 1.75] | **1.80×** [1.47, 2.04] |
| IPC | 0.59× | 0.48× |
| BNS | 0.58× | **0.34×** |

n=1800 chunks at `raw_15`; intervals are cluster bootstrap on
situation. Source `routing_confusion.csv`.

**Why it matters:** a step whose purpose is removing noise preferentially
removes substantive criminal law. The previously reported 1.8× figure is
confirmed — but it was a `filtered_n` number published without its stage, and the
same queries give 1.49× before filtering.

### 3.6 The fourth signal works only where it is not tautological

`statute_consistency` — the fraction of retrieved passages from the admissible
book — scores 0.6845 [0.6557, 0.7139] pooled (n=617),
which does not beat the generic signals. On the dated-conflict subset, where the
named code and the offence date disagree, it reaches **0.8300**
[0.7819, 0.8750] (n=197). Source `statute_consistency.csv`.

**Why it matters:** on 343 of 617 rows the corpus filter was derived from the
same query-and-date inputs the signal reads, so it cannot fail by construction.
A confidence signal placed downstream of a filter built from its own inputs is a
tautology — an architectural finding, not a tuning result.

### 3.7 The gap is a RETRIEVAL claim and does not survive at citation level

| Definition | IPC−BNS gap | clustered 95% |
|---|---|---|
| `retrieved@15` | **0.5455** | [0.3030, 0.7576] |
| `cited` | -0.0303 | [-0.1212, 0.0606] — **contains 0** |
| `grounded` | -0.0303 | [-0.0909, 0.0000] — **contains 0** |

n=66, `paired_recodification`, restriction=none. Source
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
| **Retraction 2 — BNS 33.3%** | Reported as a retrieval failure | **It is a reachability ceiling.** 33.3% [19.8%, 50.4%] of BNS-named gold labels name subsections the index stores only as bare sections. Dense and hybrid both saturate it exactly | Wave 3 paired check |
| **Confidence formula in `CLAUDE.md`** | documented as `0.15·score_gap` | Deployed code uses `0.15·(1 − min(score_gap/0.3, 1))`. **Documentation error, not a code defect** — the logged scores were always correct | Reconstruction check: brief formula matched 0 of 617 rows; real formula matches to 9e-05 |
| **`GAPS.md` #1 and #2** | `entity_coverage` exceeds 1.0, grants a free 0.30 | Describes **pre-fix code**. Values are only {0, 0.5, 1.0} | Confirmed independently in Waves 2 and 3 |
| **README AUROC pair 0.610 / 0.663** | published | Records neither correctness definition nor retrieval stage; no definition reproduces it. **Superseded, not reconcilable** | Gate |
| **Two defects in our own measurement code** | — | One raised on real data; the fix for it then silently returned 0 correct out of 617 **while nothing crashed**. Both caught before any number was published | Gate; now pinned by tests |

The full lists — 11 changed numbers, 10 failed assertions, 13 things not
computable — are appendices A–D of `results/RESULTS.md`.

---

## 5 · Limitations and threats to validity

1. **Gold reachability ceiling.** Only 85.7%
   [82.4%, 88.5%] of 518 queries have a gold
   section the index can return at all under strict matching. **Every recall
   figure must be read against this ceiling, not against 1.0.** Worst on
   BNS-named queries at 33.3%.
2. **Single annotator.** All gold labels are mine. No independent validation —
   see section 6.
3. **Single embedding model, single jurisdiction, single corpus** of four
   statutes. The BNSS is absent, so BNS-era procedure is unanswerable by
   construction.
4. **Layman significance lost under clustering.** The `filtered_n` layman rate is
   0.075, naive CI [0.033, 0.125] excluding zero,
   but clustered CI [0.000, 0.167] **includes zero** —
   the successes sit in only a few situations. At `raw_15` the rate is
   0.150, clustered [0.033, 0.275].
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
   85.7% ceiling but means revising the evaluation set, which
   I will not do without your approval.

---

## 7 · Navigating the attachments

| File | What it is |
|---|---|
| `docs/NUMBERS_AT_A_GLANCE.md` | Every headline figure on one page, with source and regenerating command |
| `results/RESULTS.md` | All 2748 measurements, plus appendices A–D: changed numbers, failed assertions, not-computable, caveats |
| `results/EXPLAIN.md` | One plain-English block per output, eight fixed headings each |
| `results/smoke_test.md` | The three gate numbers checked before the main analysis |
| `experiments/SCHEMA.md` | What the logs actually contain, and three blockers found there |
| `docs/WORKLOG.md` | Dated record of every run, including the retractions |
| `results/*.csv` | The measurements themselves, one shared schema |
