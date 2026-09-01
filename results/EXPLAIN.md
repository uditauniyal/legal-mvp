# EXPLAIN.md

One block per output file. Eight headings every time. A task is not complete until its block exists.

---

## metrics_lib — the shared metric library
Output file: `experiments/metrics_lib.py`
Regenerate with: `python -m pytest tests/test_metrics_known_answers.py -q`
Owner: Wave 0, Task B

### 1. ELI5 — what does this measure?
It measures nothing by itself. It is the single set of measuring instruments every later experiment borrows, so that five people measuring the same thing get the same answer.

Think of a school where five teachers each mark the same exam with their own homemade ruler. Four rulers are a millimetre off. Every mark is *nearly* right, and no two agree. This file is the one ruler everybody uses.

It holds: how often the right law section was found (`recall_at_k`), how far down the list it appeared (`reciprocal_rank`), whether a confidence score can tell good answers from bad (`auroc`), whether "70% confident" actually means right 70% of the time (`ece`), and how much error you accept if you only answer the questions you are surest about (`risk_coverage_curve`).

### 2. Technically
- `auroc` — Mann-Whitney U with average ranks, so ties count 0.5. Exact, not trapezoidal.
- `auroc_bootstrap_ci`, `paired_bootstrap_auroc_diff` — 10,000-sample percentile bootstrap, `SEED = 20260901`. Paired because both scores are measured on the same queries; two overlapping independent intervals can still hide a clearly non-zero paired difference.
- `ece` — Expected Calibration Error, quantile (equal-mass) bins by default.
- `platt_scale` — two-parameter logistic fit by `scipy.optimize.minimize`, BFGS.
- `aurc`, `coverage_at_risk` — selective-prediction curve over score-descending order.
- `cluster_bootstrap` — resamples clusters, not rows.
- `wilson` — 95% Wilson score interval.

### 3. What the number came out as
No measurement. Verification only: **33 of 33** known-answer tests pass; full suite **175** (was 142). Loaded against real data it returns **621 rows** after deduplication, dropping **238 of 859**. Definition: n/a. Stage: n/a.

### 4. How to read it
There is no "good" value here. The library is correct or it is not. A failing known-answer test means every number that function would ever produce is worthless. Suspicious signs: an AUROC of exactly 0.5 on real data (possible, but check the labels first), an ECE of exactly 0.0 (almost certainly a binning bug), or any function returning the same value for different inputs.

### 5. What this means for the paper
It supports nothing directly and underwrites everything. Reviewers ask whether numbers are reproducible; fixed seeds plus known-answer tests plus one shared implementation is the answer. It also removes the class of defect that cost this project six months — a metric returning a believable wrong number.

### 6. What broke while computing this
Two things.

**scikit-learn and rank_bm25 are not installed.** The plan specifies scikit-learn. It was not installed, because installing into this venv previously upgraded starlette and broke fastapi. Everything was implemented on numpy and scipy, which are present. No behaviour lost. `rank_bm25` is only needed in Wave 3 and is flagged there.

**One known-answer test failed, and the test was wrong, not the code.** It asserted that lenient matching should collapse `IPC 498A` onto `IPC 498`. That is what the older `core/citations.py` did, and it was wrong: a parenthesised number is a *part* of a section (318(4) really is inside 318), whereas a letter suffix is a *separate* section inserted by amendment (498A, cruelty by a husband, 1983, is a different offence from 498, enticing a married woman). The library widens subsections only. The test was corrected to assert the better rule, and the deviation is documented in the test itself.

### 7. What I could not compute, and why
One specified test could not be implemented as written. The plan asked for `normalise_section("IPC Section 302") == normalise_section("Section 302")` as **string** equality. Satisfying that requires dropping the statute from the canonical form — which would make `IPC 302` and `BNS 302` identical strings. Telling those apart is the entire subject of this paper, so string equality would manufacture the exact confusion being measured.

Implemented instead as `same_section("IPC Section 302", "Section 302") is True`, which preserves the intent — an unattributed reference is comparable, because statute text never names its own statute — while `same_section("IPC Section 302", "BNS Section 302")` stays `False`. Both are pinned as tests.

### 8. What surprised me
`load_logs()` drops **238 of 859** rows to deduplication — 28%. Larger than expected. It is benign: 99 are baseline-versus-intervention pairs, which are two conditions rather than repeats, and of 228 genuine same-condition repeats, 206 (90.4%) are byte-identical, `n_citations` never differs, and confidence differs by at most 0.0005. But any analysis reading the raw files without deduplicating would have inflated every proportion by roughly a quarter.
