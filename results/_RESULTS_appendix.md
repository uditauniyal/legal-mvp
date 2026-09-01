## A. Every number that CHANGED from what README.md publishes

Old value, new value, and what caused the change. A change caused by a
*documentation* error is marked as such — the measurement was always right.

| # | What | README / earlier | Measured now | Cause |
|---|---|---|---|---|
| A1 | Layman retrieval "counting bug" | claimed 7.5% should be 15.0% | **both were always correct** — 7.5% at `filtered_n`, 15.0% at `raw_15` | **RETRACTED.** No bug existed. Text-parsing recovered the section 4,906/4,906 times, a 0.0% error rate. An unfiltered probe had been compared against a filtered figure |
| A2 | Confidence formula | `0.55·top_k_mean + 0.15·score_gap + 0.30·entity_coverage` | `0.55·top_k_mean + 0.15·(1 − min(score_gap/0.3, 1)) + 0.30·entity_coverage` | **Documentation error, not a code defect.** The brief formula reproduces 0 of 617 logged composites (max deviation 0.148); the real one agrees to 9.0e-05 on every row. Found by S4's reconstruction check |
| A3 | `entity_coverage` AUROC | 0.492 (chance) | **0.581** logged · **0.605** from payload | `GAPS.md` #1 and #2 describe **pre-fix code**. In these logs the signal takes only {0, 0.5, 1.0}, never exceeds 1.0, and grants no free 0.30 default. Confirmed independently by Wave 2 and Wave 3 |
| A4 | Composite vs max_score AUROC | 0.610 vs 0.663 | **0.663 vs 0.784** under `retrieved@15` | The README pair records no correctness definition and no stage, and none of the three definitions reproduces it. Treat as **superseded, not reconcilable** |
| A5 | Supported word for the composite | "worse" | **"worse" under `retrieved@15`** (−0.121, p<0.0001) and `cited`; **"no better than" under `grounded`** (−0.058, p=0.32) | Paired bootstrap replaces eye-comparison of two intervals. `grounded` has only 27 positives and lacks the power |
| A6 | CrPC over-representation, layman | 1.8× | **1.7974× at `filtered_n`** · **1.49× at `raw_15`** | Verified, not refuted. But the published figure carried **no stage label**, and the two stages differ by a third |
| A7 | BNS-named gold-section recall | 33.3%, reported at the GATE as a retrieval failure | **33.3% is the ceiling** | 22 of 33 BNS gold labels name subsections (`BNS 318(4)`) that the index stores only as bare sections (`318`). Unreachable by any retriever under strict matching. Dense and hybrid both score 11/33 — **saturating the ceiling exactly** |
| A8 | `paired_dated_conflict` Recall@15 | 0.492 | **0.293 baseline / 0.694 intervention** | The 197 rows are 99 baseline plus 98 of the *same* queries under the Phase H intervention. The pooled figure averages two different systems and must never be quoted |
| A9 | Phase G "lenient" citation column | as published | **inflated** | The old rule stripped any trailing letter, collapsing `IPC 498A` onto `IPC 498`. A letter suffix denotes a section inserted by amendment (498A, cruelty by a husband, 1983), not a part of 498 |
| A10 | Logged confidence tier | `HIGH` on all 859 records | **HIGH 490 · MEDIUM 354 · LOW 15**; 369/859 = 42.96% mislabelled [39.69, 46.29] | `prompt_variant` was initialised once and never reassigned. **No published number is affected** — the field is written by `app.py` and read by nothing |
| A11 | Citation statute attribution | proximity-based | **1,060 of 6,687 units (15.9%) become UNKNOWN; 72 flip statute** | Binding now happens only within a citation unit. **70 of 72 flips (97.2%) are recodification pairs** — the error landed on the treatment variable |

### Numbers that did NOT change, and that is the result

| What | Value | Note |
|---|---|---|
| IPC-named cross-statute accuracy | **97.0%** [84.7, 99.5] | Reproduced **cell-for-cell** after three bug fixes, a new metric library and a fresh run against the live index |
| BNS-named cross-statute accuracy | **51.5%** [35.2, 67.5] | As above |
| Top-1 variants | 90.9% / 42.4% | As above |
| `grounded` positive count | 27 of 617 | Strict by design, not by defect |

---

## B. Every known-answer test or assertion that FAILED

Including ones fixed in seconds. Two of these were defects in code written for
this project's own measurement library, and both would have produced believable
wrong numbers.

| # | Where | What failed | Resolution |
|---|---|---|---|
| B1 | Wave 0, known-answer tests | `same_section("IPC 498A", "IPC 498", lenient=True)` returned True | **The test was wrong, not the code.** A letter suffix denotes a separate section inserted by amendment. Test corrected to assert the stricter, legally right behaviour |
| B2 | GATE | `same_section` raised `ValueError` on real logged data | `normalise_section` handled Sections only; Constitution *Articles* and CPC *Orders*/*Rules* fell through to a fallback returning no `:` separator. 28 distinct such strings, `CONSTITUTION Article 226` 29 times. Fixed to keep the kind word |
| B3 | GATE | **The fix for B2 silently zeroed every retrieval metric — 0 of 617** | `ranked_sections()` returns canonical strings and `same_section()` normalises them *again*, so the function is called on its own output. It was never idempotent; the old fallback was a no-op there only by accident. `BNS:190` became `BNS::190`. **Nothing crashed and every number looked plausible.** Fixed and pinned by `test_idempotent_on_its_own_output` |
| B4 | Wave 2, S4 | Composite reconstruction failed on **617 of 617 rows** | Not a code defect — this is how the documentation error A2 was discovered |
| B5 | Wave 2, S5 | `CHECK 2` — **deliberately left FAILING** | 8 AUROC intervals narrowed under clustering. 4 are explained by measured *negative* within-situation correlation (contrastive variants are built to disagree). **4 remain unresolved** on restricted `cited`/`grounded` subsets, ratios 1.043–1.121. Resampler bugs and Monte Carlo noise ruled out across 5 seeds. **Those two restricted subsets are marked unusable**; `restriction=none` is unaffected |
| B6 | Wave 3, S1 | `check06` failed twice before passing | Both faults in the check itself: a dedupe ordering differing from `load_logs()`, and a notes parser letting layman values masquerade as pooled ones |
| B7 | Wave 3, S1 | One reconstruction mismatch remains | A single stale pre-`ENTITY_NEUTRAL` log row, `req_id=40bd347de051`, named in the CSV |
| B8 | Wave 1, S2 | Determinism asserted but not demonstrated | A verification command timed out. Later demonstrated by the main agent: two full runs, byte-identical output |
| B9 | Wave 1, S2 | Rule breach | The agent issued a command containing `git status`, against the no-git rule. It timed out, `git status` is read-only, and no repository state was altered |
| B10 | Wave 2, S2 | Paired check disagreed by **one chunk in 608** | Traced, not smoothed: query `L0089`, replay and original differ in the **fifth decimal** of a cosine score (0.259167 vs 0.259176), flipping third place in the ≥3-forced-through rule between a CPA chunk at 0.2489 and a CrPC chunk at 0.2491 |

### Assertions that passed and are worth recording

- Wave 3 S2: a **second BM25 implementation** written from the Okapi formula in plain Python reproduced **32/33 and 0/33 exactly**; a **second tokeniser** built by character scan agreed on 52 real chunks; the dense arm reproduced `ablate_filter.py` **query-for-query**. 17 checks, all passing.
- Wave 2 S1: both gate anchors re-derived by a route that **does not import `metrics_lib` at all** — own parser, own Wilson arithmetic. 2,306 comparisons agree.
- Wave 3 S1: `exp04` AUROCs reproduced to **0.00e+00**, pooled and per set.
- Calibration: an accidental concurrent double-run produced **byte-identical values across all 24 bootstrap intervals** — 240,000 resamples.

---

## C. Everything that could NOT be computed, and why

| # | What | Why |
|---|---|---|
| C1 | Significance test that the CrPC over-representation ratio *differs* between `raw_15` and `filtered_n` | The correct instrument is a paired bootstrap on a **share** difference; `metrics_lib` exposes only the AUROC version. The agent stopped rather than reimplement a metric. Both intervals are reported; **no difference claim is made** |
| C2 | Confidence intervals on AURC, coverage-at-risk, and Platt pre/post | Requires a nested bootstrap, roughly 10× runtime |
| C3 | Calibration at `reranked_15` and `filtered_n`; per-query-set calibration intervals | Not run |
| C4 | Layman results under `exclude_entity_default_used` | All 120 layman rows use the neutral default, so the restriction **empties the set** |
| C5 | A second source for S2's `raw_15` paired check | The original run logs stored **only post-filter survivors**. Stated as NOT CHECKABLE |
| C6 | Per-query-set AUROC for `statute_consistency` under `grounded` | Only 27 positives across all 617 rows |
| C7 | 3 labelled rows | `load_logs()` deduplicates on `(query_id, intervention)` keeping the last occurrence; in 3 cases the last row has no gold while an earlier one did. `G0107`, `G0190`, `D0094`. **n is 617 where it could be 620** — 0.5%, verified to move no conclusion. Disclosed rather than fixed, because changing the loader would shift every number in eight CSVs and invalidate twelve explanation blocks that quote n=617 |
| C8 | The original 97.0 / 51.5 figures could not be *recomputed* from logs | `ablate_filter.py` printed to standard output only; its output was never saved. They had to be regenerated against the live index. Now captured at `results/ablation_rerun_2026-09-01.txt` |
| C9 | Cross-statute accuracy at all three stages from `stages.jsonl` | `stages.jsonl` replays the **recorded corpus filter**, so every row is already restricted to one statute. A cross-statute figure from it would be near 100% and meaningless |
| C10 | BNS-era procedure | The BNSS is **not in the index**. 5 of 120 layman queries require it and are unanswerable by construction |
| C11 | 56 of 120 layman queries have no single correct answer | They state no date, so either code may be admissible. Counting them as errors would manufacture a result |
| C12 | Legal-expert validation | Not obtained. Every credible paper in this field has it; almost no Indian system paper does. **The cheapest remaining differentiator** |
| C13 | Whether reranking genuinely improves rank | Pooled MRR moves 0.418 → 0.467, but cluster intervals overlap. **Flagged, not claimed** — needs a paired test |

---

## D. Caveats that must travel with any quoted figure

| # | Caveat |
|---|---|
| D1 | **`ranked_sections()` compresses rank.** It drops chunks with no `section_number`, so a gold chunk at retrieved position 5 reports at rank 3. Only 118 of 617 `raw_15` lists carry a section number on all 15 chunks. Identical at k=15 — which is why every anchor held — but layman Recall@5 is **0.100 compressed vs 0.050 positional**, a factor of two. Both conventions are in the CSVs under distinct metric names |
| D2 | **`cited` has three legitimate values on the same 617 rows.** **533** from the logged pre-fix parser · **538** re-parsed with the post-fix parser · **587** under lenient matching. Three routes, three correct answers to three different questions. Any figure must name its route |
| D3 | **Gold is not always one section.** 525 queries have one, 88 have two, 4 have three. `paired_recodification` Recall@15 is **0.737 binary** (found at least one) vs **0.616 fraction-of-gold** (found all). Finding one side of an IPC↔BNS pair is not finding both |
| D4 | **The paired 2×2 routing matrix returns 100%/100% and is not a result.** The corpus filter fired IPC on all 33 IPC-named and BNS on all 33 BNS-named queries, so the diagonal was guaranteed before an embedding was compared. Usable only as the contrast to the filter-off condition |
| D5 | **Dominant-corpus is a coarse instrument.** BM25 scores 0.0% on IPC-named queries by that measure, yet puts the correct section at **rank 1** on P0001 — ranks 6–15 flood with CrPC cross-references. Quote it alongside top-1, where BM25 reaches 45.5% |
| D6 | **`statute_consistency` is partly tautological.** On 343 of 617 rows the corpus filter was derived from the same query-plus-date inputs the signal reads, so it cannot fail by construction. It earns its keep only where the filter follows the *named* code while the *date* disagrees |
| D7 | **The normaliser artefact rate is 64% [54.2, 72.7] before filtering and 1 in 64 after.** The contents and footnote filters catch 63 of 64. Quoting 64% alone badly overstates the harm |
| D8 | **The recodification gap is a RETRIEVAL claim.** It holds under `retrieved@15` (+0.545 clustered) and **dies** under `cited` (−0.030 [−0.121, 0.061]) and `grounded`. The IPC arm cites gold 90.9% of the time, the BNS arm 93.9% — the generator cites correct sections regardless of what was retrieved. **The failure is real and the answer text conceals it** |
