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

---

## Tier logging bug

Output file: agents/answer.py, tests/test_tier_bug.py
Regenerate with:

```bash
# 1. the measurement (READ-ONLY over runs/)
./venv/Scripts/python.exe -c "
import json,glob,collections,sys; sys.path.insert(0,'.')
from experiments.metrics_lib import wilson
HIGH,MED=0.55,0.38
def tier(d):
    a=d.get('answer') or {}
    if a.get('refused') or (d.get('confidence') or {}).get('refused'): return 'REFUSED'
    c=(d.get('confidence') or {}).get('composite')
    return None if c is None else ('LOW' if c<MED else ('MEDIUM' if c<HIGH else 'HIGH'))
n=wrong=0; true_c=collections.Counter(); log_c=collections.Counter()
for f in sorted(glob.glob('runs/*/queries.jsonl')):
    for line in open(f,encoding='utf-8'):
        if not line.strip(): continue
        d=json.loads(line); n+=1
        t=tier(d); l=(d.get('answer') or {}).get('prompt_variant')
        true_c[t]+=1; log_c[l]+=1
        if t!=l: wrong+=1
print('n=',n,'logged=',dict(log_c),'true=',dict(true_c))
print('mislabelled %d/%d  p=%.4f  95%% Wilson [%.4f, %.4f]'%((wrong,n)+wilson(wrong,n)))
"

# 2. the tests
./venv/Scripts/python.exe -m pytest tests/test_tier_bug.py -q
./venv/Scripts/python.exe -m pytest tests/ -q
```

Owner: Wave 1 Subagent 1

---

### 1. ELI5 — what does this measure?

Imagine a pharmacist who reads every prescription correctly and hands over the
right medicine every single time — but whose logbook has "Aspirin" pre-printed
on every line, and she never crosses it out. The patients were fine. The
logbook is fiction.

That is exactly what `agents/answer.py` was doing. When retrieval confidence
was low, the code *did* add the strong "I am not sure, please see a lawyer"
warning to the prompt — the system behaved correctly. But the field it wrote
into the run log, `prompt_variant`, was set to `"HIGH"` on line 103 and never
changed afterwards. **Measured on the real logs: 369 of 859 records (43.0%)
recorded a confidence tier that contradicts their own confidence score.**

What changes now: nothing the user sees, and no answer text changes. Only the
log field changes — it is now computed from the confidence value itself at the
moment of writing, so it always states the tier that was actually applied. The
`"REFUSED"` path is untouched.

---

### 2. Technically

**Terms, defined on first use.**

- **Confidence (composite)** — a single number in [0, 1] that the retrieval
  stage produces to say "how well do the documents I found match this
  question." It is a weighted blend of three signals (55% top-k mean score,
  15% score gap, 30% entity coverage). Those weights, and the thresholds
  below, were fixed in February 2026 before any score was ever logged.
- **Tier** — which of three bands the confidence falls into:
  `LOW < 0.38 <= MEDIUM < 0.55 <= HIGH`.
- **Prompt variant / disclaimer** — the tier decides how much hedging text is
  prepended to the system prompt sent to the language model. LOW gets a strong
  "do not cite sections, see a lawyer" block; MEDIUM gets a softer one; HIGH
  gets none.
- **`prompt_variant`** — the field in `runs/<stamp>_<sha>/queries.jsonl` that
  is supposed to record which of those three was used.

**The defect.** The code read:

```python
system_prompt = ANSWER_SYSTEM_PROMPT
prompt_variant = "HIGH"                              # <- initialised
if retrieval.confidence < MEDIUM_CONFIDENCE:
    system_prompt = LOW_CONFIDENCE_DISCLAIMER + ...  # <- prompt updated
elif retrieval.confidence < HIGH_CONFIDENCE:
    system_prompt = MEDIUM_CONFIDENCE_DISCLAIMER + ...
else:
    ...
...
return {..., "prompt_variant": prompt_variant, ...}  # <- always "HIGH"
```

Each branch reassigned `system_prompt` but none reassigned `prompt_variant`.
This is the classic "two variables that must agree, kept in sync by hand"
failure: it is correct on the day it is written and wrong the moment anyone
adds a branch.

**The fix.** The branch is left byte-for-byte identical — no behaviour changes.
A pure function is added that mirrors the same comparisons, and the log field
is derived from the confidence value at the point of writing:

```python
def tier_for_confidence(confidence: float) -> str:
    if confidence < MEDIUM_CONFIDENCE:
        return "LOW"
    if confidence < HIGH_CONFIDENCE:
        return "MEDIUM"
    return "HIGH"
```

```python
"prompt_variant": tier_for_confidence(retrieval.confidence),
```

There is now no variable to forget to update. The refusal gate above still
returns `"REFUSED"` before this code is reached, unchanged.

**Why recomputing from the log is legitimate.** `app.py:229` writes
`composite=retrieval.confidence` — the logged `confidence.composite` is
*literally the same float* the `if` statement tested. Recomputing the tier
from it therefore reproduces the branch that actually ran; it is not an
estimate.

---

### 3. What the number came out as

Over all 8 run directories, every `queries.jsonl` row, n = 859:

| | logged | true (recomputed) |
|---|---|---|
| HIGH | 859 | 490 |
| MEDIUM | 0 | 354 |
| LOW | 0 | 15 |
| REFUSED | 0 | 0 |

**Mislabelled: 369 / 859 = 42.96%, 95% Wilson interval [39.69%, 46.29%].**

The 369/859 figure in the plan is **exactly right** — confirmed, not assumed.

Supporting proportions, same n = 859, same interval method:

| true tier | k/n | p | 95% Wilson |
|---|---|---|---|
| HIGH | 490/859 | 0.5704 | [0.5371, 0.6031] |
| MEDIUM | 354/859 | 0.4121 | [0.3797, 0.4453] |
| LOW | 15/859 | 0.0175 | [0.0106, 0.0286] |

A **Wilson interval** is the honest error bar on a proportion. The naive
interval (`p ± 1.96·sqrt(p(1-p)/n)`) collapses to ±0.00 at 0/n or n/n,
claiming perfect certainty from finite data; Wilson does not. Imported from
`experiments/metrics_lib.py` so it matches every other interval in the paper.

Note the mislabel count is not an estimate of a population parameter — it is a
complete census of these 859 rows, so the "369" is exact. The interval answers
a different and still useful question: *if this system kept running under the
same conditions, what fraction of future records would be mislabelled?*

---

### 4. How to read it

- **43% is a property of the old log files, not of the fixed code.** After the
  fix the mislabel rate on newly generated records is 0 by construction, and
  `tests/test_tier_bug.py` pins it there.
- **The 859 historical rows are still wrong on disk and stay that way.**
  `runs/` is read-only — that data cost money and must not be rewritten. Any
  analysis that needs the tier must recompute it from `confidence.composite`
  using the snippet above, never read `answer.prompt_variant`.
- **43% is not a system error rate.** No answer was ever given under the wrong
  disclaimer. It is purely an instrumentation error rate.
- **The tier split is itself informative:** only 57% of queries reached HIGH,
  and 41% sat in MEDIUM. That distribution was previously invisible because
  the log flattened all of it to "HIGH".

---

### 5. What this means for the paper

**Be precise about the size of this: `prompt_variant` was never used in a
headline number.** A repo-wide grep shows the field is written by `app.py:241`
and read by *nothing* in `experiments/` or `scripts/`. Every published figure
so far — retrieval@k, ungrounded citation rate, the layman corpus-dominance
numbers — derives from `retrieval.*` and `verifier.*` fields, not from this
one. **No existing result needs to be retracted or restated.**

What it actually cost:

1. **A planned analysis was blocked, not corrupted.**
   `docs/AUDIT_2026-08-26.md:201` records "PHASE_G.md — tier analysis
   unavailable, `prompt_variant` always logs HIGH." Any claim of the form
   "answers generated under the LOW-confidence disclaimer are less likely to
   cite ungrounded sections" was unmeasurable. It is now measurable — and
   measurable *retrospectively* on the existing 859 rows, by recomputing the
   tier, with no re-querying and no further API spend.
2. **It is a good methods-section example, honestly framed.** The right
   sentence is something like: *"An instrumentation defect caused the applied
   prompt tier to be logged as HIGH on all records; the disclaimer selection
   itself was correct, so no generated answer was affected. The field was
   corrected and, because the logged composite confidence is the exact value
   the selection tested, the true tier is recoverable for all 859 historical
   records."* That is a stronger paragraph than silence, and it is defensible
   in a viva.
3. **It does not touch the frozen constants.** The 55/15/30 weights and the
   0.55/0.38 thresholds are unchanged. Those were fixed before any score was
   logged, which is the methodological point; nothing here weakens it.

Do not inflate this into a headline. It is a logging fix that unblocks one
analysis.

---

### 6. What broke while computing this

Three things, all small, all recorded:

1. **`json.loads` on a truncated line.** My first attempt to inspect a record
   piped `head -c 3000` into Python and got
   `JSONDecodeError: Unterminated string starting at column 2981`. The file
   was fine; I had cut a record in half. Fixed by reading one whole line with
   `f.readline()` instead of byte-slicing. Worth recording because for 10
   seconds it looked like corrupted evaluation data.
2. **Full-suite collection error, pre-existing and not mine.**
   `./venv/Scripts/python.exe -m pytest -q` aborts during collection:
   `test_ingest.py:4: FileNotFoundError: C:\Users\uniya\Downloads\the_code_of_criminal_procedure,_1973.pdf`.
   That is a stray script at the repo *root* (not in `tests/`) which opens
   three PDFs from Downloads at import time — a manual ingest script pytest
   collects because of its filename. It fails identically with or without my
   change, and I did not touch it (not in my file list). The suite must be run
   as `pytest tests/ -q`. Flagging it for the main agent: it is debris that
   makes bare `pytest` unusable.
3. **A near-miss on a rounding artefact.** At confidence 0.5499 the trace
   prints `[Answer] MEDIUM confidence (0.550)` because the print uses `:.3f`.
   The value tested is still 0.5499 and the branch is correct; the display
   rounds. Not a bug, but it briefly looked like one.

---

### 7. What I could not compute, and why

Nothing. Every required number was computed from the real logs on disk with no
API calls, no writes to `runs/`, and no regeneration of anything.

One thing I deliberately did **not** do: rewrite the 369 wrong values in the
historical `queries.jsonl` files. `runs/` is read-only, and patching data
instead of code is the failure mode this project already suffered once (the
corpus-tagging defect hidden for six months by `fix_corpus_tags.py`). The
correct tier is recoverable on demand from `confidence.composite`.

---

### 8. What surprised me

**Three things.**

*The estimate was exactly right.* I was told 369 of 859 and told not to trust
it. Independently recomputed, it is 369 of 859 — not 371, not 366. That almost
never happens with a number carried between documents by hand, and it means
whoever wrote the plan had actually run the count.

*Zero refusals in 859 records.* The `REFUSED` path — the safety valve that is
supposed to fire when retrieval finds nothing usable — has **never fired
once** in the entire logged history. The lowest tier observed is LOW at 15
rows (1.75%). I was asked to keep the refusal path intact and I did, but it is
worth flagging to the main agent that a safeguard which has never triggered in
859 queries is either perfectly calibrated or effectively dead code. Given
that `entity_coverage` used to hand out 0.30 for free (`GAPS.md` #2), "dead"
is the likelier explanation, and the refusal gate may deserve its own check.

*The bug was invisible in exactly the wrong way.* It failed silently and in
the reassuring direction. A log that said `"LOW"` on a high-confidence answer
would have been noticed within a day — it looks alarming. A log that says
`"HIGH"` on everything looks like a system that is working well. Nearly half
the records were wrong and the wrongness read as good news, which is why it
survived from February to August. That is the general lesson I would keep:
**check your instrumentation hardest when it is telling you what you hoped to
hear.**

---

## Adaptive filter analysis

Output file: `results/filter_analysis.csv`
Regenerate with: `./venv/Scripts/python.exe experiments/exp08_filter.py`
Owner: Wave 1 Subagent 2

---

### 1. ELI5 — what does this measure?

When you ask the system a question, it does three things in a row.

1. It fetches the **15 passages** from the law books whose meaning is closest to your question. Call this pile **`raw_15`**.
2. It shuffles those same 15 so that passages containing a section number you literally mentioned move to the front. Same 15 passages, new order. Call this **`reranked_15`**.
3. It **throws some of them away** and shows only the survivors to the language model that writes your answer. Call the survivors **`filtered_n`** — `n`, not 15, because how many survive changes from question to question.

Step 3 is the **adaptive filter**, and it is the thing this analysis is about.

The rule it uses is:

> Keep a passage if its score is at least `max(top_score − 0.15, 0.35)`.
> But never keep fewer than 3.

A **score** here is a similarity number between 0 and 1 — how close in meaning a passage is to the question. In this project real scores sit around 0.35–0.55, not 0.8+.

So the filter takes the best score it found (`top_score`), steps 0.15 down from it, and keeps everything above that line — *unless* that line falls below 0.35, in which case it uses 0.35 instead. Two candidate lines; whichever is **higher** wins.

The worry is simple: **what if the right answer was in the pile of 15, and step 3 threw it out?** Then retrieval did its job and the filter undid it. This analysis counts exactly how often that happened, works out which of the two lines did the throwing, and then asks a "what if" question: what would have survived if the 0.35 line had been lower.

**Two words you need before reading anything below.**

**Recall.** The fraction of questions where the correct section was present in a given pile. If the gold (correct) section appears somewhere in the 15 passages for 18 of 120 questions, recall at `raw_15` is 18/120 = 0.150, or 15.0%. Recall says nothing about *where* in the pile it sat or whether the model used it — only that it was there. It is a ceiling, not a promise.

**Percentage point vs percent.** These are different and mixing them is how papers get embarrassed. Recall falling from 15.0% to 7.5% is a drop of **7.5 percentage points** (subtract) and a drop of **50 percent** (divide: 7.5 is half of 15.0). Both descriptions are true. This file always says which one it means. In the CSV the column `recall_lost_pp` is in **points**.

**Confidence interval.** We measured 120 layman questions, not all possible layman questions. If we had drawn a different 120, the number would have come out a bit different. A 95% confidence interval is the range of true values that are compatible with what we saw — it is a statement about how much the number could move if we had been unluckier. `[0.040 – 0.136]` around 0.075 means: the data are consistent with the true rate being anywhere from 4% to 14%. Narrow interval = lots of evidence. Wide interval = few observations, be careful.

**Counterfactual.** Latin-ish for "contrary to fact" — a measurement of something that did *not* happen. We did not lower the filter and re-run the system. We took the 15 passages already saved on disk for each question, along with their already-recorded scores, and re-applied the keep/discard rule with a different number in it. Nothing was re-retrieved, nothing was re-asked, no money was spent, and **the deployed system was not changed**. It is arithmetic on stored data.

---

### 2. Technically

**Data.** `experiments/stages.jsonl`, 621 rows, one per `req_id`, written by Wave 0's `experiments/rerun_stages.py` (retrieval-only replay). Each row stores all three stages, and every chunk carries an authoritative `section_number` read from the Qdrant payload rather than parsed from text. Joined to gold labels via `metrics_lib.load_logs()`, which deduplicates on `(query_id, intervention)` keeping the last occurrence — 859 raw rows collapse to 621, and the join to stages is 621/621 with zero misses.

**Analysed:** 617 rows. Excluded: 4 SMOKE rows with no gold label, and 3 rows in the legacy `criminal_paired` / `criminal_unnumbered` sets (n = 2 and n = 1, too small to report). The exclusion is recorded in the CSV as `rows_analysed`.

**Correctness definition, used everywhere below:** `retrieved@k` — the gold section (from `expected_sections`) matches, under `metrics_lib.same_section()` in **strict** mode, at least one chunk's `"<corpus> <section_number>"` in the stage being scored. All section identity goes through `normalise_section()`; nothing is string-compared by hand. `k` is the size of the stage: 15 for `raw_15` and `reranked_15`, variable `n` for `filtered_n`.

**The filter, reconstructed** (`apply_filter` in `experiments/exp08_filter.py`) — arithmetic identical to `agents/retriever.py`, with the single constant `0.35` made a parameter:

```
top = max(score for chunk in reranked_15)
thr = max(top - 0.15, floor)          # floor=None  ->  thr = top - 0.15
kept = [c for c in reranked_15 if c.score >= thr]
if len(kept) < 3 and len(reranked_15) >= 3:
    kept = reranked_15[:3]            # the >=3 forced-through rule
```

The relative arm (`−0.15`) and the `>=3` rule are held **fixed** across the entire sweep. Only `floor` varies: 0.35 (deployed), 0.30, 0.25, 0.20, and None.

**Binding arm.** The threshold is a maximum of two quantities, so exactly one of them is the one actually in force. The **absolute floor binds** iff `0.35 > top_score − 0.15`, i.e. iff `top_score < 0.50`. Otherwise the **relative arm binds**. This is a property of the query (its `top_score`), not of the individual chunk.

**A cut** is a query where the gold section is present in `raw_15` but absent from `filtered_n` under the deployed filter. For each cut we record the *best-ranked* gold-bearing chunk in `raw_15` — its score, its 1-based rank in `raw_15` and in `reranked_15` — plus the query's `top_score` and the threshold value that cut it.

**Intervals.** Proportions get a **Wilson** 95% interval (`metrics_lib.wilson`) in `ci_lo`/`ci_hi`. Wilson rather than the textbook normal interval because at 0/9 or 9/9 the normal interval reports ±0.00, claiming certainty from nine observations. Recall rows additionally get a **cluster bootstrap** (`metrics_lib.cluster_bootstrap`, `SEED = 20260901`, `N_BOOT = 10000`) resampling `pair_id` rather than rows, in `cluster_ci_lo`/`cluster_ci_hi` — three or four phrasings of one situation are not independent observations, and a row-level interval would be narrower than the data supports. `counterfactual_mean_chunks` is a mean, not a proportion, so Wilson does not apply: `ci_lo`/`ci_hi` are left **empty** and only the cluster bootstrap is reported. Per-cut descriptive statistics (mean/median/min/max of scores and ranks) carry no interval; they are descriptions of a set of 3–9 cases, not estimates.

**Nothing here reimplements a metric.** `recall_at_k`, `same_section`, `ranked_sections`, `wilson`, `cluster_bootstrap`, `SEED`, `N_BOOT` all come from `experiments/metrics_lib.py`.

**Paired check.** See §6 — it passed.

---

### 3. What the number came out as

Every number below is `retrieved@k`, strict `same_section`, with its stage named.

#### 3a. Where recall stands at each stage, deployed configuration

| Query set | n | `raw_15` recall [95% Wilson] | `filtered_n` recall [95% Wilson] | Lost |
|---|---|---|---|---|
| `generated_retrieval` | 198 | 0.692 [0.624 – 0.752] | 0.677 [0.609 – 0.738] | **1.5 pp** |
| `paired_recodification` | 99 | 0.737 [0.643 – 0.814] | 0.707 [0.611 – 0.788] | **3.0 pp** |
| `paired_dated_conflict` | 197 | 0.492 [0.423 – 0.562] | 0.452 [0.384 – 0.522] | **4.1 pp** |
| `layman_situation` | 120 | 0.150 [0.097 – 0.225] | 0.075 [0.040 – 0.136] | **7.5 pp** (= 50% relative) |

`reranked_15` recall equals `raw_15` recall in every set, as it must — reranking reorders the same 15 and cannot add or remove a section.

This reproduces Wave 0's figures on the nose, including the 15.0% → 7.5% layman result that the "counting bug" scare was about. It was never a bug. It is one measurement at two stages.

#### 3b. (a) What the filter cut — `raw_15 → filtered_n`, deployed floor

| Query set | queries with gold in `raw_15` | cuts | cut rate [95% Wilson] |
|---|---|---|---|
| `generated_retrieval` | 137 | 3 | 0.022 [0.007 – 0.062] |
| `paired_recodification` | 73 | 3 | 0.041 [0.014 – 0.114] |
| `paired_dated_conflict` | 97 | 8 | 0.082 [0.042 – 0.155] |
| `layman_situation` | 18 | **9** | **0.500 [0.290 – 0.710]** |

Half of every layman question that retrieval got right, the filter then threw away.

The cut chunks themselves, at the deployed floor:

| Query set | gold score mean (min–max) | gold rank in `raw_15` mean / median | `top_score` mean | threshold mean |
|---|---|---|---|---|
| `generated_retrieval` | 0.397 (0.388 – 0.407) | 11.67 / 10 | 0.566 | 0.416 |
| `paired_recodification` | 0.634 (0.617 – 0.664) | 8.67 / 9 | 0.816 | 0.666 |
| `paired_dated_conflict` | 0.594 (0.565 – 0.643) | 9.25 / 9 | 0.773 | 0.623 |
| `layman_situation` | **0.288 (0.234 – 0.347)** | 9.89 / 12 | **0.335** | **0.350** (all nine) |

Read the last row against the three above it. In the three non-layman sets the cut gold chunk scored **0.39 to 0.66** and the threshold that killed it was **0.42 to 0.67** — a moving line, set by a strong `top_score`. In the layman set every single cut faced the **same** threshold, 0.350, because the floor was in force on all nine, and the gold chunk scored **below 0.35** every time.

#### 3c. (b) Which arm was binding — denominator is the cuts

| Query set | cuts | floor binding [95% Wilson] | relative binding [95% Wilson] |
|---|---|---|---|
| `generated_retrieval` | 3 | 0 — 0.000 [0.000 – 0.561] | 3 — 1.000 [0.439 – 1.000] |
| `paired_recodification` | 3 | 0 — 0.000 [0.000 – 0.561] | 3 — 1.000 [0.439 – 1.000] |
| `paired_dated_conflict` | 8 | 0 — 0.000 [0.000 – 0.324] | 8 — 1.000 [0.676 – 1.000] |
| `layman_situation` | 9 | **9 — 1.000 [0.701 – 1.000]** | 0 — 0.000 [0.000 – 0.299] |

**The hypothesis was tested and the data confirmed it, in its strongest possible form: a clean 100/0 split in both directions.** Every layman cut was made by the absolute 0.35 floor. Not one non-layman cut was. The mechanism is exactly the one predicted: layman `top_score` averages 0.335, so the relative arm sits at 0.335 − 0.15 ≈ 0.185, which is far below 0.35, so the floor wins and cuts at 0.35 — a line the layman gold chunks (mean 0.288) cannot clear.

The intervals are wide because 9 and 3 are small numbers of cuts. `[0.701 – 1.000]` is the honest statement about 9/9; it is not the same claim as 900/900. The *separation between sets* is nevertheless clean — the layman interval `[0.701 – 1.000]` does not overlap any other set's floor-binding interval.

#### 3d. (c) Counterfactual sweep — recall [95% Wilson] / mean chunks reaching the LLM

Relative arm and `>=3` rule held fixed; only the floor varies. The deployed system was not modified.

| Query set | n | 0.35 (deployed) | 0.30 | 0.25 | 0.20 | none | `raw_15` ceiling |
|---|---|---|---|---|---|---|---|
| `generated_retrieval` | 198 | 0.677 [0.609–0.738] / 11.2 | 0.677 / 11.2 | 0.677 / 11.2 | 0.677 / 11.2 | 0.677 / 11.2 | 0.692 |
| `paired_recodification` | 99 | 0.707 [0.611–0.788] / 10.3 | 0.707 / 10.3 | 0.707 / 10.3 | 0.707 / 10.3 | 0.707 / 10.3 | 0.737 |
| `paired_dated_conflict` | 197 | 0.452 [0.384–0.522] / 10.1 | 0.452 / 10.1 | 0.452 / 10.1 | 0.452 / 10.1 | 0.452 / 10.1 | 0.492 |
| `layman_situation` | 120 | **0.075** [0.040–0.136] / **5.1** | **0.117** [0.071–0.186] / 9.0 | **0.117** [0.071–0.186] / 13.4 | **0.150** [0.097–0.225] / 15.0 | **0.150** [0.097–0.225] / 15.0 | 0.150 |

Cluster (`pair_id`) intervals for the layman recall row, which are the ones to quote: 0.35 → [0.000 – 0.167]; 0.30 → [0.025 – 0.233]; 0.25 → [0.025 – 0.233]; 0.20 and none → [0.033 – 0.275]. They are wider than Wilson because 120 layman rows are only 30 independent situations.

Cluster intervals on the layman chunk-count: 0.35 → [3.69 – 6.69]; 0.30 → [7.08 – 10.98]; 0.25 → [12.10 – 14.47]; 0.20 and none → [15.00 – 15.00].

Three things in that table are worth saying out loud.

1. **The floor is a no-op on three of the four query sets.** Removing it entirely changes nothing — not recall, not even the chunk count to one decimal. Those sets have high `top_score`s (0.57–0.82), so the relative arm binds and the floor is never consulted. Their remaining `raw_15 → filtered_n` gap (1.5 / 3.0 / 4.1 pp) is caused by the relative arm, which this sweep deliberately does not touch.
2. **On layman queries the floor is the entire loss.** At floor = 0.20 or no floor, layman `filtered_n` recall returns to **0.150** — precisely the `raw_15` ceiling. Zero cuts remain. Everything the layman pipeline loses between Stage A and Stage C is lost to the 0.35 constant.
3. **The recall is bought with text.** Layman goes from **5.1** chunks reaching the model to **15.0**, a 2.96× increase in retrieved context, to gain 7.5 percentage points of recall. That is the cost side and it must be reported next to the recall or the result is half a result. And 15.0 is the cap: the pool is 15, so "no floor" on layman queries means *send everything Qdrant returned* — the filter stops filtering at all.

#### 3e. Worked example — one real layman query, `L0009`

Gold section: `IPC 498A` / `BNS 85` (cruelty by husband or relatives).

```
top_score            0.380674     the best of the 15 chunks
relative arm         0.380674 - 0.15 = 0.230674
absolute floor       0.35
threshold  = max(0.230674, 0.35) = 0.350000     <- the FLOOR wins; it binds
gold chunk           rank 6 of 15,  score 0.346579
0.346579 >= 0.350000 ?   NO      -> cut, by 0.0034
chunks that survived  5   (rank 6 was not inside the forced-through top 3)
```

The gold passage was the sixth-best of fifteen and it missed the cut by **three thousandths of a point**. Under no floor the threshold would have been 0.2307 and it would have survived comfortably, along with all 15 chunks.

Now the other end of the same set, `L0085` — gold `CPA 2`, consumer law:

```
top_score            0.295152     the WHOLE pile is weak
relative arm         0.145152
threshold  = max(0.145152, 0.35) = 0.350000
gold chunk           rank 12 of 15,  score 0.241432
```

Here the floor is above the *top* score. Nothing at all clears 0.35, so the `>=3` rule fires and exactly the top 3 chunks are forwarded — the filter has degenerated into "always send 3". Four of the nine layman cuts (`L0045`, `L0047`, `L0048`, `L0085`–`L0088`, seven in total) survived on the `>=3` rule alone with `nchunks = 3`. Removing the floor there does not so much loosen the filter as switch it back on.

---

### 4. How to read it

- **Never quote a recall number without its stage.** "Layman recall is 7.5%" and "layman recall is 15.0%" are both true; they are `filtered_n` and `raw_15` of the same measurement. This is the confusion Wave 0 chased as a bug. Write `filtered_n` next to the number, every time.
- **The counterfactual columns are not a recommendation.** They say what the stored chunks would have done under a different constant. They do not say the answer would have improved, because a longer context can dilute the model as easily as help it. Nothing downstream of retrieval was re-run.
- **Read every recall next to its chunk count.** Floor 0.20 on layman queries reads as "+7.5 points of recall" and equally as "send three times the text and abolish the filter." Both are the same row.
- **Prefer the cluster interval to the Wilson interval when quoting layman numbers.** 120 rows are 30 situations. The Wilson interval `[0.040 – 0.136]` treats the 120 as independent; the cluster interval `[0.000 – 0.167]` does not, and is the defensible one.
- **The wide binding-arm intervals are not a weakness in the finding, they are its size.** 9/9 with `[0.701 – 1.000]` is a strong statement about direction and a weak one about the exact rate. The clean part of the result is the *separation*: 100% floor-binding on layman, 0% on all 308 non-layman... 0 of 14 non-layman cuts, precisely.
- **`recall_lost_pp` is in percentage points.** The layman 7.5 there is a subtraction, not a ratio. The 50% relative figure is 7.5 / 15.0 and appears nowhere in the CSV.
- **Empty cells are meaningful.** `ci_lo`/`ci_hi` are empty on `counterfactual_mean_chunks` because Wilson is a proportion interval; `cluster_ci_*` are empty on binding-arm and per-cut rows. An empty column is never a zero.

---

### 5. What this means for the paper

This is a finding about **her own system's default configuration**, and it cuts both ways, so state both. The strengthening reading is real and it is the stronger one: the deployed adaptive filter **halves gold-section recall on exactly the queries a member of the public would actually ask** (15.0% → 7.5% at `filtered_n`, a 50% relative loss), and the mechanism is now identified rather than guessed — the absolute 0.35 floor, binding on 9 of 9 layman cuts and 0 of 14 cuts everywhere else, because layman `top_score` averages 0.335 so the relative arm never gets a vote. That is a *mechanism*, with a counterfactual attached (removing the floor recovers the loss exactly, at 2.96× the context), and mechanisms are what reviewers reward over yet another ablation table. It is also a transferable warning: any RAG system with a hard similarity floor tuned on well-specified queries will silently degrade on vernacular ones, because vernacular queries depress the whole score distribution rather than just the gold chunk's rank. The honest tension is that a hostile reviewer will say: *"This is a hyperparameter you chose badly. Your headline cross-statute result is not a finding about legal RAG, it is an artefact of a poorly tuned threshold — retune it and the paper evaporates."* Three things answer that, and the paper must say all three. First, the 0.35 was **frozen before any score was logged** and has never been touched since; nothing was tuned against the evaluation set, and the counterfactual sweep was computed on stored chunks without modifying the deployed system — that provenance is the methodological defence and it should be stated in the experimental-setup section, not buried. Second, and this is the part that actually blunts the attack: **the floor is not where the layman failure lives.** `raw_15` layman recall is **15.0%**. Even with the filter abolished entirely, 85% of layman questions never had the right section in the retrieved pile at all. The filter halves a number that was already catastrophic. Retuning the floor cannot rescue the layman result; it moves it from very bad to bad. Third, the floor is provably irrelevant to the other three query sets — removing it changes their recall by exactly zero — so the cross-statute results cannot be a threshold artefact. Recommended framing: report the filter loss as a **secondary, mechanistic finding with a named cause**, keep the primary claim anchored at `raw_15` where no filter is involved, and let the sweep serve as the evidence that the primary claim is threshold-independent. Do not reframe the paper around the filter; it is the smaller of the two problems and saying otherwise invites the reviewer to notice that for us.

---

### 6. What broke while computing this

**One thing, and it was mine, not the data's.** The first attempt to write `experiments/exp08_filter.py` through a shell heredoc failed with `unexpected EOF while looking for matching quote` — the script body contains quote characters the shell tried to interpret. Second attempt used a direct file write and succeeded. No third attempt, no workaround, nothing changed about the analysis.

**Nothing broke in the data, and that is itself worth recording.** All of these were checked and all passed first time:

- `stages.jsonl` → logs join: **621 of 621** `req_id`s matched, zero orphans in either direction.
- Deduplication: `load_logs()` collapsed 859 rows to 621 exactly as documented. No manual dedupe was performed anywhere.
- **The paired check passed exactly.** Layman `filtered_n` recall was computed twice by independent routes: (1) from the filter reconstructed inside `exp08_filter.apply_filter()`, and (2) from the Stage C chunk list that Wave 0's `rerun_stages.py` wrote to disk — a separate implementation, written by someone else, run at a different time against the live Qdrant collection. Both give **0.075000** on layman, and they agree to better than 1e-12 on every query set individually and on all 617 rows pooled (`0.4927`). A second, stricter version of the same check compares the *length* of the reconstructed keep-list against the stored one row by row: **0 mismatches in 621 rows**. Both are `assert` statements in `check_paired()`, so the script cannot produce a CSV if they ever stop holding. If it had disagreed it would have meant one of the two filters is not the deployed filter, which would have invalidated the entire sweep — that is why it is asserted rather than eyeballed.

**One thing left unverified, stated rather than glossed.** A second full run to confirm byte-identical output was started and hit the 2-minute tool timeout — the ten cluster bootstraps at `N_BOOT = 10000` each are the slow part. The script is deterministic *by construction*: every bootstrap goes through `metrics_lib.cluster_bootstrap` with `SEED = 20260901` explicitly passed, and no other randomness enters. But that is an argument, not an observation. If byte-for-byte reproducibility needs to be *shown* for the paper, re-run with a longer timeout and diff; it was not shown here.

**One judgement call, flagged rather than hidden.** Seven rows were excluded: 4 SMOKE rows with no gold label (nothing to score against) and 3 rows in the legacy `criminal_paired` (n=2) and `criminal_unnumbered` (n=1) sets, which are too small to carry an interval worth printing. The count and reason are in the CSV as `rows_analysed`. Excluding them changes no reported number, because every reported number is per-query-set.

---

### 7. What I could not compute, and why

- **Whether lowering the floor would improve the *answer*.** Everything here stops at retrieval. Recall says the gold section reached the model's context window; it does not say the model read it, cited it, or got the answer right. Testing that requires re-generating answers under the counterfactual floor, which is API spend and outside this task's zero-API-call constraint. **NOT MEASURED.** Do not let the sweep table be read as an answer-quality claim.
- **The cost of the extra text, in tokens or rupees.** `answer.prompt_tokens` exists in the run logs, but it was recorded for the *deployed* chunk count. What 15 chunks instead of 5.1 would cost in prompt tokens cannot be read off stored data; it would have to be estimated from chunk lengths, and `stages.jsonl` stores only a 160-character `text_head`, not full chunk text. **NOT MEASURED.** `counterfactual_mean_chunks` is the honest proxy and is reported as a count, not a cost.
- **What the relative arm alone is costing.** The three non-layman sets lose 1.5 / 3.0 / 4.1 points between `raw_15` and `filtered_n` and this sweep cannot recover any of it, because the sweep holds the `−0.15` constant fixed by design. A sweep over the relative arm is a separate experiment and was not in scope.
- **Whether the `>=3` forced-through rule helps or hurts.** It fires constantly on layman queries — 7 of the 9 cuts had exactly 3 chunks surviving, meaning nothing cleared the threshold and the rule alone kept the pipeline from sending an empty context. Isolating its contribution means varying it, which the brief explicitly holds fixed. **NOT MEASURED.**
- **Anything about a floor between 0.30 and 0.35, or below 0.20.** Only the five specified floors were computed. Layman recall is identical at 0.30 and 0.25 (both 0.117) while the chunk count jumps 9.0 → 13.4, so the useful frontier clearly lies somewhere in 0.20–0.30 — but naming an optimum from this evaluation set would be tuning on the test set, which is the thing this task exists to avoid. **DELIBERATELY NOT COMPUTED.**
- **Statistical power on the binding-arm split.** With 9 layman cuts and 14 non-layman cuts, the intervals are wide (`[0.701 – 1.000]` and `[0.000 – 0.324]`). The split is unambiguous in direction and the intervals do not overlap, but the *rate* is estimated from a couple of dozen events. No amount of analysis fixes that; only more queries would.

---

### 8. What surprised me

**Three things, in ascending order of how much they matter.**

**First, the split was 100/0, not 80/20.** The hypothesis was that the floor "does nearly all the damage" on layman queries. The data are cleaner than the hypothesis: **every** layman cut was floor-bound and **not one** of the 14 non-layman cuts was. There was no messy middle to explain away. That happens because the two query populations have almost disjoint `top_score` distributions — layman averages 0.335, the others 0.57 to 0.82 — and the arm that binds is determined entirely by whether `top_score` clears 0.50. It is a threshold effect on a threshold, and it partitions the query sets almost perfectly.

**Second, the floor is a complete no-op on three of four query sets.** Removing a filter constant entirely and watching *nothing at all change* — same recall to three decimals, same chunk count to one — was not what I expected from a "the filter is costing us recall" framing. It reframes 0.35 from "a threshold that is too aggressive" to "a threshold that is only ever consulted when retrieval has already failed." The floor is not a filter for most of the system's traffic; it is a trapdoor that opens only under weak queries.

**Third, and this is the one that should change how the paper is written: the filter is the smaller problem.** I came into this expecting the headline to be "the filter halves layman recall," and it does. But the number it halves is **15.0%**. Turning the filter off completely gets layman recall to 15.0% and no further, because for 102 of 120 layman questions the correct section was never in the retrieved 15 to begin with. The filter is a visible, fixable, one-constant defect sitting on top of a much larger and much less tractable retrieval failure — plain-English situational queries simply do not embed close to statutory prose. Fixing the floor would take one character. It would still leave 85% of the public's questions unanswerable. The genuinely surprising result of this task is how much less important its own subject turned out to be than the thing standing behind it.

---

## Citation statute-binding bug

Output file: `core/citations.py`, `tests/test_citations_bug.py`

Regenerate with:

```bash
# 1. the code artifact and its tests
./venv/Scripts/python.exe -m pytest -q tests/test_citations_bug.py
./venv/Scripts/python.exe -m pytest -q tests/

# 2. the blast-radius numbers in section 3.
#    Needs the OLD (proximity) parser to compare against. It is the version
#    committed before this change; at the time of writing that is HEAD.
git show HEAD:core/citations.py > /tmp/citations_old.py
./venv/Scripts/python.exe - <<'PY'
import importlib.util, json, sys
from pathlib import Path
sys.path.insert(0, ".")
from core import citations as new
from experiments.metrics_lib import wilson
spec = importlib.util.spec_from_file_location("citations_old", "/tmp/citations_old.py")
old = importlib.util.module_from_spec(spec)
sys.modules["citations_old"] = old            # dataclass needs the module registered
spec.loader.exec_module(old)

def units(t):                                  # every reference match, in order
    out = []
    for m in new._SECTION_RE.finditer(t):
        if m.group(1) or m.group(2): out.append((m.start(), m.end()))
    for m in new._ARTICLE_RE.finditer(t): out.append((m.start(), m.end()))
    for m in new._ORDER_RE.finditer(t):  out.append((m.start(), m.end()))
    return out

def pct(k, n, label):
    p, lo, hi = wilson(k, n)
    print(f"{label:44s} {k:5d}/{n:<5d} = {100*p:5.1f}%  [{100*lo:4.1f}, {100*hi:5.1f}]")

texts = []
for f in sorted(Path("runs").glob("*/queries.jsonl")):
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.strip():
            t = (json.loads(line).get("answer") or {}).get("answer_text") or ""
            if t.strip(): texts.append(t)

tot = same = unk = flip = gain = 0
risk_tot = risk_unk = risk_flip = 0
recod_flip = 0
RECOD = {("IPC","BNS"),("BNS","IPC"),("CRPC","BNSS"),("BNSS","CRPC"),("IEA","BSA"),("BSA","IEA")}
n_risk = 0
for t in texts:
    risky = {"IPC", "BNS"} <= new.named_statutes(t)
    n_risk += risky
    for s, e in units(t):
        o, n = old._statute_near(t, s, e), new._statute_for_unit(t, s, e)
        tot += 1; risk_tot += risky
        if o == n: same += 1
        elif o is not None and n is None: unk += 1; risk_unk += risky
        elif o is None: gain += 1
        else:
            flip += 1; risk_flip += risky; recod_flip += (o, n) in RECOD

print(f"answers with non-empty answer_text  n = {len(texts)}")
print(f"citation units in those answers     n = {tot}")
pct(n_risk, len(texts), "answers naming BOTH IPC and BNS (at risk)")
pct(same, tot, "units: attribution UNCHANGED")
pct(unk,  tot, "units: confident statute -> UNKNOWN")
pct(flip, tot, "units: statute A -> statute B")
pct(gain, tot, "units: UNKNOWN -> confident statute")
pct(risk_unk,  risk_tot, "at-risk units: confident -> UNKNOWN")
pct(unk - risk_unk, tot - risk_tot, "not-at-risk units: confident -> UNKNOWN")
pct(risk_flip, risk_tot, "at-risk units: statute A -> statute B")
pct(flip - risk_flip, tot - risk_tot, "not-at-risk units: statute A -> B")
pct(recod_flip, flip, "flips that are a recodification pair")
PY
```

Owner: Wave 1 Subagent 3

---

### 1. ELI5 — what does this measure?

When the system writes an answer, it names statutory provisions in prose:
"Section 420 IPC", "Section 190 of the Bharatiya Nyaya Sanhita". Something has
to read that prose back and turn it into structured records, because every
citation metric in the paper — is the cited section actually in the corpus? did
the answer cite the code that governs? — compares *records*, not sentences.
That reader is `core/citations.py`.

Finding the **number** is easy: look for the word "Section" followed by digits.
Finding which **Act** the number belongs to is the hard part, because a section
number on its own is meaningless. Section 302 is murder under the IPC and
wounding religious feelings under the BNS. Same digits, different offence.

**What was silently going wrong.** The old rule was: look 60 characters left and
60 characters right of the number, and take whichever Act name is *closest*.
That is a guess dressed up as a measurement, and it fails hardest on exactly the
sentences this project exists to study.

India replaced the IPC (Indian Penal Code, 1860) with the BNS (Bharatiya Nyaya
Sanhita, 2023) on 1 July 2024. Both are still operative — which one applies
depends on when the offence happened. So a **correct** answer names both codes
in one paragraph. And then this happens, from her own logs (run
`2026-08-23_0206_36ec68d`, query `P0037`):

> "...the statement of the victim must be recorded by a woman police officer,
> and later before a Judicial Magistrate under **Section 164 of the CrPC** (or
> **Section 183 of the Bharatiya Nagarik Suraksha Sanhita, 2023**)."

The answer is right. Section 164 CrPC and Section 183 BNSS are the same power
under the old code and the new. But the logged record says:

```
CRPC Section 164, CRPC Section 183      <- "CrPC" was nearer than "Bharatiya
                                           Nagarik Suraksha Sanhita"
```

Section 183 was recorded as CrPC even though the answer spells the correct Act
out in full, eight characters to the right. The parser looked at raw character
distance and "CrPC" won by a nose.

**What changes now.** A statute is bound to a number only when the two sit in
the same **citation unit** — the reference plus the material touching it that
carries no meaning of its own. Where no Act is attributable, the answer is an
explicit **UNKNOWN** (`statute=None`, printed as `?`), not a guess.

The same passage now reads:

```
CRPC Section 164, BNSS Section 183      <- correct
```

And the sentence the bug was originally found on:

> "Under the Indian Penal Code the offence was punishable, and the
>  corresponding provision is now Section 190."

was `IPC Section 190` (wrong — 190 is BNS) and is now `? Section 190`. The
parser no longer knows, and now says so.

---

### 2. Technically

**Definition of a citation unit, and why this one.**

A citation unit is *the reference match, extended in both directions over
tokens that carry no propositional content*. Two kinds of token may extend it:

| token kind | members |
|---|---|
| FILLER | whitespace, `,` `(` `)` `[` `]` `*` `|` `/`, the words `of` `the` `under`, a 4-digit year |
| ALIAS | any statute name in `STATUTE_ALIASES` |

Everything else — every content word, every conjunction (`and`, `or`, `which`),
and the sentence-level marks `.` `;` `:` `-` — **terminates** the unit.

Three definitions were on the table:

1. **The same regex match.** Too narrow on its own: `_SECTION_RE` captures only
   "Section 190", so `Section 420 IPC` would lose its statute. It becomes
   workable only once the match is extended, which is what the filler grammar
   above does. **This is the one chosen**, in that extended form.
2. **The same bracketed/parenthetical reference.** Rejected: Indian legal prose
   mostly does not bracket its citations. All four preserved behaviours would
   fail.
3. **The clause, delimited by comma / semicolon / conjunction.** Rejected for a
   concrete reason: `and` is a clause delimiter, so `"Sections 299 and 300 IPC"`
   would split into `Sections 299` | `300 IPC`, stranding 299 with no statute.
   The enumeration is one citation, and this definition cuts it in half.

Definition 1-extended keeps the enumeration whole because attribution is
resolved **once against the whole match** in `add_run()` and then applied to
every number in the run — the enumeration *is* the unit.

**Two refinements, both forced by the real data.**

*(a) A trailing statute is decisive.* Indian citation form writes the Act after
the number. When exactly one Act follows through filler alone, that settles it,
even if a leading Act is also in the unit. This is what makes
`"| Code of Criminal Procedure (CrPC) / BNSS | Sec 154 CrPC / Sec 173 BNSS |"`
resolve to CRPC 154 and BNSS 173 rather than collapsing to UNKNOWN because the
header cell names two codes. A **leading** Act is a heading, a topic sentence or
a table header, and is used only as a fallback.

*(b) An Act belongs to the reference it is glued to.* These two say the same
thing and differ only in which side of its number each Act sits on:

```
Section 357C CrPC / Section 397 BNSS      -> CRPC 357C, BNSS 397
CrPC Section 154(3) / BNSS Section 175(3) -> CRPC 154(3), BNSS 175(3)
```

In the second, the Act *following* 154(3) is BNSS — but a list separator
(`/ | , ;`) divides them and BNSS is immediately followed by its own
`Section 175(3)`. So it is discarded, and the leading `CrPC` is used. In the
first, only a space divides 357C from CrPC, so CrPC stands. An Act is dropped
only when **both** hold: a separator divides it from this reference, **and** a
reference begins right after it.

**Ambiguity.** If the unit ends up naming two different canonical codes and
none of them trails, the result is UNKNOWN. Two aliases of the *same* code
("Indian Penal Code (IPC)") are one statute, because the comparison is over
canonical codes, not surface strings.

**UNKNOWN reuses `None`; it is not a new sentinel.** Every call site was
checked before deciding:

| site | code | why `None` is right |
|---|---|---|
| `core/citations.py` | `Provision.key` | already renders `None` as `?` — `?:section:190` |
| `core/citations.py` | `same_provision` | "a reference with no statute matches on kind and number only". Retrieved *statutory text* also parses with `statute=None` (a chunk reads "Section 302. Punishment for murder" and never names its own Act), so grounding already compares this way |
| `core/statute_mapper.py:164` | `[p for p in extract_provisions(t) if p.statute]` | truthiness filter — drops UNKNOWNs, which is the correct behaviour for deciding which corpus to search |
| `core/verifier.py:reattribute` | `if exact or not p.statute:` | already leaves unattributed citations alone |
| `core/verifier.py:_vintage_relation` | `if not cited: return None` | an UNKNOWN can never be scored as a vintage mismatch — conservative, correct |
| `scripts/analyze_eval.py:178,188` | `extract_provisions(g.replace(" ", " Section "))` | gold strings are `"IPC 149"` → `"IPC Section 149"`, leading-form, still attributed |

A sentinel string such as `"UNKNOWN"` would be **truthy** and would walk
straight past four of those six guards, silently entering metrics as if it were
a real statute. That is the same class of failure this change exists to remove.
`tests/test_citations_bug.py::test_unknown_uses_none_and_not_a_sentinel_string`
pins the decision.

**Performance.** The unit regexes use atomic groups `(?>…)` so a long run of
aliases and filler cannot backtrack exponentially, and the scan is capped at
`_UNIT_SCAN = 200` characters per side. The cap is a cost bound, not part of
the rule — a run of pure filler longer than 200 characters does not occur.

**Diff shape:** `core/citations.py` only. `_statute_near()` (28 lines, the
nearest-name-wins rule) deleted; `_statute_for_unit()`, `_trailing_statutes()`
and `_reference_starts_at()` added, plus the token grammar. One line changed
inside `add_run()`. No signature changed, nothing else in the repo touched.

---

### 3. What the number came out as

Measured over **every answer text in `runs/*/queries.jsonl`** — 8 run
directories, all `answer.answer_text` fields that are non-empty. Read-only.

Denominators, stated up front:

- **859** answers with a non-empty `answer_text`
- **6,687** citation units (reference matches) inside those answers
- **5,616** deduplicated `Provision` records — what `verifier.cited` counts

Sanity check first: the old parser reproduces the `verifier.cited` list actually
logged at run time in **857/857 = 100.0% [99.6, 100.0]** of records that have
one. So the "before" column below is the parser that produced the recorded
numbers, not a reconstruction of it.

**The population at risk** — answers that mention both the IPC and the BNS, the
case where proximity can pick the wrong code:

```
answers naming BOTH IPC and BNS       497/859  = 57.9%  [54.5, 61.1]
```

Not a corner case. It is the majority of the corpus.

**Change at the citation-unit level** (n = 6,687):

```
attribution UNCHANGED                5555/6687 = 83.1%  [82.2, 84.0]
confident statute -> UNKNOWN         1060/6687 = 15.9%  [15.0, 16.7]
statute A -> statute B                 72/6687 =  1.1%  [ 0.9,  1.4]
UNKNOWN -> confident statute            0/6687 =  0.0%  [ 0.0,  0.1]
answers with >= 1 changed unit        447/859  = 52.0%  [48.7, 55.4]
```

**Change at the deduplicated `Provision` level** (n = 5,616), which is the unit
the verifier's metrics are computed over:

```
confident statute -> UNKNOWN          797/5616 = 14.2%  [13.3, 15.1]
other attribution change              360/5616 =  6.4%  [ 5.8,  7.1]
```

**The change is concentrated on the at-risk population**, which is the finding:

| | at risk (n = 3,712 units) | not at risk (n = 2,975 units) |
|---|---|---|
| confident → UNKNOWN | **20.8%** [19.5, 22.1] | 9.7% [8.7, 10.8] |
| statute A → statute B | **1.4%** [1.0, 1.8] | 0.7% [0.5, 1.1] |

The intervals do not overlap on either row. Attributions in answers naming both
codes were more than twice as likely to be unsupported by the text.

**And the corrections are almost entirely old-code/new-code confusions:**

```
flips that are a recodification pair    70/72  = 97.2%  [90.4, 99.2]
  (IPC<->BNS, CrPC<->BNSS, IEA<->BSA)

direction        count
CRPC -> BNSS       46
BNS  -> IPC        10
BNSS -> CRPC        8
IEA  -> BSA         2
IPC  -> BNS         2
BSA  -> IEA         2
CONSTITUTION -> CRPC 2   <- the only 2 that are not a recodification pair
```

**Worked example, real, from `runs/2026-08-23_0206_36ec68d`, query `P0037`**
("What is the punishment for rape under Section 376 of the Indian Penal Code?"):

```
logged (old): CRPC 164, CRPC 183, IPC 376(1), IPC 376(2), IPC 376(3), IPC 376A,
              IPC 376AB, IPC 376D, IPC 228A, BNS 64, CRPC 357C, CRPC 397, CRPC 357A
now   (new):  CRPC 164, BNSS 183, IPC 376(1), IPC 376(2), IPC 376(3), IPC 376A,
              IPC 376AB, IPC 376D, IPC 228A, BNS 64, CRPC 357C, BNSS 397, CRPC 357A
                         ^^^^                                    ^^^^
```

Two of thirteen corrected, both CrPC → BNSS, both cases where the answer named
the BNSS in full and the parser overruled it on character distance.

---

### 4. How to read it

**83.1% unchanged** is the headline reassurance: this is a targeted correction,
not a rewrite. Four fifths of all attributions were already right and are
untouched.

**15.9% → UNKNOWN** is the price. Those attributions were *asserted* before and
are *withheld* now. Read that as: in one attribution in six, the answer text did
not actually say which Act the number belonged to, and the old parser filled the
gap by guessing. Some of those guesses were correct by luck. We can no longer
tell which, and pretending otherwise is what got two metrics retired.

**1.1% flipped, 97.2% of them recodification pairs** is the sharp result. This
is the error the paper cares about — not a diffuse 1% noise floor but a
systematic old-code/new-code mislabel. 72 units is small in absolute terms
because a flip needs *two* Acts close enough to compete; the 1,060 UNKNOWNs are
the larger, quieter version of the same defect.

**0 units gained a statute.** Attribution can only get stricter under the new
rule. That matters for interpreting any before/after comparison: nothing here
can inflate a citation count.

**On the CIs.** These are Wilson intervals from `experiments/metrics_lib.py`.
They describe sampling uncertainty in the *rate*, given these 6,687 units — they
do **not** cover the risk that these 859 answers are unrepresentative of Indian
legal answers generally. Read them as "how precisely do I know this rate on this
corpus", not "how well does this generalise".

**One caution on the units.** The 6,687 citation units are not independent —
they cluster within 859 answers, and an answer that formats its citations in a
table contributes many similar units at once. So the true uncertainty is wider
than the interval printed. The answer-level number (52.0% [48.7, 55.4] of
answers have at least one changed attribution) is the more conservative one to
quote in the paper.

---

### 5. What this means for the paper

**The two retired metrics were `gold_cited` and `wrong_era_cited`**
(`docs/WORKLOG.md`, "A metric retired mid-analysis"). They were retired because
`wrong_era_cited = 100%` could not separate *"wrongly relied on repealed law"*
from *"correctly explained the law changed"* — opposite behaviours, identical
measurement.

**Can they be revived? Partially, and each for a different reason.**

`wrong_era_cited` — **yes, and this is the fix it needed.** The specific
mechanism that broke it is gone: an answer citing BNS 190 is no longer recorded
as IPC 190 because "Indian Penal Code" appeared upstream. The metric can be
recomputed, with two conditions attached:

1. It must be **recomputed from the answer texts, not read off the recorded
   `verifier.*` fields**, which were written by the old parser. Mixing them
   would be exactly the "never mix pre-fix and post-fix numbers" failure.
2. It must be reported with an explicit **denominator of scoreable citations**.
   Which brings us to the honest part.

`gold_cited` — **yes, and it should improve**, since it asks whether the gold
provision appears among the cited ones and `same_provision()` lets an UNKNOWN
match on number alone. An UNKNOWN citation is still comparable against a gold
section. But that same permissiveness cuts both ways (see below).

**Say it plainly: some citations can no longer be scored, and some queries may
not be scoreable at all.** 14.2% of extracted provisions now carry no statute.
For a metric that turns on *which code* was cited — `wrong_era_cited` is exactly
that — an UNKNOWN is not a pass and not a fail, it is **not evaluable**. Those
must be reported as a third category, with its own count, never silently folded
into either side. Any answer whose citations are *all* UNKNOWN contributes
nothing to that metric, and the effective n falls accordingly. The at-risk
subgroup — the recodification queries, the ones the paper is about — loses the
most: 20.8% of its attributions, against 9.7% elsewhere.

That is a real cost and it should be stated in the paper rather than absorbed.
The defensible position is: *the previous measurement had 100% coverage and
unknown accuracy; this one has ~86% coverage and states where it is uncertain.*
A reviewer can check the second claim. They could not have checked the first.

**A claim that is now available and was not before.** 57.9% [54.5, 61.1] of
answers mention both codes, and attributions in those answers changed at more
than twice the rate of the rest, with non-overlapping intervals. That is direct
evidence that the measurement error **correlated with the treatment** — it was
not a uniform error rate that would wash out of a before/after comparison. This
is worth stating explicitly in the limitations or methodology section, because
it is the argument for why the earlier numbers had to be withdrawn rather than
merely widened.

**What this does NOT fix.** Attribution still comes from the answer's own prose.
The stronger fix is to bind each citation to the retrieved chunk that supports
it, using the chunk's authoritative `corpus` label — the machinery for that
already exists in `core/verifier.py` (`provisions_from_chunks`, `reattribute`)
and is currently called by nothing. This change makes prose-level attribution
honest; it does not make it authoritative.

---

### 6. What broke while computing this

**One error, fixed on the first attempt.** Loading the old parser from a
scratchpad copy via `importlib` raised
`AttributeError: 'NoneType' object has no attribute '__dict__'` inside
`dataclasses._process_class`. Cause: `@dataclass` looks the defining module up
in `sys.modules` to resolve annotations, and a module built with
`module_from_spec` is not registered there until you put it there. Fix:
`sys.modules["citations_old"] = old` before `spec.loader.exec_module(old)`. The
reproducing command above carries that line and a comment.

**No test failures, pre-existing or otherwise.** No pre-existing test was
pinning the old proximity behaviour — checked deliberately, because a
pre-existing test failing here would have been a finding (a wrong behaviour
written into the spec), not a licence to edit it.

**Not an error, but worth recording as design cost.** The rule went through
three measured revisions before it held:

| revision | at-risk consequence | why revised |
|---|---|---|
| filler = punctuation + `of/the/under/year` | 53.1% of units → UNKNOWN | markdown table rows (`\| Indian Penal Code (IPC) \| Sec 302 \|`) lost their Act to the pipe |
| + `\|` `/` as filler, whole unit must name one code | 23.5% → UNKNOWN | `Sec 154 CrPC / Sec 173 BNSS` collapsed to UNKNOWN — a correct trailing citation thrown away |
| + trailing statute decisive, + separator rule | **15.9% → UNKNOWN** | final |

The intermediate versions were *rejected on named counterexamples*, not on the
size of the number. The second one, in particular, would have introduced a
**new** wrong attribution (`CrPC Section 154(3) / BNSS Section 175(3)` reading
154(3) as BNSS) — caught by inspecting the flips one by one rather than
accepting the aggregate.

---

### 7. What I could not compute, and why

**Accuracy. This is the important gap.** Everything in section 3 is a measure of
*change* — how many attributions differ — not of *correctness*. To say "the new
rule is 94% accurate and the old one was 79%" needs a human-labelled sample of
citation units with the true Act for each. No such labelled set exists, and
producing it is annotation work, not parsing work. I can show the direction is
right on named examples (P0037's Section 183, the BNS/IPC table cells); I cannot
put a number on it.

**The right size for that sample, if it gets built:** to separate two rates near
90% with non-overlapping Wilson intervals you need on the order of 300–400
labelled units. This should be folded into E1 (the annotated query set), which
has no prerequisites, rather than run as a separate exercise.

**How many of the 1,060 new UNKNOWNs were previously CORRECT guesses.** Same
reason — it needs ground truth. This is the honest cost of the change and it is
currently unquantified. My expectation, from reading the examples, is that it is
substantial: patterns like `"| Indian Penal Code, 1860 (IPC - Historical) | Sec
141 & 149 |"` lose their Act to the content word "Historical" inside the header
cell, and the old guess was right there. Treat 15.9% as an upper bound on
information lost, not an estimate of errors removed.

**The downstream effect on `ungrounded_rate`, `out_of_corpus_rate` and
`panel_prose_jaccard`.** Computing those requires re-running the verifier over
the recorded runs, and `core/verifier.py` belongs to another subagent this wave.
Direction is predictable but the magnitude is not: `same_provision()` treats an
UNKNOWN as matching on number alone, so UNKNOWNs should make grounding look
*better* and out-of-corpus look *smaller*. That is a leniency introduced by this
change and it must be checked before any of those three numbers is quoted again.

**Whether the four `runs/` directories with fewer than 100 records are
independent replicates or re-runs of the same queries.** I pooled all 859
answers. If some are duplicates the effective n is smaller and the intervals are
optimistic. The answer-level figure (52.0%) is less exposed to this than the
unit-level ones.

---

### 8. What surprised me

**The corpus does not write prose, it writes tables.** I designed the rule
against sentences and it looked correct on all four preserved behaviours and on
the regression. Then I ran it over the real answers and 53% of attributions
vanished. The reason had nothing to do with the linguistics: the model answers
in markdown tables, `| Indian Penal Code (IPC) | Sec 302 | Punishment |`, and a
table row binds its Act cell to its section cell structurally, not by proximity.
Nothing in the docstrings or the existing tests hinted at that. **The lesson is
the "measure the blast radius, do not assume it" instruction earning its keep —
had I shipped on the tests alone, the fix would have destroyed half the signal
while passing every check.** The pipe and slash are in the filler set because of
what the logs say, and the code comment says so.

**The old rule failed even when the answer spelled the Act out in full.**
I expected the failures to be cases where the model wrote a bare number.
Instead, `"Section 183 of the Bharatiya Nagarik Suraksha Sanhita, 2023"` was
recorded as CrPC — the correct Act is *right there*, eight characters away, and
a shorter alias 60 characters off won on raw character distance. Proximity was
not merely a weak signal; it actively overruled explicit evidence. The 34-letter
correct name lost to the 4-letter wrong one because the metric was characters.

**97.2% of the corrections are recodification pairs.** I expected the flips to
be a mixed bag of near misses. They are almost entirely IPC↔BNS, CrPC↔BNSS and
IEA↔BSA — the exact axis the paper measures. An error rate that lands on the
treatment variable is not a precision problem, it is a validity problem, and
that distinction is what justifies withdrawing the earlier numbers rather than
reporting them with wider error bars.

**Zero units gained a statute.** I expected a handful, from cases where the old
60-character window was too short and the unit rule reaches further through
filler. Not one, in 6,687. The old window was never the binding constraint —
the *decision rule inside it* was.

---

## GATE smoke test

The three gate numbers and their full explanation blocks live in
`results/smoke_test.md` rather than here, because the GATE prompt in
`docs/PLAN.md` section 5 names that file specifically. Three blocks, eight
headings each.

---

## Retrieval metrics
Output file: `results/retrieval_metrics.csv`
Regenerate with:

```
./venv/Scripts/python.exe experiments/exp01_retrieval.py        # writes the CSV
./venv/Scripts/python.exe experiments/check01_retrieval_check.py  # verifies it
```

Owner: Wave 2 Subagent 1

---

### 1. ELI5 — what does this measure?

You ask the system a legal question. Before it writes a word of answer, it goes to the shelf and pulls **15 passages** out of the corpus. Somebody has already written down, by hand, **which section of which Act is the right one** for that question — that is the *gold* answer.

This file asks one question, over and over, from different angles:

> **Did the right section come off the shelf at all — and how near the top?**

That is all. It says nothing about whether the final answer was any good. It only grades the fetching.

Four ways of grading the same fetch:

| Name | Plain English | Worked on one real query |
|---|---|---|
| **Recall@k** | Of all the questions, what share had the right section somewhere in the top *k* passages? | On the 120 layman questions, the right section was in the top 5 for **12** of them. 12/120 = **Recall@5 = 0.100** |
| **Precision@k** | Of the *k* passages you pulled, what share were the right one? | If 1 of 15 passages is the gold one, Precision@15 = 1/15 = 0.067 |
| **MRR** | *Mean Reciprocal Rank.* If the right section was 1st, score 1; 2nd, score ½; 3rd, ⅓; never, 0. Average that over all questions. | Rewards being near the top, not merely present |
| **nDCG@k** | Same idea as MRR but the penalty for being lower down falls more gently: 1/log₂(rank+1) | 1st = 1.00, 2nd = 0.63, 3rd = 0.50 |

And a **confidence interval** (CI). Measuring 120 questions is a sample, not the whole world. The 95% CI is the honest range the true value plausibly sits in. `0.150 [0.097, 0.225]` means: *measured 15.0%; the truth is plausibly anywhere from 9.7% to 22.5%.* **A number without its interval is not a result.** If two intervals overlap heavily, you have not shown a difference.

---

### 2. Technically

Everything is imported from `experiments/metrics_lib.py`. Nothing is reimplemented.

| Thing | How |
|---|---|
| Rows | `load_logs()` → 621 deduplicated rows, **617 carrying gold** |
| Ranked list | `load_stages()` → `ranked_sections()`, using the **authoritative `section_number`** from the Qdrant payload |
| Section identity | `same_section()` / `normalise_section()` — the one comparison rule |
| Recall@k | `correctness_label(row, "retrieved@k", k, stages)` — binary per query |
| Precision@k, MRR, nDCG@k | `precision_at_k`, `reciprocal_rank`, `ndcg_at_k` |
| Intervals, proportions | `wilson(k, n)` → `ci_lo` / `ci_hi` |
| Intervals, means | `cluster_bootstrap(..., "pair_id", 10000, 20260901)` → `cluster_ci_lo` / `cluster_ci_hi` |

**Why two interval methods.** Wilson is exact for a *proportion of queries* — "84 out of 120 succeeded". MRR and nDCG are not proportions; they are averages of numbers like 0.5 and 0.33, so Wilson does not apply and their `ci_lo`/`ci_hi` are deliberately **EMPTY**. For those, the bootstrap resamples the data 10,000 times and reads off the middle 95%.

**Why *cluster* bootstrap.** The query sets are 30–80 real-world *situations*, each rephrased 2–4 ways. Three phrasings of one situation are not three independent facts. Resampling rows would pretend there are 617 independent observations and report an interval that is **too narrow**. `cluster_bootstrap` resamples **situations** (`pair_id`). You can see the cost: layman Recall@15 is `0.150`, Wilson `[0.097, 0.225]`, cluster `[0.033, 0.275]` — the honest interval is roughly **twice as wide**.

Every row's `notes` column states which method produced its interval.

**Three stages.** `raw_15` = Qdrant score order. `reranked_15` = the same 15 reordered by entity match. `filtered_n` = what survived `max(top−0.15, 0.35)` and reached the language model. **`raw_15` is primary for MRR and nDCG**, because reranking deliberately overwrites score order, so a rank measured after it grades the rerank policy, not the retriever.

---

### 3. What the number came out as

**Headline — Recall@15**, share of queries with the gold section retrieved. Definition `retrieved@k`. Wilson interval; cluster interval in the last column.

| Query set | n | raw_15 | reranked_15 | filtered_n | cluster CI (raw_15) |
|---|---:|---|---|---|---|
| `generated_retrieval` | 198 | **0.692** [0.624, 0.752] | 0.692 [0.624, 0.752] | 0.677 [0.609, 0.738] | [0.647, 0.735] |
| `paired_recodification` | 99 | **0.737** [0.643, 0.814] | 0.737 [0.643, 0.814] | 0.707 [0.611, 0.788] | [0.687, 0.798] |
| `paired_dated_conflict` | 197 | **0.492** [0.423, 0.562] | 0.492 [0.423, 0.562] | 0.452 [0.384, 0.522] | [0.437, 0.543] |
| `layman_situation` | 120 | **0.150** [0.097, 0.225] | 0.150 [0.097, 0.225] | 0.075 [0.040, 0.136] | [0.033, 0.275] |
| **ALL (pooled)** | **617** | **0.530** [0.491, 0.569] | 0.530 [0.491, 0.569] | 0.493 [0.453, 0.532] | [0.483, 0.576] |

**Recall@k at `raw_15`**, definition `retrieved@k`, Wilson intervals in the CSV:

| Query set | n | k=1 | k=3 | k=5 | k=10 | k=15 |
|---|---:|---:|---:|---:|---:|---:|
| `generated_retrieval` | 198 | 0.545 | 0.626 | 0.636 | 0.687 | 0.692 |
| `paired_recodification` | 99 | 0.495 | 0.646 | 0.677 | 0.737 | 0.737 |
| `paired_dated_conflict` | 197 | 0.325 | 0.431 | 0.452 | 0.487 | 0.492 |
| `layman_situation` | 120 | 0.025 | 0.058 | 0.100 | 0.133 | 0.150 |
| **ALL** | **617** | 0.366 | 0.457 | 0.480 | 0.524 | **0.530** |

**MRR@15**, definition `retrieved@k`, cluster-bootstrap intervals:

| Query set | n | raw_15 (PRIMARY) | reranked_15 | filtered_n |
|---|---:|---|---|---|
| `generated_retrieval` | 198 | 0.595 [0.551, 0.637] | 0.643 [0.598, 0.686] | 0.628 [0.581, 0.672] |
| `paired_recodification` | 99 | 0.573 [0.469, 0.678] | 0.650 [0.571, 0.729] | 0.620 [0.525, 0.712] |
| `paired_dated_conflict` | 197 | 0.381 [0.305, 0.456] | 0.447 [0.388, 0.502] | 0.416 [0.341, 0.484] |
| `layman_situation` | 120 | 0.051 [0.008, 0.115] | 0.051 [0.008, 0.115] | 0.038 [0.000, 0.100] |
| **ALL** | **617** | **0.418 [0.372, 0.464]** | 0.467 [0.421, 0.510] | 0.444 [0.396, 0.491] |

**nDCG@15 and Precision@15 at `raw_15`**, definition `retrieved@k`, cluster intervals:

| Query set | n | nDCG@15 | Precision@15 |
|---|---:|---|---|
| `generated_retrieval` | 198 | 0.618 [0.577, 0.657] | 0.046 [0.043, 0.049] |
| `paired_recodification` | 99 | 0.612 [0.523, 0.702] | 0.057 [0.050, 0.064] |
| `paired_dated_conflict` | 197 | 0.408 [0.338, 0.475] | 0.034 [0.030, 0.038] |
| `layman_situation` | 120 | 0.074 [0.019, 0.147] | 0.012 [0.003, 0.023] |
| **ALL** | **617** | 0.445 [0.400, 0.489] | 0.037 [0.034, 0.041] |

**The other two correctness definitions — no stage, no k.** `cited` and `grounded` are properties of the **answer**, not of the ranked list. They do not change when k changes and they do not change between stages. Their `stage` and `k` cells in the CSV are **EMPTY on purpose**. Reporting them at 3 stages × 5 k values would put 15 copies of one measurement into the table and invite a reviewer to read them as 15 measurements.

| Query set | n | `cited` (Wilson) | `grounded` (Wilson) |
|---|---:|---|---|
| `generated_retrieval` | 198 | 0.960 [0.922, 0.979] | 0.126 [0.087, 0.180] |
| `paired_recodification` | 99 | 0.949 [0.887, 0.978] | 0.020 [0.006, 0.071] |
| `paired_dated_conflict` | 197 | 0.868 [0.814, 0.908] | **0.000** [0.000, 0.019] |
| `layman_situation` | 120 | 0.633 [0.544, 0.714] | **0.000** [0.000, 0.031] |
| **ALL** | **617** | 0.864 [0.835, 0.889] | 0.044 [0.030, 0.063] |

---

### 4. How to read it

**Read the interval, not the point.** `layman_situation` Recall@15 is `0.150`, but the cluster interval is `[0.033, 0.275]`. On 30 situations you have established *"low"*, not *"15%"*.

**Read the stage.** `layman_situation` Recall@15 is **0.150 at `raw_15`** and **0.075 at `filtered_n`** — the same measurement, two stages, a factor of two apart. This is exactly the confusion `metrics_lib` was built to end. **Never quote either without naming the stage.**

**Read the definition.** Pooled, the gold section is *retrieved* 53.0% of the time but *cited* 86.4% of the time. The answer cites the right law more often than the system finds it — those citations come from the model's own knowledge, not the corpus.

**Do not read four independent metrics into this table.** See §8 — Precision@k and nDCG@k are, on this data, near-deterministic functions of Recall@k and rank. They agree because they are algebraically bound to agree, not because four instruments converged.

**Two things not to read as differences:**

- `raw_15` and `reranked_15` have **identical Recall@15 in every row**. That is arithmetic, not a finding: reranking reorders the same 15 chunks, and membership of a 15-item list cannot change when you shuffle it.
- `paired_dated_conflict` pools **two experimental conditions** — 99 rows at `intervention=baseline` and 98 of the *same* queries at `intervention=both`. Its 0.492 is an average of 0.293 and 0.694. The split is in the CSV as `recall_at_k_baseline_rows` / `recall_at_k_both_rows`. **Do not quote 0.492 as a system property.**

---

### 5. What this means for the paper

**(a) The layman result survives full measurement, and gets worse the closer you look.** For questions a real person would ask — no section number, no Act name — the gold provision reaches the model **7.5%** of the time [0.040, 0.136], with MRR **0.038**. Meanwhile the answer *cites* the gold provision 63.3% of the time and is fully grounded **0.0%** of the time [0.000, 0.031]. The pipeline is barely retrieval-augmented on exactly the queries it exists for. Recall@k and MRR now put numbers with intervals on a claim that was previously one figure without a stage.

**(b) Statutory vocabulary is worth about 4.6× the recall.** `generated_retrieval` 0.692 [0.624, 0.752] vs `layman_situation` 0.150 [0.097, 0.225] at `raw_15`, same index, non-overlapping intervals — the strongest clean contrast in the table.

State the contrast carefully, because the two sets differ in more than one way. `generated_retrieval` is built **from the corpus's own section titles**: 80 of 198 queries name the section outright (`variant=numbered`), 60 name the Act and paraphrase the title (`topic_code`), 60 give the title language alone (`topic_only`). Even the hardest third therefore shares vocabulary with the target chunk. `layman_situation` is first-person narrative with no statutory vocabulary at all. So this is **"query written in the language of the statute" vs "query written in the language of the person"**, not purely "numbered vs unnumbered". A per-variant breakdown would separate the two and is **not computed here** — it belongs with the routing analysis.

**(c) The adaptive filter is a real, quantified cost.** Pooled Recall@15 falls 0.530 → 0.493 between `raw_15` and `filtered_n`. On layman queries it **halves**, 0.150 → 0.075. The retriever had the answer and the threshold threw it away. This is Subagent 5's territory but it is visible here.

**(d) Entity reranking helps rank order — the opposite of the pre-registered expectation.** Pooled MRR rises 0.418 → 0.467 and nDCG 0.445 → 0.482 from `raw_15` to `reranked_15`. The rerank was described as "destroying score order"; it does, but it moves the *gold* chunk **up**. Cluster intervals overlap, so this is **not established** — it needs the paired bootstrap, not two intervals compared by eye. Flag as a candidate, do not claim it.

**(e) Anything at k < 15 must name its rank convention.** See §6.

---

### 6. What broke while computing this

**One thing broke, and it was worth breaking.**

The first run of `check01_retrieval_check.py` **failed on 108 of 110 comparisons** — every k < 15 cell disagreed with `exp01`, while k = 15 and both external anchors agreed exactly. That pattern (agree at the top, disagree everywhere below) is a rank-alignment signature, not an arithmetic error.

**Cause.** `metrics_lib.ranked_sections()` **drops** chunks with no `section_number` — preamble, split continuations, demoted footnotes. Only **118 of 617** `raw_15` lists have a section number on all 15 chunks; the rest lose between 1 and 14. Dropping them **compresses rank positions**: a gold chunk sitting at retrieved position 5 is reported at rank 3.

So "rank" has two meanings:

| | What "top k" means |
|---|---|
| `recall_at_k`, `mrr_at_k`, `ndcg_at_k` | rank among chunks that **have** a section number (the `metrics_lib` convention) |
| `recall_at_k_positional`, `mrr_at_k_positional`, `ndcg_at_k_positional` | rank among chunks **as retrieved** — section-less chunks keep their slot |

At k = 15 the two are identical by construction, which is why both anchors held. Below k = 15 the `metrics_lib` convention is **optimistic**:

| Recall@k at `raw_15` | k=1 | k=3 | k=5 | k=10 | k=15 |
|---|---|---|---|---|---|
| ALL, `metrics_lib` | 0.366 | 0.457 | 0.480 | 0.524 | 0.530 |
| ALL, positional | 0.353 | 0.447 | 0.467 | 0.514 | 0.530 |
| `layman`, `metrics_lib` | 0.025 | **0.058** | **0.100** | 0.133 | 0.150 |
| `layman`, positional | 0.025 | **0.033** | **0.050** | 0.108 | 0.150 |

**On the layman set at k=5 the two differ by a factor of two.** A reader who is shown 5 passages and told "the right section was in the top 5" means the positional number.

**Resolution.** Neither route was wrong, so neither was adjusted. **Both are in the CSV**, both are independently reproduced by `check01`, and every row's `notes` names its convention. The `metrics_lib` series stays primary because it is the shared ruler every other Wave-2 agent is using and the one the anchors were set under. **This matters beyond this file:** any other agent calling `correctness_label(..., k)` with k < 15 has inherited the same optimism.

`check01` now also asserts two structural invariants that would have caught this immediately: compressed rank ≤ positional rank on every hit, and the two conventions must agree on *whether* gold was found.

Nothing else broke. The test suite is at **237 passing**, unchanged.

---

### 7. What I could not compute, and why

| Not computed | Why |
|---|---|
| `cited` and `grounded` per (stage, k) | **Not a limitation — a refusal.** They are properties of the answer text. They do not vary with k or stage. Producing 15 identical rows each would manufacture apparent variation. `stage` and `k` are EMPTY by design |
| Wilson intervals on MRR, nDCG, Precision, fraction-of-gold recall | They are means, not proportions of queries. Wilson does not apply. `ci_lo`/`ci_hi` are EMPTY; `cluster_ci_lo`/`cluster_ci_hi` carry the interval |
| A per-set row for the 3 legacy `criminal_*` queries | Excluded per the wave brief. They *do* carry gold, so they sit inside pooled `ALL`. **This is why `ALL` n=617 while the four sets sum to 614.** Recorded in `rows_analysed` |
| Anything for the 4 SMOKE rows | No gold label. Dropped, and the drop is recorded |
| Recall broken down by query **variant** (`numbered` / `topic_code` / `topic_only`, or `ipc_era` / `bns_era` / `vague` / `no_date`) | The field is on every query set and the split is worth having — but it is a routing question, not a retrieval-metrics one, and the wave brief scopes this file to per-set and pooled. See §5(b) for why it would sharpen the headline contrast |
| Whether the rerank's MRR gain is real | Needs `paired_bootstrap_auroc_diff`-style paired testing on the *same* queries, not two overlapping intervals. Out of this file's scope |
| Graded relevance for nDCG | Gold is binary — a section is right or it is not. There is no 3-point relevance judgement in this project, so IDCG = 1 and nDCG collapses (see §8) |

---

### 8. What surprised me

**(a) Three of the four metrics carry almost no information beyond the first.** This is the point a reviewer must not be allowed to miss.

The pre-registered statement was:

> *With a single binary gold section per query, Precision@k equals Recall@k / k exactly, and nDCG@k is a monotone function of reciprocal rank. Both are therefore reported for completeness rather than for information.*

**I measured both halves rather than asserting them.**

*nDCG — confirmed exactly.* Gold is binary and there is one relevant item, so IDCG = 1 and nDCG@k = 1/log₂(rank+1), a strictly increasing function of 1/rank. Across all 1,851 (query × stage) rows there are **14 distinct reciprocal-rank values and exactly 14 distinct (RR, nDCG) pairs** — a perfect one-to-one map. nDCG@15 is monotone non-decreasing in RR@15 with zero violations. **nDCG adds nothing to MRR here.**

*Precision — very nearly, but not exactly, and the exception is instructive.* Gold is a **section**; retrieval returns **chunks**; a long section is split across several chunks. When two chunks of the same gold section both land in the top k, Precision@k = 2/k while Recall@k/k = 1/k.

| Stage (single-gold rows, n=525) | k=1 | k=3 | k=5 | k=10 | k=15 |
|---|---|---|---|---|---|
| `raw_15` | 100.0% | 100.0% | 99.2% | 99.2% | 99.2% |
| `reranked_15` | 100.0% | 99.4% | 99.2% | 99.2% | 99.2% |
| `filtered_n` | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |

*(share of rows where P@k = R@k/k holds exactly)*

It breaks on **4 queries out of 525**, where the gold section spans two retrieved chunks. So the statement is right in spirit and wrong in the third decimal — **report Precision for completeness, never as corroboration.**

**Say this plainly in the paper: these are not four instruments agreeing. Recall is the measurement. MRR adds rank. Precision and nDCG are algebra.**

**(b) Gold is not always one section, which the pre-registered statement assumed.** 525 of 617 queries have one gold section; **88 have two and 4 have three** (`layman_situation` and `paired_recodification`). Two defensible recalls therefore exist, and both are in the CSV: `recall_at_k` (did **any** gold section arrive — the binary definition `correctness_label` uses, the one the 327/617 anchor was set under) and `recall_at_k_fraction_of_gold` (**what share** of a query's gold sections arrived, `metrics_lib.recall_at_k` verbatim). They differ where it matters: `paired_recodification` at `raw_15`, k=15 is **0.737** binary but **0.616** by fraction — the set is IPC↔BNS pairs, and finding one side of a pair is not finding both.

**(c) The rerank moves gold up, not down.** Discussed in §5(d). I expected `reranked_15` MRR to fall.

**(d) The independent route agreed on 2,306 comparisons using a *naive* matcher.** `check01` matches gold to chunk by exact uppercased Act + exact uppercased number — no `normalise_section()`, no `same_section()`. It reproduced every cell. Defect E2 in this project was caused by exactly this comparison being wrong, so the agreement is reassuring: on *this* data the canonicaliser is doing nothing a naive matcher would not do. It earns its place on the messy inputs (`Section 302`, `318(4)`, `CONSTITUTION Article 226`), not on these.

---

### Paired check

`experiments/check01_retrieval_check.py` recomputes the headline values **without importing `metrics_lib` at all** — its own JSON loading, its own section parser, its own Wilson algebra, its own recall / RR / nDCG arithmetic — then asserts against the CSV.

```
ANCHOR 1 OK  layman filtered_n Recall@15 =   9/120 = 0.0750  (Wave 1: 9/120 = 0.0750)
ANCHOR 2 OK  pooled raw_15     Recall@15 = 327/617 = 0.5300  (GATE:  327/617)
checks run: 2306
PAIRED CHECK PASSED
```

Both externally established anchors reproduced **exactly**. All 2,306 comparisons pass: every Recall@k / MRR@k / nDCG@k cell in both rank conventions, across 5 query sets × 3 stages × 5 values of k, plus the two structural invariants and the cited/grounded emptiness check.

---

## Routing analysis

Output file: `results/routing_confusion.csv`
Regenerate with: `./venv/Scripts/python.exe experiments/exp02_routing.py`
Verify with: `./venv/Scripts/python.exe experiments/check02_routing_check.py`
Owner: Wave 2 Subagent 2

---

### 1. ELI5 — what does this measure?

The corpus is four law books:

| Book | What it is |
|---|---|
| **IPC** | Indian Penal Code 1860 — the old list of crimes and punishments |
| **BNS** | Bharatiya Nyaya Sanhita 2023 — the new list, replaced the IPC on 1 July 2024 |
| **CrPC** | Code of Criminal Procedure 1973 — the old *procedure* book: arrest, bail, FIR |
| **CPA** | Consumer Protection Act 2019 — refunds, defective goods, complaints |

When someone types a question, the system picks passages out of these four books
and hands them to the language model. **This experiment asks: does it pick from
the right book?**

Three plain-English questions:

**(a)** If the right answer lives in the IPC, does the system read the IPC?
A **confusion matrix** is just a table that answers this. Rows = the book that
*should* have been read. Columns = the book that *was* read. The diagonal
(IPC→IPC, BNS→BNS, …) is where it got it right. Everything off the diagonal is a
mistake, and the table shows you *which* mistake.

**(b)** When the question literally says the word "IPC", does it go to the IPC?

**(c)** This is the important one. Suppose I told you the system reads the CrPC
70% of the time and you thought "wow, it is obsessed with the CrPC". Before you
believe that, you have to ask: **how much of the library is CrPC in the first
place?** If 39% of all the pages in the library are CrPC pages, then picking
CrPC 39% of the time is not obsession — it is just what randomly grabbing pages
would give you. That 39% is called the **base rate**: the share you would get by
pure chance.

Divide the two and you get the **over-representation ratio**:

```
                          how often it actually read CrPC
over-representation  =  ---------------------------------
                          how much of the library is CrPC
```

- **1.0** = exactly chance. Nothing to explain.
- **1.8** = it read CrPC almost twice as often as its share of the shelf.
- **0.5** = it read that book only half as often as its share.

Without this control, "70% CrPC" is an unfalsifiable claim. With it, the claim
becomes testable — and it can fail.

A **confidence interval** is the honesty margin. "1.80x [1.47, 2.04]" means: the
best estimate is 1.80, and if we re-ran this with a fresh sample of similar
questions, we would expect the answer to land between 1.47 and 2.04 about 95
times out of 100. Since 1.47 is still above 1.00, the over-representation is not
a fluke of which questions we happened to pick.

A **cluster** is a group of answers that are not really independent. The layman
set is **30 real-life situations × 4 date phrasings** = 120 queries. The four
phrasings of "my landlord kept my deposit" are the *same situation* asked four
ways — they will mostly retrieve the same passages, so they are not four
independent pieces of evidence, they are closer to one. Treating them as four
makes the confidence interval look narrower than the data deserves. The
**clustered** interval resamples whole *situations* instead of individual
queries, which is the honest version. Both are reported side by side below so
the difference is visible.

---

### 2. Technically

**Two filters exist and are never conflated in this analysis.**

| Filter | When | What it does | Logged as |
|---|---|---|---|
| **CORPUS filter** | *before* Qdrant search | restricts the search to one statute | `retrieval.filter_applied` |
| **ADAPTIVE SCORE filter** | *after* retrieval | drops chunks below `max(top_score − 0.15, 0.35)` | the `raw_15` → `filtered_n` step |

`experiments/stages.jsonl` replays the **recorded** corpus filter, so all three
of its stages are already corpus-restricted. On the layman set this hardly
matters: 116 of 120 rows recorded `filter_applied = None`, and the 4 that fired
were all CPA. A sensitivity run dropping those 4 is reported in §3.

**Three stages, and the stage is always stated.**

| Stage | Meaning | Layman chunks |
|---|---|---|
| `raw_15` | what Qdrant returned, score order | 1,800 (= 120 × 15) |
| `reranked_15` | the same 15, reordered by entity match | 1,800 |
| `filtered_n` | survivors of the adaptive score filter, what the model read | 608 |

**Definition of "which book the system went to": the DOMINANT corpus** — the
book supplying the most chunks at that stage.

*Why dominance and not the top-1 chunk.* The single top-scoring hit is one
embedding coin-flip; it is not what the model reads. The answer prompt is built
from the whole retrieved set, so the book that supplies most of that set is the
book that actually shapes the answer. Dominance is also more stable: it takes
eight chunks changing to flip it, versus one.

*Ties.* When two books supply an equal number of chunks the tie is broken by the
highest-scoring chunk among the tied books. The number of ties is written to the
CSV (`confusion_ties_broken_by_top_score`) so the rule can be audited rather
than trusted.

**Index share source: Qdrant, read-only scroll of the `legal_mvp` collection,
1,899 points.** *Not* derived from `stages.jsonl`, because `stages.jsonl`
contains only chunks that were *retrieved* — using it as the chance baseline
would compare retrieval against itself and drive every ratio toward 1.0 by
construction. The index is a **census**, not a sample, so its shares carry no
sampling error; all the uncertainty in the ratio comes from the retrieval side,
and the denominator is held fixed in the bootstrap.

**Intervals.** Wilson intervals (`wilson()`) for proportions; percentile
bootstrap with `N_BOOT = 10000`, `SEED = 20260901` (`cluster_bootstrap()`) for
shares and ratios. "Naive" resamples individual queries; "clustered" resamples
whole `pair_id` situations. Every statistic is imported from
`experiments/metrics_lib.py`; nothing is reimplemented.

---

### 3. What the number came out as

#### (a) 4×4 routing confusion, layman set, stage `raw_15` (primary)

Rows = book the gold answer lives in. Columns = dominant book actually retrieved.
Diagonal in **bold**.

| gold ↓ / went to → | IPC | BNS | CrPC | CPA | row n |
|---|---|---|---|---|---|
| **IPC** | **3** | 2 | 17 | 1 | 23 |
| **BNS** | 3 | **1** | 18 | 1 | 23 |
| **CrPC** | 0 | 0 | **5** | 0 | 5 |
| **CPA** | 0 | 0 | 0 | **8** | 8 |

Per-row accuracy (diagonal ÷ row total), `raw_15`:

| gold book | correct | accuracy | naive 95% | clustered 95% |
|---|---|---|---|---|
| IPC | 3/23 | 13.0% | [4.5, 32.1] | [0.0, 26.1] |
| BNS | 1/23 | 4.3% | [0.8, 21.0] | [0.0, 13.0] |
| CrPC | 5/5 | 100.0% | [56.6, 100.0] | [100.0, 100.0] |
| CPA | 8/8 | 100.0% | [67.6, 100.0] | [100.0, 100.0] |

**The dominant failure mode is a single cell pair: 17 of 23 IPC questions and 18
of 23 BNS questions were answered predominantly out of the CrPC.** A question
about *what crime was committed* is being answered from the *procedure* book.
CrPC and CPA score 100% but on tiny n (5 and 8) — their intervals are wide
([56.6, 100.0] and [67.6, 100.0]) and carry no weight. Worth stating precisely:
all 8 CPA-gold rows recorded `filter_applied = None`, so that 8/8 is genuinely
the retriever, not the corpus filter. (The 4 layman rows where the CPA corpus
filter *did* fire have gold IPC 1, BNS 1, EITHER 2 — it fired on the wrong
queries, and all 4 are the *same situation*, `pair_id = L024`: a builder who took
18 lakh and abandoned the site, where the gold answer is criminal cheating. The
router's `act_map_single` path locked all four phrasings of that one situation to
the Consumer Protection Act. One clustered mistake, counted four times if you
forget to cluster.)

#### Same matrix at `filtered_n` — does the picture change?

| gold ↓ / went to → | IPC | BNS | CrPC | CPA | row n |
|---|---|---|---|---|---|
| **IPC** | **3** | 3 | 16 | 1 | 23 |
| **BNS** | 4 | **4** | 14 | 1 | 23 |
| **CrPC** | 0 | 0 | **5** | 0 | 5 |
| **CPA** | 0 | 0 | 0 | **8** | 8 |

**The picture does not change qualitatively.** BNS accuracy rises 4.3% → 17.4%
(1/23 → 4/23) and IPC is unchanged at 13.0%. CrPC still takes 16 + 14 = 30 of
the 46 substantive-law queries. The two stages agree on the dominant book for
**93 of 120 queries (77.5%)** — so the stage label matters for the exact cell
counts and must always be stated, but not for the conclusion.

#### Rows the 4×4 cannot hold (in the CSV as `confusionSUPP_*`)

| gold | n | why it is not a matrix row | where it went (`raw_15`) |
|---|---|---|---|
| `EITHER` | 56 | no date stated, so IPC *or* BNS is acceptable — there is no single correct column | IPC 6, BNS 2, **CrPC 46**, CPA 2 |
| `BNSS` | 5 | **BNSS is not in the 1,899-chunk index at all** — unroutable by construction | CrPC 5 |

The `EITHER` rows reproduce the same pattern even more starkly: 46 of 56 went to
the CrPC. The 5 `BNSS` rows landing in the CrPC is arguably the *least* wrong
available answer (BNSS is the successor to the CrPC), but the corpus cannot
supply the governing text at all.

#### (b) 2×2 IPC/BNS, paired recodification set — **CORPUS FILTER AS RECORDED**

> **Read this before the table.** These are **not** a reproduction of
> `scripts/ablate_filter.py`. That script *disables* the corpus filter and asks
> whether the embeddings alone can tell the two codes apart, getting IPC 32/1 =
> 97.0% [84.7, 99.5] and BNS 16/17 = 51.5% [35.2, 67.5]. The figures below come
> from the **logged runs with the corpus filter exactly as it fired**, and they
> answer a **different question**. They are labelled `filter_as_recorded`
> throughout the CSV.

Filter as recorded on these 66 queries: `ipc_numbered` → filter `IPC` (33),
`bns_numbered` → filter `BNS` (33). Zero unfiltered.

| gold ↓ / went to → | IPC | BNS | CrPC | CPA | accuracy | naive 95% | clustered 95% |
|---|---|---|---|---|---|---|---|
| **IPC-named** | **33** | 0 | 0 | 0 | 33/33 = 100.0% | [89.6, 100.0] | [100.0, 100.0] |
| **BNS-named** | 0 | **33** | 0 | 0 | 33/33 = 100.0% | [89.6, 100.0] | [100.0, 100.0] |

Identical at `raw_15` and `filtered_n`.

**This perfect diagonal is not a retrieval result.** The router read the Act name
out of the query string and applied a hard Qdrant filter, so an IPC-named query
*could not* have returned a BNS chunk. The matrix measures a keyword lookup; the
diagonal was guaranteed before a single embedding was compared. Its only
legitimate use in the paper is as the *contrast* that makes the filter-off
ablation meaningful — 100% → 51.5% for BNS-named queries is the size of the
crutch.

#### (c) THE BASE-RATE CONTROL

Index shares (Qdrant census, 1,899 points):

| Book | chunks | index share |
|---|---|---|
| CrPC | 742 | 39.07% |
| IPC | 595 | 31.33% |
| BNS | 424 | 22.33% |
| CPA | 138 | 7.27% |

**Stage `filtered_n` — the stage the previously recorded 70.4% figure was
measured at** (120 queries, 608 chunks):

| Book | index share | retrieval share | **ratio** | naive 95% | clustered 95% |
|---|---|---|---|---|---|
| **CrPC** | 39.07% | **70.23%** | **1.80×** | [1.65, 1.93] | **[1.47, 2.04]** |
| IPC | 31.33% | 14.97% | 0.48× | [0.37, 0.59] | [0.29, 0.71] |
| BNS | 22.33% | 7.57% | 0.34× | [0.25, 0.44] | [0.18, 0.55] |
| CPA | 7.27% | 7.24% | 1.00× | [0.57, 1.54] | [0.24, 2.20] |

**Stage `raw_15` — primary, pre-adaptive-filter** (120 queries, 1,800 chunks):

| Book | index share | retrieval share | **ratio** | naive 95% | clustered 95% |
|---|---|---|---|---|---|
| **CrPC** | 39.07% | **58.22%** | **1.49×** | [1.36, 1.62] | **[1.22, 1.75]** |
| IPC | 31.33% | 18.50% | 0.59× | [0.51, 0.68] | [0.43, 0.76] |
| BNS | 22.33% | 13.00% | 0.58× | [0.47, 0.69] | [0.37, 0.81] |
| CPA | 7.27% | 10.28% | 1.41× | [0.82, 2.09] | [0.31, 2.82] |

`reranked_15` is **identical to `raw_15` to four decimals** on every book — the
entity reranker reorders the 15 but never changes which 15, so it cannot move a
corpus share.

Sensitivity — dropping the 4 layman rows whose corpus filter fired (116 rows,
`filter_applied = None` only):

| Stage | CrPC ratio | clustered 95% |
|---|---|---|
| `raw_15` | 1.54× | [1.28, 1.79] |
| `filtered_n` | 1.83× | [1.52, 2.06] |

The control does not depend on those 4 rows.

**Worked example, with the real numbers, so the arithmetic is checkable by hand:**

```
Stage filtered_n, layman set.
  Total chunks the model actually read across 120 queries : 608
  Of those, chunks from the CrPC                          : 427
  Retrieval share  = 427 / 608                            = 0.7023  (70.23%)

  CrPC points in the Qdrant index                         : 742
  Total points in the index                               : 1899
  Index share (the base rate) = 742 / 1899                = 0.3907  (39.07%)

  Over-representation ratio = 0.7023 / 0.3907             = 1.797x
```

So: the CrPC occupies **39%** of the shelf and supplied **70%** of what the model
read — **1.80 times its fair share.** The clustered interval [1.47, 2.04] does
not contain 1.00, so this is not chance.

---

### 4. How to read it

**Read a confusion-matrix row left to right.** Row "IPC", `raw_15`, reads
3 · 2 · 17 · 1: of the 23 layman queries whose answer is in the IPC, 3 went to
the IPC, 2 to the BNS, **17 to the CrPC**, 1 to the CPA. Row totals are the
number of queries with that gold book; column totals tell you which book is
absorbing traffic.

**Never quote a share without its stage.** 58.2% (`raw_15`) and 70.2%
(`filtered_n`) are the *same measurement of the same queries* at two points in
the pipeline. Quoting one as if it were the other is exactly the error that
`metrics_lib.py` warns about in its header, and it is what happened to the
earlier "70.4%" figure — it was a `filtered_n` number reported without the
label.

**Read a ratio against 1.0, and read its interval against 1.0.**

| If the interval… | then… |
|---|---|
| lies entirely above 1.0 | over-represented beyond chance — a real effect |
| lies entirely below 1.0 | under-represented beyond chance |
| straddles 1.0 | indistinguishable from chance — **claim nothing** |

CPA at `filtered_n` is 1.00× [0.24, 2.20]. That interval straddles 1.0 and is
enormous, because only 8 layman situations are consumer matters. **CPA is not
evidence of anything and must not be reported as "correctly proportioned".**

**Read the naive and clustered intervals together.** The clustered one is always
the wider and always the one to quote. For CrPC at `filtered_n` the naive
interval is [1.65, 1.93] and the clustered is [1.47, 2.04] — about 60% wider.
Quoting the naive interval would overstate precision by claiming 120 independent
observations where there are really 30.

Where the two coincide (e.g. the per-row accuracies in the 4×4), the reason is
mechanical, not lucky: only one of the four date variants of each situation has
gold book "IPC", so within that row each situation contributes exactly one row
and there is nothing to cluster.

**Do not read the (b) table as a retrieval result at all.** See the warning box.

---

### 5. What this means for the paper

**Does the base-rate control survive the Wave 1 fixes? Yes — at the stage it was
originally measured, essentially unmoved.**

| | Previously recorded | Recomputed here | Δ |
|---|---|---|---|
| CrPC layman retrieval share | 70.4% | **70.23%** (`filtered_n`) | −0.17 pp |
| CrPC index base rate | 39.1% | **39.07%** (742/1899) | −0.03 pp |
| Over-representation ratio | 1.8× | **1.80×** | none |
| 95% CI | not reported | **[1.47, 2.04]** clustered | new |

The claim is now falsifiable *and* it survived: the clustered interval excludes
1.0 with room to spare, and the sensitivity run without the 4 corpus-filtered
rows gives 1.83× [1.52, 2.06].

**But the paper must now report a stage, and it must report both.** The 1.80×
figure is a `filtered_n` number. At `raw_15` — before the adaptive score filter
— the same queries give **1.49× [1.22, 1.75]**. Both exceed chance, so the
direction of the claim is unaffected, but the magnitudes differ by a third and
they are not interchangeable. The honest sentence is:

> On plain-language queries the CrPC supplied 58.2% of raw retrieved chunks
> against a 39.1% index base rate (1.49×, 95% CI [1.22, 1.75] clustered on 30
> situations), rising to 70.2% (1.80×, [1.47, 2.04]) among the chunks that
> survive the adaptive score filter and reach the model.

**The adaptive score filter makes the skew worse, and that is a finding in its
own right.** Going from `raw_15` to `filtered_n`, CrPC rises 1.49× → 1.80×,
while IPC falls 0.59× → 0.48× and BNS falls 0.58× → 0.34×. The filter keeps
chunks within 0.15 of the top score; because the CrPC chunks tend to *be* the
top scorers on these queries, the filter preferentially deletes the substantive-
law chunks. **A mechanism intended to remove noise is amplifying a corpus bias.**
The BNS is hit hardest — it ends up at barely a third of its fair share of what
the model actually reads.

**The headline framing for the layman set.** Of 46 layman queries whose gold
answer is substantive criminal law (23 IPC + 23 BNS), **35 at `raw_15` (30 at
`filtered_n`) were answered predominantly out of the procedure code.** Diagonal
accuracy is 13.0% for IPC and 4.3% for BNS. This is the paper's central
negative result about plain-language legal retrieval, and it is now stated as a
matrix with a chance baseline rather than as an unanchored percentage.

**The `EITHER` and `BNSS` rows are a coverage story, not a routing story.** 56 of
120 layman queries state no date, so no single correct book exists — the system
cannot be scored, and 46 of those 56 went to the CrPC anyway. A further 5 expect
the BNSS, which is **absent from the index entirely**. Together that is 61 of 120
plain-language queries the corpus is structurally unable to answer correctly.
That belongs in the limitations section as a corpus-coverage claim.

**On (b): report it only as the contrast.** 33/33 and 33/33 with the corpus
filter on is a keyword lookup, not evidence about embeddings. Its value is that
it sets up `ablate_filter.py`'s 51.5% for BNS-named queries: turning the filter
off costs nearly half the BNS routing accuracy, which quantifies exactly how
much of the system's apparent statute-discrimination is the router's regex and
how much is the retriever.

---

### 6. What broke while computing this

**A one-chunk disagreement between the replay and the original logs — found,
traced, and it does not move the result.**

`check02_routing_check.py` re-derives the CrPC layman share from a source
`exp02` never touches: `runs/*/queries.jsonl`, field
`retrieval.chunks[*].corpus`. The two routes agreed on total chunk count (608 vs
608), on per-query chunk counts (0 mismatches in 120), and exactly on IPC and
BNS — but differed by **one chunk** on CrPC and CPA:

| Book | `stages.jsonl` | original logs | Δ |
|---|---|---|---|
| IPC | 0.1497 | 0.1497 | 0.0000 |
| BNS | 0.0757 | 0.0757 | 0.0000 |
| CrPC | 0.7023 | 0.7039 | −0.0016 |
| CPA | 0.0724 | 0.0707 | +0.0016 |

Traced to a single query, `L0089` (`no_date` variant, `filter_applied = None`):

```
replay  : CPA 0.259167, CPA 0.257375, CPA  0.248857
original: CPA 0.259176, CPA 0.257364, CRPC 0.249097
```

The two runs' cosine scores differ in the **fifth decimal place** — ordinary
floating-point non-determinism in the embedding/search path. Both runs kept only
3 chunks (the "≥3 forced through" rule), and the third slot was a near-tie
between a CPA chunk at 0.2489 and a CrPC chunk at 0.2491. The jitter flipped it.

Effect on the headline: 1.7974× vs 1.8016×, a difference of 0.004×, against a
clustered interval half-width of about 0.28×. The assertion tolerance is 0.005
on a share and 0.02 on the ratio; both passed. **Reported rather than smoothed
over, because "the replay is byte-identical to the logs" would have been a false
claim.**

**Nothing else broke.** No metric was missing from `metrics_lib.py`. No API
calls were made. Qdrant was read only via `scroll(..., with_vectors=False)`.

---

### 7. What I could not compute, and why

| Not computed | Why |
|---|---|
| A confusion row for the 56 `EITHER` layman queries | No date is stated, so IPC *and* BNS are both correct. A confusion matrix needs exactly one correct column per row. Reported as `confusionSUPP_*` rows with the counts, but no accuracy figure and no interval. |
| A confusion row for the 5 `BNSS` layman queries | **BNSS is not in the 1,899-chunk index.** Every one of these is unroutable by construction — there is no column that could be correct. Counts reported, accuracy is undefined, not zero. |
| An independent check of the `raw_15` stage | The original server logs stored **only post-adaptive-filter survivors** (`SCHEMA.md` §4b: `len(chunks) < len(scores_raw)` on 467 of 859 rows). There is no second source for the pre-filter 15. `stages.jsonl` is the sole source and its `raw_15` numbers rest on the replay being faithful — which §6 establishes only at `filtered_n`. |
| A filter-**off** condition on the layman set | Would require fresh embedding calls. **Zero API calls** was a hard constraint. It matters less here than elsewhere: 116 of 120 layman rows already recorded `filter_applied = None`, so the layman set is already close to unfiltered, and the sensitivity run confirms the 4 filtered rows change nothing. |
| A statistical test that the CrPC ratio *changed* between `raw_15` and `filtered_n` | The two stages are nested measurements of the same 120 queries and the correct instrument is a paired bootstrap on the difference. `metrics_lib` exposes `paired_bootstrap_auroc_diff`, which is specific to AUROC and does not apply to a share difference. Rather than reimplement a metric — explicitly forbidden — the two intervals are reported separately and no claim of a *significant* difference is made. **NOT MEASURED.** |
| Per-row confusion accuracy for CrPC and CPA with usable precision | n = 5 and n = 8. Both read 100%, and their intervals ([56.6, 100.0] and [67.6, 100.0]) are too wide to support any claim. The numbers are in the CSV; they should not carry a sentence in the paper. |

---

### 8. What surprised me

**1. The 70.4% and the 58.2% are the same measurement.** I expected to either
confirm or refute a single number. Instead the previously recorded figure turned
out to be a `filtered_n` number quoted without its stage, and the pre-filter
value on the identical queries is 58.2%. Nothing was *wrong* — 1.80× reproduced
to two decimals — but the claim was underspecified in a way that could have
been read as a 12-point discrepancy by anyone recomputing it at the other stage.
This is the exact failure mode `metrics_lib.py`'s header warns about, met in the
wild within an hour of looking.

**2. The adaptive score filter is a bias amplifier, not a bias-neutral cleanup.**
I assumed a score threshold would be roughly corpus-agnostic — it looks only at
scores. It is not: CrPC goes 1.49× → 1.80× while BNS goes 0.58× → 0.34×. The
filter strips out precisely the substantive-law chunks. That is a mechanism
finding nobody was looking for, and it makes the pipeline's *last* retrieval
step complicit in the *first* step's failure.

**3. The BNS row is worse than the IPC row.** IPC 3/23, BNS 1/23 at `raw_15`.
The BNS is the **currently governing** criminal code — the one a user in 2026
actually needs — and it is the book the system finds least often. It has the
second-smallest index share (22.3%) and the worst ratio at `filtered_n` (0.34×).
A system that answers today's criminal-law questions out of a 1973 procedure
manual is failing in the most legally consequential direction available.

**4. The paired set's perfect diagonal is genuinely 33/33 — and genuinely
worthless as retrieval evidence.** I half-expected the corpus filter to leak
somewhere. It does not: zero off-diagonal, both stages, all 66 queries. Seeing a
completely clean 2×2 and having to write "this proves nothing about the
retriever" was a useful lesson in how a good-looking table can be an artefact of
the experimental design rather than a property of the system.

**5. Non-determinism is real at the fifth decimal, and the "≥3 forced through"
rule is where it becomes visible.** One chunk in 608 flipped between two runs of
the same query against the same index. It was harmless here, but it means any
future metric that depends on the exact identity of the marginal chunk — a
precision@3, say — carries a small irreducible jitter that has to be disclosed.

---

## Calibration

Output file: `results/calibration.csv`, `results/reliability_diagram.png`
Regenerate with: `./venv/Scripts/python.exe experiments/exp03_calibration.py`
Verify with: `./venv/Scripts/python.exe experiments/check03_calibration_check.py`
Owner: Wave 2 Subagent 3

---

### 1. ELI5 — what does this measure?

Imagine a weather app. Look at every day it said **"70% chance of rain."** If it rained on
about 70 of every 100 such days, the app is **calibrated** — its numbers mean what they say.
If it rained on only 40 of them, the app is **overconfident**: it claims more certainty than
it earns.

**Calibration** is exactly that comparison, for this system. Every answer this system produces
carries a confidence number. Collect all the queries where it said roughly 0.79, and ask: how
often was it actually right?

That is what the picture in `results/reliability_diagram.png` shows. It is called a
**reliability diagram**:

- the **x-axis** is what the system claimed ("claimed confidence")
- the **y-axis** is how often it was actually right ("observed accuracy")
- the **dashed diagonal** is where a perfectly honest system would sit — claim 0.7, be right 70% of the time
- **above the diagonal** = underconfident (better than it says)
- **below the diagonal** = overconfident (worse than it says) — the dangerous direction for legal advice

Two summary numbers compress that picture:

- **ECE (Expected Calibration Error)** — the average size of the vertical gap between the
  curve and the diagonal. 0.00 = perfect. **0.24 means the confidence number is off by about
  24 percentage points on average.**
- **Brier score** — the average squared error between the number and the outcome (outcome is
  1 if right, 0 if wrong). Lower is better. It punishes being confidently wrong harder than
  being unsure.

And two numbers about *using* confidence to decide when to shut up:

- **Coverage** — the fraction of questions the system chooses to answer.
- **Risk** — the error rate among only the ones it chose to answer.
- **Risk-coverage curve** — answer only your most confident queries first, then loosen. Plot
  risk against coverage. **AURC** is the area under that curve; lower is better.
- **"Coverage at 10% risk"** — the largest share of questions you can answer while keeping
  your error rate at or below 10%.

Finally, **Platt scaling**: a small repair. Fit a two-parameter S-curve (a logistic) that maps
the raw score onto a genuine 0–1 probability. Fitted on 60% of the data, tested on the other
40% — a **stratified split**, meaning the positives and negatives are each divided 60/40
separately so both halves have the same proportion of correct answers.

**⚠ The catch, stated up front because it is the whole point.**
This system's `composite` score is

```
composite = 0.55 * top_k_mean + 0.15 * score_gap + 0.30 * entity_coverage
```

It is a weighted blend of **cosine similarities** and a coverage ratio. Nothing in that formula
estimates a probability. So when ECE says "off by 0.24", the score is not breaking a promise —
**it never made the promise.** Section 4 and section 5 explain how to say that honestly without
using it as an excuse.

---

### 2. Technically

**Sample.** n = 617 gold-labelled queries from `load_logs()` (621 rows, 4 without gold
sections), already deduplicated by the loader on `(query_id, intervention)`. These 617 rows
cover **177 distinct `pair_id` clusters** — the same underlying legal situation appears under
several phrasings and under two date conditions, so the rows are *not* independent.

**Two scores compared, so the blend can be judged against a baseline.**

| Score | What it is |
|---|---|
| `composite` | the deployed blend, `0.55·top_k_mean + 0.15·score_gap + 0.30·entity_coverage` |
| `max_score` | the raw top cosine similarity from Qdrant — the simplest possible baseline |

**Three correctness definitions, all from `metrics_lib.correctness_label()`.**

| Definition | Stage | Positives / 617 | Base rate |
|---|---|---|---|
| `retrieved@k`, k=15 | `raw_15` | 327 | 0.5300 |
| `cited` | answer | **533** | 0.8639 |
| `grounded` | answer | 27 | 0.0438 |

> **⚠ DISCREPANCY, REPORTED NOT SILENCED.** The Wave-2 task brief states the gate established
> **538** positives under `cited`. Running `metrics_lib.correctness_label(row, "cited")` over
> the 617 rows today gives **533**. Lenient sub-section matching gives 587, so 538 is neither
> the strict nor the lenient value. Every `cited` number in this file uses the library's 533
> and inherits the difference. This must be reconciled before the paper quotes either. It is
> a 5-row difference (0.8%) and does not change any conclusion here, but it is exactly the
> kind of drift that produced defect E2.

**Binning: QUANTILE (equal-mass), 10 bins.** Each bin holds ~62 queries. This is deliberate:
the scores live in roughly 0.35–0.87, so equal-width bins over [0,1] would leave most bins
empty and one bin holding almost everything, and ECE would be dominated by a single bin's
sampling noise. Equal-mass binning is stated in the figure caption and in every `notes` field.

**Bootstrap.** 95% percentile bootstrap, `N_BOOT = 10000`, `SEED = 20260901`, using
`metrics_lib.cluster_bootstrap()` in two modes:

- `ci_lo` / `ci_hi` — a unique-per-row cluster id, which makes it the ordinary **iid row**
  bootstrap.
- `cluster_ci_lo` / `cluster_ci_hi` — resampling **`pair_id`**, i.e. resampling *situations*
  rather than *phrasings*. **Quote this one.** Treating three phrasings of one situation as
  three independent observations reports an interval narrower than the data supports.

**Platt.** 60/40 stratified split (train 370, test 247), fitted with
`metrics_lib.platt_scale()` (scipy BFGS on the logistic negative log-likelihood; scikit-learn
is deliberately absent from this venv). **ECE before and after is reported on the TEST half
only.** Reporting post-scaling ECE on the training data would be circular — the fit minimises
exactly the miscalibration you would then report.

**Not touched.** The 55/15/30 weights and the 0.55/0.38 tier thresholds are read only. They
were fixed in February 2026, before a single retrieval score had been logged, which is why
these numbers measure the system rather than the result of tuning on the evaluation set.
Nothing here writes to any production path, and no API call was made.

---

### 3. What the number came out as

**ECE — lower is better; 0.00 is perfect.** n = 617.

| Score | Definition | Stage | ECE | 95% CI (clustered by `pair_id`) | 95% CI (iid rows) |
|---|---|---|---|---|---|
| `composite` | retrieved@15 | `raw_15` | **0.2410** | [0.1983, 0.2737] | [0.2016, 0.2695] |
| `composite` | cited | answer | 0.2697 | [0.2361, 0.3025] | [0.2421, 0.2973] |
| `composite` | grounded | answer | 0.5504 | [0.5242, 0.5750] | [0.5305, 0.5694] |
| `max_score` | retrieved@15 | `raw_15` | **0.1270** | [0.0991, 0.1724] | [0.1065, 0.1681] |
| `max_score` | cited | answer | 0.2309 | [0.1981, 0.2621] | [0.2041, 0.2567] |
| `max_score` | grounded | answer | 0.5892 | [0.5587, 0.6187] | [0.5692, 0.6082] |

**Brier — lower is better.** n = 617.

| Score | Definition | Brier | 95% CI (clustered) |
|---|---|---|---|
| `composite` | retrieved@15 | 0.2326 | [0.2207, 0.2441] |
| `composite` | cited | 0.1977 | [0.1862, 0.2091] |
| `composite` | grounded | 0.3622 | [0.3439, 0.3803] |
| `max_score` | retrieved@15 | 0.2113 | [0.1966, 0.2264] |
| `max_score` | cited | 0.1632 | [0.1466, 0.1801] |
| `max_score` | grounded | 0.4081 | [0.3813, 0.4338] |

**Risk-coverage.** `risk@full coverage` = the error rate if you answer everything = 1 − base
rate. It is the number selective prediction has to beat.

| Score | Definition | AURC ↓ | Coverage at 10% risk | risk @ full coverage |
|---|---|---|---|---|
| `composite` | retrieved@15 | 0.3980 | **0.0000** | 0.4700 |
| `composite` | cited | 0.1120 | 0.6483 (400 queries, threshold 0.4819) | 0.1361 |
| `composite` | grounded | 0.9610 | **0.0000** | 0.9562 |
| `max_score` | retrieved@15 | 0.2705 | 0.0486 (30 queries, threshold 0.8102) | 0.4700 |
| `max_score` | cited | 0.0868 | **0.8768** (541 queries, threshold 0.3619) | 0.1361 |
| `max_score` | grounded | 0.9474 | **0.0000** | 0.9562 |

**`0.0000` is a real measured value, not a missing one.** For `composite` at `retrieved@15`
there is *no* confidence threshold, however strict, at which the system can answer even one
query while keeping retrieval failure at or below 10%. The lowest risk anywhere on that curve
is 0.2685, reached at 59.2% coverage.

**Platt scaling — ECE on the TEST half only (n = 247; train n = 370).**

| Score | Definition | ECE before | ECE after | Change | Fitted probability range on test |
|---|---|---|---|---|---|
| `composite` | retrieved@15 | 0.2198 | 0.2014 | −0.018 | 0.253 – 0.783 |
| `composite` | cited | 0.2752 | 0.0746 | −0.201 | 0.798 – 0.912 ⚠ |
| `composite` | grounded | 0.5496 | 0.0375 | −0.512 | 0.037 – 0.049 ⚠⚠ |
| `max_score` | retrieved@15 | 0.1233 | 0.0760 | −0.047 | 0.051 – 0.869 |
| `max_score` | cited | 0.2272 | 0.0639 | −0.163 | 0.573 – 0.961 |
| `max_score` | grounded | 0.5851 | 0.0157 | −0.569 | 0.009 – 0.088 ⚠⚠ |

The ⚠ marks are section 4's most important paragraph. **Do not quote the `grounded` row as a
success.**

**Supplementary — ECE by query set** (no CI computed; in the CSV with
`query_set != "ALL"`):

| Query set | Score | retrieved@15 | cited | grounded |
|---|---|---|---|---|
| generated_retrieval | composite | 0.3279 | 0.3871 | 0.4462 |
| generated_retrieval | max_score | 0.2322 | 0.2850 | 0.5484 |
| layman_situation | composite | 0.3139 | 0.1694 | 0.4639 |
| layman_situation | max_score | 0.2052 | 0.2869 | 0.3465 |
| paired_dated_conflict | composite | 0.2206 | 0.2287 | 0.6410 |
| paired_dated_conflict | max_score | 0.2245 | 0.1641 | 0.7169 |
| paired_recodification | composite | 0.2151 | 0.2615 | 0.6785 |
| paired_recodification | max_score | 0.1017 | 0.2177 | 0.7116 |

---

### 4. How to read it

#### 4a. A worked example, with the real bin table

Here is the actual reliability table for `composite` at `retrieved@15`. Read it row by row
before reading any formula.

| bin | score range | n | mean claimed score | observed accuracy | gap = claimed − observed | weight `n/617` | contribution |
|---|---|---|---|---|---|---|---|
| 0 | 0.3455 – 0.4371 | 62 | 0.4064 | 0.3548 | +0.0515 | 0.1005 | 0.0052 |
| 1 | 0.4371 – 0.4538 | 62 | 0.4460 | 0.1613 | +0.2847 | 0.1005 | 0.0286 |
| 2 | 0.4538 – 0.4714 | 62 | 0.4633 | 0.1452 | +0.3181 | 0.1005 | 0.0320 |
| 3 | 0.4714 – 0.5109 | 61 | 0.4874 | 0.2787 | +0.2087 | 0.0989 | 0.0206 |
| 4 | 0.5109 – 0.5977 | 62 | 0.5596 | 0.9516 | **−0.3920** | 0.1005 | 0.0394 |
| 5 | 0.5977 – 0.6355 | 61 | 0.6187 | **1.0000** | **−0.3813** | 0.0989 | 0.0377 |
| 6 | 0.6355 – 0.7210 | 62 | 0.6776 | 0.7903 | −0.1127 | 0.1005 | 0.0113 |
| 7 | 0.7210 – 0.7475 | 61 | 0.7356 | 0.5082 | +0.2274 | 0.0989 | 0.0225 |
| 8 | 0.7475 – 0.7698 | 62 | 0.7573 | 0.5645 | +0.1928 | 0.1005 | 0.0194 |
| 9 | 0.7698 – 0.8339 | 62 | 0.7906 | 0.5484 | +0.2422 | 0.1005 | 0.0243 |

**Take bin 9 on its own.** 62 queries where the system claimed about **0.79** confidence. It
actually found the right statutory section in the top 15 for **54.8%** of them. It said 79,
it delivered 55. That single bin is 24 percentage points overconfident.

**Now bin 5.** 61 queries claiming about **0.62** — and the gold section was in the top 15
for **every single one**. Claimed 62, delivered 100. That bin is 38 points *under*confident.

ECE is just the weighted average of the absolute gaps:

```
ECE = Σ over bins  (n_bin / n) · |accuracy_bin − mean_score_bin|
    = (62·0.0515 + 62·0.2847 + 62·0.3181 + 61·0.2087 + 62·0.3920
       + 61·0.3813 + 62·0.1127 + 61·0.2274 + 62·0.1928 + 62·0.2422) / 617
    = 148.6894 / 617
    = 0.2410
```

`check03_calibration_check.py` computes exactly this sum, by hand, from the bin table, and
asserts it equals `metrics_lib.ece()`. It does.

#### 4b. The finding that the average hides

**The `composite` curve is not monotone.** Look at the accuracy column going down: 0.35, 0.16,
0.15, 0.28, **0.95, 1.00, 0.79**, 0.51, 0.56, 0.55. It climbs to a perfect 1.00 in the middle
of the score range and then **falls back to the base rate at the top.**

A single ECE of 0.241 makes this look like "the score is about 24 points off." It is worse
than that, and differently wrong: **at the top of its own range, `composite` carries almost no
information about whether retrieval worked.** The most confident queries are no more likely to
be right than a coin weighted at the base rate (0.53).

Compare `max_score` in the row below it: 0.13, 0.21, 0.31, 0.35, 0.58, 0.56, 0.71, 0.80, 0.81,
0.84 — monotone increasing all the way. It is systematically *underconfident* (the curve sits
above the diagonal at the top), which is a far more benign failure and a far easier one to fix.

#### 4c. **What ECE on this score does and does not tell you**

**It DOES tell you:**
- How far the displayed number is from the frequency a user would infer from it. Users
  *do* read 0.79 as "probably right." Measuring that gap is legitimate and necessary,
  because the number is shown and is thresholded into HIGH / MEDIUM / LOW tiers.
- Which score is better *as a confidence signal*, since both are measured identically.
- Where the miscalibration lives (section 4b), which the single number cannot.

**It does NOT tell you:**
- **That the formula is "broken."** ECE presupposes the number is a probability estimate.
  `composite` is a weighted sum of cosine similarities. Comparing it to a probability is
  comparing two different kinds of quantity, and a large ECE is the expected result, not a
  bug report. Do not write "the confidence score is badly calibrated" as though calibration
  were ever attempted.
- **Anything about ranking quality.** ECE is invariant to nothing useful here: a score can
  have terrible ECE and perfect ranking (add 0.3 to every value), or excellent ECE and zero
  ranking ability (predict the base rate for everyone — see below). For "does high
  confidence mean more likely correct," use AUROC or the risk-coverage curve, not ECE.
- **Anything on its own about the `grounded` definition.** With a base rate of 0.0438, a
  score that lives in 0.35–0.87 has ECE ≈ 0.55 for the trivial reason that 0.55 ≈ mean score
  − base rate. That number is measuring the mismatch of *scales*, not of *information*.

#### 4d. **Does Platt scaling make it usable AS a probability? Mostly no — and the table above is a trap**

Platt scaling puts the score on the right scale. That is all it does. It is a two-parameter
monotone S-curve: it can stretch, shift and squash, but it **cannot reorder anything.** Two
queries ranked (A above B) by the raw score stay ranked (A above B) after Platt. So it adds
exactly zero discriminative information.

That matters here because of what the fitted outputs look like:

| Score | Definition | Fitted probabilities span | Test base rate | Raw AUROC (test) |
|---|---|---|---|---|
| `composite` | grounded | **0.037 – 0.049** | 0.0445 | 0.524 |
| `max_score` | grounded | 0.009 – 0.088 | 0.0445 | 0.566 |
| `composite` | cited | 0.798 – 0.912 | 0.8623 | 0.617 |
| `max_score` | cited | 0.573 – 0.961 | 0.8623 | 0.689 |
| `composite` | retrieved@15 | 0.253 – 0.783 | 0.5304 | 0.652 |
| `max_score` | retrieved@15 | 0.051 – 0.869 | 0.5304 | 0.781 |

Read the top row. Platt cut `composite`/`grounded` ECE from 0.550 to 0.037 — a 93% reduction,
the single most impressive number in this whole experiment — **by learning to output a
constant equal to the base rate.** Every query gets "about a 4% chance of being fully
grounded." That is perfectly calibrated and completely useless: it distinguishes nothing, and
it is what a model with AUROC 0.524 (0.5 = no information) *should* be forced to output.

**This is the reviewer's question, and the honest answer is:**

- For `grounded`, Platt does **not** make the score usable as a probability. It makes the
  score *honest about having nothing to say*. Report the 0.037 next to the AUROC of 0.524 or
  it will be read as a success.
- For `composite`/`cited`, the fitted range 0.798–0.912 is a 11-point band around an 86%
  base rate. Calibrated, near-constant, barely actionable.
- For `max_score`/`retrieved@15`, Platt is genuinely doing something: the fitted range spans
  0.051–0.869 and the underlying AUROC is 0.781. **This is the one cell in the table where a
  calibrated probability would be worth deploying.**
- For `composite`/`retrieved@15` — the currently deployed configuration — Platt moves ECE only
  0.220 → 0.201. It cannot fix the non-monotonicity in section 4b, because monotone maps
  cannot reorder. **The deployed score is the one Platt helps least.**

#### 4e. **What would have to be true for a calibrated score to be trustworthy in deployment**

Four conditions. None of them currently hold.

1. **The score must rank before it can be calibrated.** Calibration is a monotone
   transformation; it inherits whatever ordering it is given. `composite` at AUROC 0.663
   (retrieved@15) is weakly informative; at 0.531 (grounded) it is not informative at all.
   **Fix the ranking first, calibrate second.** Calibrating a score that cannot rank produces
   a well-behaved constant.
2. **The calibration set must resemble deployment.** These 617 queries are 4 statutory PDFs,
   1,011 chunks, 4 query sets built for this project. The per-query-set ECE table in section 3
   already shows the fit moving — `max_score`/`retrieved@15` is 0.102 on `paired_recodification`
   and 0.232 on `generated_retrieval`, a factor of 2.3 across sets drawn from the *same*
   corpus. A real user's question distribution is a further shift, and the Platt parameters
   fitted here would not transfer.
3. **The calibration must be fitted and tested on disjoint data, and re-fitted whenever the
   pipeline changes.** Done here (60/40 stratified, test-only reporting). But the Platt
   parameters are a function of the retriever, the corpus, the chunker and the prompt. Every
   pending fix in `docs/GAPS.md` — the `entity_coverage` defect, the corpus mis-tagging, the
   stale `ACT_MAP` — invalidates them. **These numbers calibrate the system as it is broken
   today.**
4. **The deployment decision must actually use it.** A calibrated probability is only
   trustworthy if it is wired to an abstention rule with a stated risk budget. The
   risk-coverage table is where that lives, and it currently says: at a 10% error budget on
   retrieval, `composite` supports **zero** coverage. A number nobody can act on cannot be
   trusted or distrusted; it is decoration.

---

### 5. What this means for the paper

**Claim 1 — the honest framing, and it must come first.**
> The system's confidence score is a weighted blend of cosine similarities, not a probability
> estimate. We nonetheless evaluate it with ECE and Brier because it is displayed to users and
> thresholded into HIGH/MEDIUM/LOW advisory tiers, so users read it as a likelihood. ECE here
> measures the gap between the number as read and the frequency it corresponds to; it does not
> imply that a probabilistic interpretation was ever intended.

Put that sentence in the paper before any calibration number. A reviewer who reaches
ECE = 0.241 without it will (correctly) object that the metric presupposes a probability.

**Claim 2 — the headline finding, and it is a negative result worth publishing.**
The engineered `composite` score is **worse than the raw cosine similarity it is built from**,
on every axis, under every definition:

| | `composite` | `max_score` | |
|---|---|---|---|
| ECE, retrieved@15 | 0.2410 | **0.1270** | max_score 47% lower |
| Brier, retrieved@15 | 0.2326 | **0.2113** | |
| AURC, retrieved@15 | 0.3980 | **0.2705** | |
| AUROC, retrieved@15 | 0.663 | **0.784** | |
| Coverage at 10% risk, cited | 0.6483 | **0.8768** | +23 points of answerable queries |

Blending in `score_gap` and `entity_coverage` **destroys** information that `max_score` already
had. This is consistent with, and independent evidence for, the `entity_coverage` defect in
`docs/GAPS.md` (chunks divided by entities; neutral default granting 0.30 free). It is a
concrete, measured cost of that bug — 12 AUROC points and 11 ECE points — rather than a
code-reading argument.

**Claim 3 — the average hides a worse shape.** Report the non-monotonicity of section 4b, not
just ECE. "Confidence above 0.72 is no more accurate than the base rate" is a stronger and more
useful statement to a practitioner than "ECE = 0.24."

**Claim 4 — report Platt with its AUROC beside it, always.** The `grounded` improvement
(0.550 → 0.037) is a degenerate constant fit and will be caught by any competent reviewer if
presented as a success. Presenting it *as* a degenerate fit, deliberately, is a genuine
contribution: it is a clean worked demonstration that ECE alone cannot detect an uninformative
model.

**Claim 5 — the methodological strength, stated explicitly.** The 55/15/30 weights and the
0.55/0.38 tier thresholds were frozen in February 2026, before any retrieval score had ever
been logged. **No hyperparameter in this confidence system was tuned on the evaluation data.**
Say this in the paper. It converts "our confidence score is poorly calibrated" from an
embarrassment into a clean, unbiased measurement — which is precisely what makes the negative
result in Claim 2 credible.

**Caveat to carry into every table.** These are pre-fix numbers, on the pipeline as it stands
today, with the defects listed in `docs/GAPS.md` present. They are a **baseline**, not a
result. Every number here carries the git SHA of the commit that produced it.

---

### 6. What broke while computing this

1. **`tee` failed on the first launch.** `./venv/Scripts/python.exe experiments/exp03_calibration.py | tee "$TMPDIR/exp03.log"` — `$TMPDIR` was unset in the Bash tool's environment, so the path became `/exp03.log` and `tee` exited with `Permission denied`. Rerun without the pipe. **Unexpected consequence:** Python did not die on the broken pipe (its stdout was buffered and never flushed until exit), so that run completed normally and wrote both output files. A second run had already been launched, so the experiment ran **twice, concurrently, three minutes apart**, and both wrote to the same two paths.
2. **That accident produced a free determinism check.** Both runs emitted byte-identical values across all 24 bootstrap intervals — for example `composite`/`retrieved@15` ECE = 0.2410 with clustered CI [0.1983, 0.2737] from both. `SEED = 20260901` is doing its job. No torn file: the writes were ~3 minutes apart and the second completed last. Recorded here because a reader inspecting file timestamps would otherwise see two writes and reasonably suspect a race.
3. **The `cited` positive count does not match the brief.** Brief says 538; `correctness_label(..., "cited")` gives **533** on the 617 gold-labelled rows today. Lenient matching gives 587, so 538 is neither. Documented in section 2, unresolved, and it needs an `OPEN_QUESTIONS.md` entry.
4. **The run is slow and it is the bootstrap, not the metric.** 24 bootstraps × 10,000 resamples ≈ 24 minutes wall clock (with four other subagents competing for cores). The cost is `cluster_bootstrap`'s index construction — `np.flatnonzero(ids == c)` once per cluster per resample. Not a defect; just budget ~25 minutes for a rerun and do not assume it has hung.
5. **A first draft wrote smoke-test artifacts into `results/`.** `results/_smoke_calibration.csv` and `results/_smoke_reliability.png` were created during a 300-resample trial run, in a directory this subagent does not own. Both were deleted; subsequent trial work went to the scratchpad. Flagged because four subagents were writing to `results/` concurrently.

**Nothing broke in the metrics themselves.** All five paired checks passed on the first run.

---

### 7. What I could not compute, and why

| Not computed | Why |
|---|---|
| Calibration at `reranked_15` or `filtered_n` | The gate established the `retrieved@k` positives at `raw_15` (327/617) and this experiment was scoped to that stage so the label counts stay comparable across Wave 2. The other two stages are available in `experiments/stages.jsonl`; recomputing there is a one-line change to `DEFS` and roughly 25 more minutes of bootstrap. Not run, so **NOT MEASURED**. |
| Bootstrap CIs on AURC and coverage-at-risk | Not requested by the task brief, and coverage-at-risk is a discontinuous step function of the data whose percentile bootstrap needs a stated justification I did not have room to give. **NOT MEASURED**, deliberately, rather than reported without one. |
| Bootstrap CIs on Platt before/after ECE | Would require re-splitting inside every resample (otherwise the interval is conditional on one arbitrary split and is too narrow). That is a nested bootstrap and roughly 10× the runtime. **NOT MEASURED.** The point estimates in section 3 have no uncertainty attached and must not be quoted as if they did. |
| Per-query-set CIs | The supplementary per-set ECE/Brier rows carry no CI — at n≈99–198 per set with only 30–80 clusters, the bootstrap would be dominated by cluster resampling noise. Reported as point estimates, labelled SUPPLEMENTARY in the CSV. |
| Whether calibration improves after the `docs/GAPS.md` fixes | Requires re-running retrieval on fixed code. Out of scope, zero API budget, and mixing pre-fix and post-fix numbers is forbidden. This whole file is a **pre-fix baseline**. |
| A recalibration that could actually be deployed | Would need conditions 1–4 of section 4e satisfied. Condition 1 fails today. Fitting one now would produce a well-calibrated constant and a false sense of progress. |

---

### 8. What surprised me

**1. The raw cosine similarity beats the engineered score. Every time.**
I expected the blend to help at least somewhere — three signals should carry more than one.
`max_score` won on ECE, Brier, AURC, AUROC and coverage-at-risk, under all three definitions
where the comparison is meaningful. The 30% `entity_coverage` term is not neutral; it is
actively destroying signal that was already there. The known defect has a measurable price:
**12 AUROC points.**

**2. The composite curve turns around.** I expected monotone overconfidence — a curve below the
diagonal, sagging further as it rises. Instead accuracy climbs to a *perfect* 1.00 at
`composite` ≈ 0.62, then **falls back to the base rate** by 0.79. The system's most confident
predictions are its least informative ones. A single ECE number conceals this completely,
which is a small lesson about ECE itself.

**3. Coverage at 10% risk is exactly zero, and I had to check it three times.**
For `composite` at `retrieved@15`, no threshold anywhere on the curve achieves 10% risk. The
brute-force route in `check03` — try every distinct score as an explicit cutoff, measure the
error rate among the answered — agrees to 1e-12. It is a real 0.0, and it means the deployed
confidence score currently cannot support *any* abstention policy at that risk budget.

**4. Platt's biggest "win" is its most worthless output.** Cutting ECE by 93% on `grounded`
looked like the best result in the experiment for about ten minutes, until I printed the fitted
range: 0.037–0.049. The scaler had learned to say "4%" to everything. That is the cleanest
demonstration I have seen of why ECE must never be reported without a discrimination metric
beside it — and it came out of this project's own data rather than a textbook.

**5. The accident that ran the experiment twice was more reassuring than annoying.** Two
independent processes, started three minutes apart, on a loaded machine, produced identical
values to every printed digit across 240,000 bootstrap resamples.

---

## Confidence ablation

Output file: `results/ablation.csv` (133 rows)
Regenerate with: `./venv/Scripts/python.exe experiments/exp04_ablation.py`
Verify with: `./venv/Scripts/python.exe experiments/check04_ablation_check.py`
Owner: Wave 2 Subagent 4
Data: `load_logs()` → 621 deduplicated rows, **617 with a gold section**. SEED = 20260901, N_BOOT = 10000.

---

### 1. ELI5 — what does this measure?

Every time the system answers a question it also prints a number between 0 and 1 called **confidence**: "how sure am I that I found the right law?" That number is a recipe. It stirs together three ingredients:

| Ingredient | Plain English | Recipe share |
|---|---|---|
| `top_k_mean` | how similar the five best-matching chunks of statute were to the question | 55% |
| the gap term | how *evenly* good those five were — did quality fall off a cliff after the first one? | 15% |
| `entity_coverage` | if the question named a section ("Section 302"), did the retrieved text actually mention it? | 30% |

An **ablation** is the cooking equivalent of removing one ingredient at a time to find out which one the dish actually needs. Nobody changes the restaurant's recipe while doing this — you cook extra portions on the side and taste them. That is exactly what this file does: the deployed recipe (55/15/30) is untouched; alternative recipes are recomputed offline from numbers that were already written down for all 617 queries. **No API calls, no re-running the system, no change to any production file.**

The question being answered is: *is this three-ingredient confidence score actually better than any one of its ingredients alone?*

The short answer, which you should brace for: **no.** The blended score is worse at telling right from wrong than the single simplest ingredient in it. One ingredient is not merely useless — it is wired in backwards, and it is actively dragging the score down.

---

### 2. Technically

#### 2.1 AUROC — the yardstick

**AUROC** (Area Under the Receiver Operating Characteristic curve) answers one question in one number:

> Pick one query the system got right and one it got wrong, at random. How often does the confidence score give the right one a higher number?

- **1.0** = always. Perfect separation.
- **0.5** = a coin flip. The score carries **no information**.
- **below 0.5** = the score is *anti*-predictive — it is confident exactly when it is wrong. A score of 0.27 is not "bad"; it is *informative with the sign flipped*. Multiply it by −1 and you get 0.73, a genuinely useful signal.

AUROC is a **rank statistic**: it only looks at the *order* the scores put the queries in, never at the actual values. This has one consequence that matters below — multiplying every score by the same positive number cannot change the AUROC, because it cannot change the order.

It comes from `metrics_lib.auroc()` (Mann–Whitney U with average ranks, so ties count as half). Nothing was reimplemented here.

#### 2.2 Bootstrap confidence intervals

We have 617 queries, not all queries that exist. A **bootstrap** asks "if I had drawn a different 617, how much would this number have moved?" by resampling the 617 rows *with replacement* 10,000 times and recomputing the AUROC each time. The 2.5th and 97.5th percentiles of those 10,000 values are the **95% confidence interval**. Two versions are reported:

- `ci_lo`/`ci_hi` — resamples **rows**.
- `cluster_ci_lo`/`cluster_ci_hi` — resamples **situations** (`pair_id`, 177 of them). Three rephrasings of one legal situation are not three independent observations, so the row bootstrap reports an interval that is narrower than the data deserves. The cluster interval is the honest one. It is computed for the headline `retrieved@k` rows.

#### 2.3 Paired comparison — why two intervals side by side is not a test

`entity_coverage` scores 0.581 [0.538, 0.623] and the composite 0.663 [0.617, 0.710]. Those intervals overlap. It is tempting to conclude "no real difference". **That reasoning is wrong**, and this is one of the easiest ways to lose a paper in review.

Both scores are measured on **the same 617 queries**. So instead of comparing two independent intervals by eye, bootstrap the **difference** directly: resample the 617 rows, recompute *both* AUROCs on the *same* resample, take the difference, repeat 10,000 times. The queries that are hard for one score are hard for the other, and the pairing cancels that shared noise out.

`paired_bootstrap_auroc_diff()` does exactly this, and here it returns a difference of **−0.0825 [−0.1056, −0.0594], p = 0.0000** — an interval nowhere near zero. The eyeball test said "maybe the same". The correct test says "definitely not". Always use the paired one.

---

### 3. What the number came out as

#### 3.0 FIRST — the deployed formula is not the formula the task brief described

The task brief (and, informally, the project notes) describe the composite as:

```
composite = 0.55*top_k_mean + 0.15*score_gap + 0.30*entity_coverage
```

**That formula does not reproduce a single one of the 617 logged confidence values.** It is off by up to 0.148, and by 0.090 on average, on 617 of 617 rows.

The formula actually in `agents/retriever.py:137–142` is:

```python
gap_penalty = min(score_gap / 0.3, 1.0)
confidence  = 0.55*top_k_mean + 0.15*(1.0 - gap_penalty) + 0.30*entity_coverage
```

The gap is **normalised and inverted** before it is used. With that transform, the reconstruction matches the logged composite to **9.0 × 10⁻⁵ on every row**, which is exactly the rounding floor you get when four quantities are each stored to four decimal places. Two independent implementations (`exp04_ablation.py` via `load_logs()`; `check04_ablation_check.py` reading `runs/*/queries.jsonl` with the `json` module and no shared code) both confirm it and both `assert` it.

**Worked example, a real row** — `req_id = 6b7aabdef03c`, the single worst-agreeing row of all 617:

| Step | Arithmetic | Value |
|---|---|---|
| logged `top_k_mean` | — | 0.4043 |
| logged `score_gap` | — | 0.0216 |
| logged `entity_coverage` | — | 0.5000 |
| gap_penalty | `min(0.0216 / 0.3, 1.0)` | 0.0720 |
| **gap_term** | `1 − 0.0720` | **0.9280** |
| term 1 | `0.55 × 0.4043` | 0.222365 |
| term 2 | `0.15 × 0.9280` | 0.139200 |
| term 3 | `0.30 × 0.5000` | 0.150000 |
| reconstructed | sum | **0.511565** |
| **logged composite** | — | **0.5115** |

Off by 0.000065 — pure 4-decimal rounding. Under the brief's formula the same row would give `0.55×0.4043 + 0.15×0.0216 + 0.30×0.5 = 0.3756`, which is 0.136 away from what the system actually logged.

**Why this matters more than a typo.** `1 − gap/0.3` means the deployed system pays out the full 0.15 when the gap is **small** — it treats "all five chunks were about equally good" as a sign of confidence (the source comment says *"small gap = consistent relevance"*). Everything below shows the data says the opposite. So the quantity that actually enters the blend is `gap_term`, and that is what parts (b) and (c) manipulate — only then does the weighting (0.55, 0.15, 0.30) reproduce the deployed composite exactly, which is the whole point of comparing against it.

#### 3.1 (a) Per-signal AUROC — does each signal carry information *on its own*?

**Definition `retrieved@k`, stage `raw_15`, k = 15, n = 617, 327 positives** — "the gold section was among the 15 chunks Qdrant returned".

| Signal | AUROC | 95% CI (rows) | 95% CI (clustered) | Paired diff vs composite | p |
|---|---|---|---|---|---|
| `max_score` | **0.7837** | [0.7470, 0.8195] | [0.7316, 0.8312] | **+0.1207** [+0.0798, +0.1623] | 0.0000 |
| `top_k_mean` | **0.7571** | [0.7188, 0.7939] | [0.7024, 0.8075] | **+0.0940** [+0.0561, +0.1324] | 0.0000 |
| `score_gap` (raw) | **0.7298** | [0.6893, 0.7684] | [0.6743, 0.7813] | **+0.0667** [+0.0128, +0.1200] | 0.0184 |
| **`composite` (deployed)** | **0.6631** | [0.6172, 0.7096] | [0.6047, 0.7212] | — | — |
| `entity_coverage` | 0.5806 | [0.5376, 0.6232] | [0.5435, 0.6183] | −0.0825 [−0.1056, −0.0594] | 0.0000 |
| `gap_term` (as deployed) | **0.2702** | [0.2316, 0.3107] | [0.2187, 0.3257] | −0.3929 [−0.4604, −0.3239] | 0.0000 |

**Read the ordering.** The deployed composite sits **below three of its own inputs**, and every one of those three gaps is significant under the paired test. Blending made the signal worse.

**Definition `cited`, n = 617, 533 positives** — "the gold section appears in the answer's citations".

| Signal | AUROC | 95% CI | Paired diff vs composite | p |
|---|---|---|---|---|
| `max_score` | 0.6895 | [0.6195, 0.7551] | +0.0984 [+0.0441, +0.1523] | 0.0006 |
| `top_k_mean` | 0.6749 | [0.6057, 0.7419] | +0.0838 [+0.0345, +0.1317] | 0.0020 |
| `score_gap` | 0.6652 | [0.5985, 0.7298] | +0.0741 [+0.0020, +0.1457] | 0.0454 |
| **`composite`** | **0.5911** | [0.5206, 0.6602] | — | — |
| `entity_coverage` | 0.5017 | [0.4460, 0.5577] | −0.0894 [−0.1262, −0.0528] | 0.0000 |
| `gap_term` | 0.3348 | [0.2702, 0.4015] | −0.2563 [−0.3680, −0.1404] | 0.0000 |

`entity_coverage` at **0.5017** is a coin flip to four decimals.

**Definition `grounded`, n = 617, only 27 positives** — "every citation in the answer was supported".

| Signal | AUROC | 95% CI | Paired diff vs composite | p |
|---|---|---|---|---|
| `top_k_mean` | 0.5930 | [0.4931, 0.6884] | +0.0621 [−0.0387, +0.1561] | 0.2190 |
| `max_score` | 0.5888 | [0.4886, 0.6864] | +0.0579 [−0.0560, +0.1687] | 0.3154 |
| `score_gap` | 0.5695 | [0.4719, 0.6670] | +0.0386 [−0.1070, +0.1826] | 0.5864 |
| **`composite`** | **0.5309** | [0.4486, 0.6075] | — | — |
| `entity_coverage` | 0.4554 | [0.3867, 0.5273] | −0.0754 [−0.1116, −0.0383] | 0.0000 |
| `gap_term` | 0.4305 | [0.3330, 0.5281] | −0.1003 [−0.2027, +0.0040] | 0.0586 |

With 27 positives every interval is wide and every interval crosses 0.5 except `entity_coverage`'s difference. **Nothing here separates grounded answers from ungrounded ones.** Report it as "no signal detected at n=27", not as a ranking.

**Per query set** (`retrieved@k`, `raw_15`, k=15) — the aggregate hides a large amount:

| Query set | n | pos | `top_k_mean` | `score_gap` | `entity_coverage` | `composite` | `max_score` |
|---|---|---|---|---|---|---|---|
| `generated_retrieval` | 198 | 137 | 0.805 | 0.755 | **0.880** | **0.873** | 0.880 |
| `paired_recodification` | 99 | 73 | 0.692 | 0.668 | **0.386** | **0.353** | 0.735 |
| `paired_dated_conflict` | 197 | 97 | 0.623 | 0.629 | 0.474 | 0.471 | 0.656 |
| `layman_situation` | 120 | 18 | 0.569 | 0.521 | **0.500** | 0.571 | 0.552 |

Three things jump out:

1. On `generated_retrieval` the composite looks excellent (0.873) — but only because those queries were built by naming a section, so `entity_coverage` is nearly a direct label leak (0.880).
2. On `paired_recodification` the composite is **0.353, well below chance** — it is confident precisely when it is wrong, driven by `entity_coverage` at 0.386. These are the IPC→BNS recodification queries: the query names an old section, the corpus holds the new one, so "the entity appears in the text" fires for the *wrong* statute.
3. On `layman_situation` — the queries this project exists for — `entity_coverage` is **exactly 0.500**, because a layman never names a section, so the signal is the constant 0.5 for all 120 rows. A constant has no ranking information by definition.

#### 3.2 (b) Leave-one-out — does *removing* a signal hurt the blend?

**This is a different question from 3.1, and the difference is the point of doing both.**

- (a) asks: *does this signal carry information on its own?*
- (b) asks: *does removing it hurt the combination?*

These can disagree in both directions. A signal can be worthless alone yet valuable in combination — it might be noise except on exactly the queries where the other signals fail, correcting them. And a signal can look informative alone yet be dead weight in combination — if it is redundant with a stronger signal already in the blend, deleting it costs nothing. **Neither result implies the other.** You need both tables.

**Leave-one-out** means: zero one weight, then **renormalise** the survivors — rescale them so they still sum to 1.0. Worked example, the one from the brief: dropping `gap_term` leaves 0.55 and 0.30, which sum to 0.85, so `0.55/0.85 = 0.647` and `0.30/0.85 = 0.353`. Applied to our real row above: `0.647 × 0.4043 + 0.353 × 0.5000 = 0.4381`.

> **An honest footnote about renormalisation.** Because AUROC is a rank statistic (§2.1), rescaling every score by the same positive constant *cannot change the AUROC at all* — the reduced composite would rank the 617 queries identically at 0.55/0.30 and at 0.647/0.353. So renormalisation contributes exactly **0.0** to every AUROC below. It is done because the brief specifies it, and because it keeps the reduced score on a 0–1 scale comparable with the deployed one — which genuinely does matter for the tier thresholds (HIGH ≥ 0.55, MEDIUM ≥ 0.38), just not for AUROC. What moves the numbers below is the **removal of the term**, never the rescaling. This is recorded in `ablation.csv` as `loo_renormalisation_effect_on_auroc = 0.0`.

**Definition `retrieved@k`** — full deployed composite AUROC **0.6631**:

| Dropped | Remaining weights | AUROC | 95% CI | Clustered CI | Paired diff vs full | p |
|---|---|---|---|---|---|---|
| `top_k_mean` | 0.000 / 0.333 / 0.667 | 0.4860 | [0.4391, 0.5334] | — | **−0.1772** [−0.2092, −0.1465] | 0.0000 |
| `gap_term` | 0.647 / 0.000 / 0.353 | **0.7047** | [0.6602, 0.7493] | — | **+0.0415** [+0.0282, +0.0555] | 0.0000 |
| `entity_coverage` | 0.786 / 0.214 / 0.000 | 0.6581 | [0.6150, 0.7010] | — | −0.0050 [−0.0498, +0.0383] | 0.8210 |

**Definition `cited`** — full composite 0.5911:

| Dropped | AUROC | Paired diff vs full | p |
|---|---|---|---|
| `top_k_mean` | 0.4346 | −0.1565 [−0.2068, −0.1069] | 0.0000 |
| `gap_term` | 0.6118 | **+0.0207** [+0.0010, +0.0403] | 0.0426 |
| `entity_coverage` | 0.6754 | **+0.0842** [+0.0328, +0.1327] | 0.0018 |

**Definition `grounded`** — full composite 0.5308 (27 positives, nothing is significant except the first row):

| Dropped | AUROC | Paired diff vs full | p |
|---|---|---|---|
| `top_k_mean` | 0.3953 | −0.1355 [−0.1869, −0.0829] | 0.0000 |
| `gap_term` | 0.5173 | −0.0135 [−0.0446, +0.0163] | 0.3662 |
| `entity_coverage` | 0.5901 | +0.0593 [−0.0249, +0.1446] | 0.1658 |

**Summary of (b):** removing `top_k_mean` collapses the score toward chance under all three definitions — it is the only ingredient carrying the dish. Removing `gap_term` **improves** the score significantly under `retrieved@k` and `cited`. Removing `entity_coverage` is neutral under `retrieved@k` and **improves** the score under `cited`.

And note the (a)/(b) divergence in action: `score_gap` looked *informative alone* (0.730) yet its deployed form is *harmful in combination* (+0.0415 from deleting it) — because what is blended is the inverted `gap_term`, not the raw gap.

#### 3.3 (c) Weight sweep — what would other recipes have scored?

**This is analysis, not tuning. The deployed weighting stays 0.55 / 0.15 / 0.30, and no production file was touched.** The sweep tries every weighting `(w1, w2, w3)` where each is a multiple of 0.05 and the three sum to 1.0 — **231 weightings**, built in exact integer units of 0.05 so no floating-point sum ever fails the `== 1.0` test. **Argmax** just means "the input that maximises the output" — here, the weighting with the highest AUROC.

| Definition | Argmax weighting (top_k_mean / gap_term / entity_coverage) | AUROC (in-sample) | Deployed 55/15/30 | Gain | Weightings within 0.005 of best |
|---|---|---|---|---|---|
| `retrieved@k` | **1.00 / 0.00 / 0.00** | 0.7571 | 0.6631 | **+0.0940** | **1 of 231** |
| `cited` | **1.00 / 0.00 / 0.00** | 0.6749 | 0.5911 | +0.0838 | 5 of 231 |
| `grounded` | **1.00 / 0.00 / 0.00** | 0.5930 | 0.5308 | +0.0622 | 5 of 231 |

**Does the argmax put any signal at or near zero? Yes — it puts BOTH other signals at exactly zero, under all three definitions.** The best of 231 weightings is the degenerate corner that throws away `gap_term` and `entity_coverage` entirely and keeps only `top_k_mean`. This is the strongest single result in this file.

And the surface is **not** flat: for `retrieved@k`, exactly **1** of 231 weightings lands within 0.005 AUROC of the winner. The peak is sharp, so the argmax is not an arbitrary pick among near-ties.

##### Overfitting, and the honest number

**Overfitting** here means: the sweep tried 231 candidates and reported the best one *on the same 617 rows it used to choose it*. Even pure noise gives one of 231 candidates a lucky high score, so the winning AUROC is **optimistically biased** — it is an upper bound, not an estimate.

The fix is a **stratified split**: cut the 617 rows into a 60% train half and a 40% test half, *separately within the positives and within the negatives* so both halves carry the same proportion of correct queries (unstratified, `grounded`'s 27 positives could land almost entirely in one half and leave AUROC undefined in the other). Choose the weighting on train; **report the AUROC on test only**, where those rows played no part in the choice.

| Definition | Train argmax (n=370) | **Test AUROC (n=247), 95% CI** | Deployed on the same test half | **Test gain** | In-sample gain |
|---|---|---|---|---|---|
| `retrieved@k` | 1.00 / 0.00 / 0.00 | **0.7436** [0.6780, 0.8027] | 0.6519 | **+0.0918** | +0.0940 |
| `cited` | 1.00 / 0.00 / 0.00 | **0.6738** [0.5653, 0.7780] | 0.6174 | **+0.0564** | +0.0838 |
| `grounded` | 0.75 / 0.25 / 0.00 | **0.5535** [0.3961, 0.7203] | 0.5239 | **+0.0297** | +0.0622 |

The test-half intervals are wide because 247 rows is not many — the point of the table is the *shrinkage of the gain*, not the precision of any single cell.

**Both numbers must be stated together, and this table is why.** For `retrieved@k` the gain barely shrinks (+0.0940 → +0.0918), so the finding survives held-out evaluation. For `cited` it shrinks by a third and for `grounded` by half — those two are partly the selection artefact. Quote the test column.

Note that under all three definitions the train half independently chose weight **0.00** for `entity_coverage`, and 0.00 for `gap_term` in two of three.

##### Secondary sweep: what if the gap were not inverted?

Because §3.0 found the gap enters the blend sign-flipped, the sweep was repeated with the **raw** `score_gap` in place of `gap_term` (in-sample, reported for contrast only):

| Definition | Argmax (top_k_mean / raw score_gap / entity_coverage) | AUROC |
|---|---|---|
| `retrieved@k` | 0.55 / 0.45 / 0.00 | **0.7850** |
| `cited` | 0.20 / 0.80 / 0.00 | 0.6925 |
| `grounded` | 0.95 / 0.05 / 0.00 | 0.5930 |

With the sign the right way round, the gap becomes the **second most valuable ingredient** (0.45 weight) and the blend reaches 0.7850 — edging past `max_score`'s 0.7837. `entity_coverage` still gets weight 0.00 under all three definitions.

#### 3.4 Provenance and data quirks

| | |
|---|---|
| `load_logs()` rows | 621 (859 before dedupe) |
| Rows with a gold section | **617** |
| Clusters (`pair_id`) | 177 |
| `entity_coverage` fell back to its neutral constant | **268 / 617 = 43.4%** |
| Distinct values of `entity_coverage` on this data | **only 0.00, 0.50, 1.00** |
| Values of `entity_coverage` above 1.0 | **0** |

`entity_coverage` is not a continuous signal on this data — it is a **three-level flag**: 0.0 (entity named, not found), 0.5 (`ENTITY_NEUTRAL`, no entity named — 43.4% of all queries), 1.0 (entity named and found). Almost every query names at most one entity, so "fraction of entities found" can only be 0 or 1.

---

### 4. How to read it

**Reading `ablation.csv`.** Twelve fixed columns. `metric` names the quantity; `notes` carries the signal name, the weighting, and the train/test role, because the schema is shared with four other subagents and columns cannot be added. The metrics you want:

| `metric` | What it is |
|---|---|
| `auroc_signal` | part (a): one signal alone. `notes` has `signal=...` |
| `auroc_diff_vs_composite` | part (a): paired difference, that signal minus the composite |
| `auroc_loo` | part (b): composite with one signal removed. `notes` has `drop=...` |
| `auroc_diff_loo_vs_full` | part (b): paired difference. **Positive means dropping the signal HELPED** |
| `auroc_sweep_argmax` | part (c): best of 231, in-sample. **Optimistically biased** |
| `auroc_sweep_argmax_test` | part (c): **the honest number** — chosen on train, measured on test |
| `sweep_argmax_weight` | the weight the argmax gives one signal. **0.0 means the sweep deleted it** |
| `composite_reconstruction_max_abs_dev` | the paired check |

**Rules for reading the numbers themselves:**

1. **Always read the `definition` column.** `retrieved@k` (327 positives) is the load-bearing one. `grounded` has 27 positives and its intervals are so wide that essentially nothing is distinguishable; do not build an argument on it.
2. **Prefer the clustered interval where one is present.** The row interval is too narrow because three phrasings of one situation are not three independent facts.
3. **Prefer the paired difference to comparing two intervals by eye.** §2.3.
4. **AUROC below 0.5 is not "bad", it is backwards.** `gap_term` at 0.2702 is a *strong* signal pointed the wrong way.
5. **Quote the test-half gain, not the in-sample gain**, whenever you say what a different weighting would have bought.
6. **A blank cell means not applicable, never zero.** `cluster_ci_*` is blank outside the `retrieved@k` headline rows; `ci_*` is blank on rows that are counts rather than estimates.
7. **Nothing in this file changed the system.** The deployed weights are still 55/15/30 and the tiers are still 0.55/0.38.

---

### 5. What this means for the paper

**Write this up as a negative result about your own design, stated plainly. It is a contribution, not an embarrassment.** A paper that measures its own confidence score, finds it does not work, and shows exactly which component fails and why, is more useful to a reader than one that reports a number and moves on. Reviewers reward this; the alternative — quietly dropping the component — is the thing that gets caught.

Five claims the data supports, strongest first.

**1. The blended confidence score is worse than the simplest signal available.**
Composite 0.663 [0.605, 0.721 clustered] vs `max_score` 0.784 [0.732, 0.831], paired difference **+0.1207 [+0.0798, +0.1623], p < 0.0001**. Even `top_k_mean` alone — an ingredient already inside the composite — beats the composite by +0.0940. Three signals were combined and the result discriminates worse than one of them. That is the headline.

**2. The gap component is wired in backwards, and this is the mechanism.**
The raw gap is genuinely informative (AUROC 0.730): a **large** gap between the best chunk and the fifth means retrieval found one clearly-best match, which is good. The deployed system computes `1 − min(gap/0.3, 1)` and therefore rewards a **small** gap, on the stated theory that a small gap means "consistent relevance". As deployed, that term has AUROC **0.2702** — the most anti-predictive quantity anywhere in this analysis. Removing it *raises* the composite by +0.0415 (p < 0.0001). Flipping it instead lifts the best achievable blend to 0.7850, above `max_score`.
This is a clean, mechanistic finding with a one-line cause, and it is the most citable thing in the file. **Do not fix it before the paper reports the baseline** — it is the measured behaviour of the frozen configuration.

**3. `entity_coverage` is worthless in combination, and worse than worthless on the queries that matter.**
- Alone: 0.5806 under `retrieved@k`, **0.5017 under `cited`** — a coin flip.
- In combination: dropping it changes nothing under `retrieved@k` (−0.0050, p = 0.82) and **improves** the score under `cited` (+0.0842, p = 0.0018).
- The weight sweep assigns it **0.00 under all three definitions**, in-sample and on the train half.
- On `layman_situation` it is the constant 0.5 for all 120 rows, because laymen do not cite sections. On `paired_recodification` it is 0.386 — *anti*-predictive, because the query names the repealed IPC section while the corpus holds the BNS successor.
Note it is worth reporting that this is measured on the **corrected** implementation: the logged `entity_coverage` never exceeds 1.0 and takes only {0.0, 0.5, 1.0}, so the divide-chunks-by-entities defect and the free-1.0 default are *not* present in this data. The signal is not broken here. It is simply uninformative — 30% of the confidence budget spent on a three-level flag that is a constant for 43.4% of all queries.

**4. Retuning the weights is not the fix.**
The best of 231 weightings is the degenerate corner 1.00 / 0.00 / 0.00 — i.e. *stop blending, just use `top_k_mean`*. Held out properly, that buys **+0.0918** AUROC under `retrieved@k` (0.7436 vs 0.6519 on the same 247 test rows). But `max_score` alone already scores 0.7837 with no weights at all. The honest conclusion is that the three-signal architecture adds nothing over a single similarity number, not that a better weighting exists.

**5. Every number here is a measurement, not a tuning outcome — and say so explicitly.**
The weights 0.55/0.15/0.30 and the tiers 0.55/0.38 were frozen in February 2026, months before the first retrieval score was ever logged. They could not have been tuned on this evaluation set because this evaluation set did not exist. That is a real methodological strength and should be one sentence in the Method section, because the alternative reading — "she tried weightings until one worked" — is what a reviewer will otherwise assume of any ablation. The sweep in §3.3 is reported as a counterfactual and changed nothing.

**Also worth a line in Limitations:** under `grounded`, with 27 positives out of 617, *no* signal separates grounded from ungrounded answers (every interval crosses 0.5). Report that as "underpowered at n=27", not as evidence of absence.

---

### 6. What broke while computing this

**(i) The formula in the task brief was wrong, and the paired check caught it.**
The first reconstruction — brief's formula, `0.15*score_gap` untransformed — missed the logged composite on **617 of 617 rows**, by 0.148 at worst and 0.090 on average. Under the brief's instruction that a mismatch here "would mean the logged composite was not produced by the documented formula", this initially looked like the major finding. Reading `agents/retriever.py:137–142` showed the deployed code applies `1 − min(gap/0.3, 1)` first, and with that the reconstruction agrees to 9.0×10⁻⁵ on every row. So the logged composite **is** the deployed formula; the *description* was wrong, not the data. Both facts are recorded in `ablation.csv` (`composite_reconstruction_max_abs_dev` and `..._brief_formula`) so the discrepancy is visible rather than quietly absorbed. This changed the design of parts (b) and (c): they blend `gap_term`, not `score_gap`, because only then does 0.55/0.15/0.30 reproduce the deployed composite.

**(ii) I wrote a matcher with the exact bug `metrics_lib` exists to prevent.**
`check04`'s deliberately-simple `simple_key()` uppercased and squashed `"BNS Section 351"` into `"BNSSECTION351"`, then tested `startswith("BNSS")` — which is true. Every BNS citation was attributed to the BNSS, a different statute, and 69 genuine matches were silently lost (`cited` positives came out 462 instead of ~533). This is the same class of failure as defect E2. Fixed by stripping the words `SECTION` / `SEC` / `ARTICLE` / `ORDER` / `RULE` before looking for a statute prefix; the count then rose to 537. The moral, and the reason `metrics_lib.normalise_section()` is the single comparison rule: **never hand-roll section matching.** The bug and its cost are now documented in the source of `check04`.

**(iii) A count that does not match the GATE.**
The gate recorded **538** positives under `cited` at n = 617. Measured here with `metrics_lib.correctness_label(..., "cited")` the answer is **533**. `retrieved@k` (327) and `grounded` (27) both reproduce exactly; only `cited` is off, by 5. I did not resolve it, and I did not adjust anything to match. See §7.

**(iv) Runtime.** 911 s. Cluster bootstraps at N_BOOT = 10000 over 177 clusters are the cost; the run was backgrounded rather than trimmed.

---

### 7. What I could not compute, and why

**(a) The 5-row `cited` discrepancy against the GATE — NOT RESOLVED.**
533 measured here, 538 at the gate. Both `retrieved@k` and `grounded` reproduce exactly, so this is specific to the `cited` definition. Possible causes not eliminated: a different matching strictness, or the row-set difference described in (b) below. **Reported, not reconciled.** Whoever owns the gate number should reconcile it before either figure is published; do not average them and do not assume mine is right.

**(b) Three labelled rows are lost inside `load_logs()`, and I could not fix it — the loader is not my file.**
`load_logs()` deduplicates on `(query_id, intervention)` with `keep="last"`. Nine server rows have no matching `eval_summary` record and therefore no gold. In three cases such a gold-less row is the *last* occurrence of a key whose earlier occurrence **did** carry gold, so `keep="last"` discards the labelled row and keeps the unlabelled one. Verified: keys `('G0107','baseline')`, `('G0190','baseline')`, `('D0094','both')`. The labelled count is therefore **617** where a gold-preferring dedupe gives **620**. Reproduce with:

```
./venv/Scripts/python.exe -c "import sys; sys.path.insert(0,'.'); from experiments.metrics_lib import load_logs; d=load_logs(); print(len(d), int(d['expected_sections'].map(lambda x: len(x or [])>0).sum()))"
```

This is ~0.5% of the data and does not move any conclusion here, but it is a shared-loader issue affecting every subagent's `n`. **Flagged for the `metrics_lib` owner; not fixed by me.**

**(c) Clustered confidence intervals for `cited` and `grounded` — NOT MEASURED.**
Cluster bootstraps are computed only for the `retrieved@k` headline rows in parts (a) and (b). At 10,000 resamples over 177 clusters each one costs ~36 s, and covering all three definitions plus the per-query-set breakdown would have pushed the run past an hour. The row-level intervals are present everywhere; treat them as **narrower than the truth** wherever the clustered column is blank. Any conclusion here that depends on an interval's exact width should be re-run with clustering before publication.

**(d) Clustered intervals for the paired differences — NOT MEASURED**, same reason. `paired_bootstrap_auroc_diff()` accepts `cluster_ids` and would give the honest interval; the `p_two_sided` values reported are from the row bootstrap and are therefore anti-conservative.

**(e) A selection-corrected interval for the sweep argmax — NOT COMPUTED.**
`auroc_diff_sweep_argmax_vs_deployed` bootstraps the difference between the winning weighting and the deployed one, but the winner was *chosen on those same rows*, and the bootstrap does not re-run the selection inside each resample. That interval is therefore anti-conservative and is labelled as such in `notes`. The train/test split in §3.3 is the correct answer to this question and is what should be quoted; a nested bootstrap that re-selects inside each resample would be better still and was not attempted.

**(f) Anything requiring re-retrieval — OUT OF SCOPE.** Zero API calls were made. Every number is recomputed from signals already logged.

---

### 8. What surprised me

**1. The composite is beaten by its own ingredients.** I expected a blend to be at worst roughly as good as its best component — that is the intuition combination usually earns. Instead 0.663 sits below `top_k_mean`'s 0.757, which is *inside* it at 55% weight. Two of the three ingredients are not merely diluting the good one; one of them is actively pulling in the wrong direction. Averaging a signal with an anti-signal destroys information, and I had not internalised how much.

**2. The sign error hid behind a plausible sentence.** `# Signal 2: Score drop-off (small gap = consistent relevance)` reads perfectly sensibly. It is even arguably true about *relevance*. It is just false about *correctness* — what actually predicts finding the right section is one chunk standing clearly above the rest, not five chunks being equally mediocre. AUROC 0.270 versus 0.730 for the same underlying quantity, and the only difference is which direction "good" points. A comment that sounds right is not evidence, and no test could have caught this, because the code does exactly what the comment says.

**3. The argmax was the degenerate corner, not a nearby adjustment.** I expected something like 0.70/0.10/0.20 — the deployed recipe, nudged. What 231 weightings actually chose was 1.00/0.00/0.00 under all three definitions: *delete two of the three signals*. And it is not a flat-surface accident — exactly 1 of 231 weightings comes within 0.005 of it under `retrieved@k`.

**4. The per-query-set table nearly fooled me into the opposite conclusion.** On `generated_retrieval` the composite scores 0.873 and `entity_coverage` 0.880 — in isolation those numbers say the confidence score works beautifully. They say nothing of the kind: those queries were *constructed* by naming a section, so "does the retrieved text mention the named section" is close to reading the answer key. On `layman_situation` — the queries this system exists to serve — the same signal is the constant 0.5. **An aggregate over query sets built by different processes can average a label leak together with a constant and produce a respectable-looking middle.** Always break the table down by query set before believing it.

**5. `entity_coverage` was anti-predictive on `paired_recodification` (0.386), and the reason is a legal fact, not a bug.** The query names a repealed IPC section; the corpus holds its BNS successor. The entity genuinely is not in the right chunk, and the times it *does* appear are the times retrieval landed in the wrong (repealed) statute. The signal is working exactly as coded and is wrong anyway, because the underlying assumption — that the words of the query should appear in the correct answer — fails specifically under recodification. That is a substantive point about legal RAG, not about this codebase, and it may be the most paper-worthy observation in this file.

---

# Robustness and clustering

Output file: `results/robustness.csv`
Regenerate with: `./venv/Scripts/python.exe experiments/exp05_robustness.py`
Verify with: `./venv/Scripts/python.exe experiments/check05_robustness_check.py`
Owner: Wave 2 Subagent 5
Seed 20260901 · N_BOOT 10000 · zero API calls · reads only

---

### 1. ELI5 — what does this measure?

Two questions, both about whether the other four subagents' numbers are actually true.

**Question one: does "correct" mean what you think it means?**

This project can call an answer correct in three different ways:

| Name | Means | Positives out of 617 |
|---|---|---|
| `retrieved@15` | the right section of law was **found** and put in front of the model | **327** (53.0%) |
| `cited` | the right section **appears in the answer text** | **538** (87.2%) |
| `grounded` | **every** section the answer cited was actually supported by retrieved text | **27** (4.4%) |

Same 617 questions. Same system. Same day. The score is 87% or 53% or 4% depending purely on which of these three you write in the paper. So any sentence of the form "the system achieves X" is meaningless until it says *which* X. This experiment re-runs the project's three core analyses under **all three**, and never picks one.

**Question two: how much evidence do you actually have?**

The query sets are not 617 separate questions. They are 177 legal *situations*, each asked several different ways. Here is one real situation, `pair_id = L001`, gold answer IPC 376 / BNS 64:

| variant | the query | found the right law? |
|---|---|---|
| `no_date` | "i was sexually assaulted and this happened but it has been long time now…" | no |
| `ipc_era` | *same text* + "This happened in March 202…" | no |
| `bns_era` | *same text* + "This happened last month." | no |
| `vague` | *same text* + "This happened a while back" | no |

Those four rows are the **same sentence with a different date glued on the end**. They failed together, for the same reason. Counting them as four independent failures is like asking one person the same question four times and writing down four opinions.

It is not a fluke of L001. Across the 30 layman situations, **28 of 30 (93.3%)** had all four phrasings agree — either all four found the law or all four missed it. Only 2 situations split.

So the layman set contains something much closer to **30** pieces of evidence than 120. Pretending it has 120 makes the error bars too narrow, and "too narrow" is exactly what a reviewer will circle.

---

### 2. Technically

Terms, each defined once, in the order you meet them.

| Term | Definition |
|---|---|
| **Independent observation** | A data point that carries genuinely new information — knowing the others would not let you guess it. The four L001 rows are *not* independent: knowing three tells you the fourth almost certainly. |
| **Cluster** | A group of rows that belong together and are not independent of each other. Here a cluster is one legal situation, identified by `pair_id`. 617 rows fall into **177** clusters. |
| **Naive interval** | A 95% confidence interval computed as if every row were independent. Too narrow whenever clusters exist and agree internally. |
| **Cluster bootstrap** | Instead of resampling *rows*, resample whole *situations* with replacement, 10,000 times, and take the 2.5th and 97.5th percentiles. A situation is drawn all-or-nothing, so the fact that its phrasings agree can no longer masquerade as extra evidence. `metrics_lib.cluster_bootstrap()`. |
| **Design effect** | clustered interval width ÷ naive interval width. Above 1 = clustering widened the interval (the usual case). Below 1 = clustering narrowed it. |
| **`width_ratio`** | naive ÷ clustered — the ratio this task asked for. It is the **reciprocal** of the design effect, so *smaller than 1 is the normal, healthy case*. Both are written into every `notes` field so neither can be misread. |
| **Sensitivity analysis** | Recomputing a result under a different reasonable choice, to see whether the conclusion depended on the choice rather than on the data. Done here for the correctness definition (three of them) and for four data restrictions. |

**How the naive column is computed, and why it matters.** The naive interval is *not* a Wilson formula. It is the same `cluster_bootstrap()` call with the cluster column set to a per-row unique id, so each "cluster" is one row and the resample degenerates to an ordinary row bootstrap. Same code, same seed, same 10,000 draws — **the only thing that changes between the two columns is the definition of a cluster.** Had the naive column used a closed-form Wilson interval instead, the width ratio would have confounded "clustering" with "bootstrap vs formula". CHECK 4 confirms Wilson and the naive bootstrap agree anyway (widths 0.1276 vs 0.1250, ratio 0.979).

---

### 3. What the number came out as

All values below are `restriction=none`, the full 617 rows / 177 clusters. Every gate anchor reproduced exactly: 327 / 538 / 27 positives, and the paired 87.9% / 33.3%.

**The naive-vs-clustered table.** This is the headline deliverable.

| value | definition · stage | n | point | naive 95% CI | clustered 95% CI | width_ratio | design effect |
|---|---|---|---|---|---|---|---|
| paired rate, IPC-numbered | retrieved@15 · raw_15 | 33 | 0.879 | [0.758, 0.970] | [0.758, 0.970] | 1.000 | 1.00 |
| paired rate, BNS-numbered | retrieved@15 · raw_15 | 33 | 0.333 | [0.182, 0.485] | [0.182, 0.485] | 1.000 | 1.00 |
| **paired gap IPC − BNS** | retrieved@15 · raw_15 | 66 | **+0.545** | [0.348, 0.737] | **[0.303, 0.758]** | 0.856 | 1.17 |
| paired gap IPC − BNS | cited | 66 | −0.030 | [−0.160, 0.096] | **[−0.121, 0.061]** | 1.406 | 0.71 |
| paired gap IPC − BNS | grounded | 66 | −0.030 | [−0.100, 0.000] | [−0.091, 0.000] | 1.100 | 0.91 |
| **layman rate** | retrieved@15 · raw_15 | 120 | **0.150** | [0.092, 0.217] | **[0.033, 0.275]** | **0.517** | **1.93** |
| layman rate | retrieved@15 · filtered_n | 120 | 0.075 | [0.033, 0.125] | **[0.000, 0.167]** | 0.550 | 1.82 |
| layman rate | cited | 120 | 0.667 | [0.583, 0.750] | [0.542, 0.783] | 0.690 | 1.45 |
| layman rate | grounded | 120 | 0.000 | [0.000, 0.000] | [0.000, 0.000] | — | — |
| AUROC composite | retrieved@15 · raw_15 | 617 | 0.663 | [0.617, 0.710] | [0.605, 0.721] | 0.793 | 1.26 |
| AUROC max_score | retrieved@15 · raw_15 | 617 | 0.784 | [0.747, 0.820] | [0.732, 0.831] | 0.728 | 1.37 |
| **AUROC diff (composite − max)** | retrieved@15 · raw_15 | 617 | **−0.121** | [−0.162, −0.080] | **[−0.166, −0.075]** | 0.909 | 1.10 |
| AUROC diff | cited | 617 | −0.103 | [−0.159, −0.046] | [−0.164, −0.041] | 0.913 | 1.09 |
| AUROC diff | grounded | 617 | −0.058 | [−0.169, 0.056] | [−0.158, 0.045] | 1.110 | 0.90 |

The two paired *arms* show `width_ratio` exactly 1.000 because each situation contributes exactly one IPC row and one BNS row — there is nothing inside a cluster to collapse, so clustering is a no-op there **by construction**, not by accident.

**Why clustering bites hardest on the layman set.** Per query set, for `retrieved@15 / raw_15`:

| query set | rows | situations | all variants agreed | design effect |
|---|---|---|---|---|
| `layman_situation` | 120 | 30 | **93.3%** | **1.93** |
| `generated_retrieval` | 198 | 80 | 42.5% | 1.13 |
| `paired_dated_conflict` | 197 | 33 | 3.0% | **0.79** |
| `paired_recodification` | 99 | 33 | 24.2% | **0.64** |

The layman number is near the theoretical ceiling: with 4 phrasings per situation that agree essentially always, the most clustering can cost you is √4 = 2.00, and it costs 1.93. **The layman set's effective sample size is 30, not 120.**

The bottom two sets are *below* 1, and that is by design rather than by defect — see section 6.

---

### 4. How to read it

- **Read the clustered interval, not the naive one.** The naive column is in the file only so the difference is visible; it is not the number for the paper.
- **`width_ratio` below 1 is healthy.** It means clustering widened the interval, which is what should happen. Do not read a small ratio as a small problem — 0.517 means the honest interval is nearly **twice** as wide.
- **Never quote a rate without its definition and its stage.** "15.0%" and "7.5%" for the layman set are not a disagreement between two studies; they are `raw_15` and `filtered_n` of the same measurement, and both are in the table above.
- **The `n` column is rows, not evidence.** For the layman set, `n=120` but there are 30 situations. The clustered interval already accounts for this; the naive one does not.
- **An interval touching 0.000 means "cannot rule out zero."** That is the case for the layman `filtered_n` rate once clustered.

---

### 5. What this means for the paper

Three claims were tested. **One survives everything. Two do not.** Naming the failures is the point of this task.

#### CLAIM 1 — "IPC-numbered queries retrieve the right law far more often than BNS-numbered ones" (the recodification gap)

| definition | gap | clustered CI | verdict |
|---|---|---|---|
| `retrieved@15` raw_15 | +0.545 | [0.303, 0.758] | **HOLDS** |
| `retrieved@15` reranked_15 | +0.545 | [0.303, 0.758] | **HOLDS** |
| `retrieved@15` filtered_n | +0.455 | [0.242, 0.667] | **HOLDS** |
| `cited` | −0.030 | [−0.121, 0.061] | **DIES** — contains 0, and the sign flips |
| `grounded` | −0.030 | [−0.091, 0.000] | **DIES** — contains 0 |

It also holds under all four stability restrictions, naive and clustered.

**But it is a claim about retrieval only, and the paper must say so.** Under `cited` the gap is gone: the IPC arm cites the gold section 90.9% of the time and the BNS arm 93.9% — *higher*. The model names the right section whether or not the retriever found it. That is this project's known "cites unretrieved authority" pathology, and it means the recodification gap is **invisible in the output the user actually reads**. Written as "the system answers IPC-numbered questions better", the claim is false. Written as "the retriever finds IPC-numbered provisions better, while the generator papers over the difference by citing from parametric memory", it is true, supported, and considerably more interesting.

#### CLAIM 2 — "the layman retrieval rate is low but non-zero"

| definition · stage | rate | naive CI | clustered CI | verdict |
|---|---|---|---|---|
| `retrieved@15` raw_15 | 0.150 | [0.092, 0.217] | [0.033, 0.275] | holds, but barely |
| `retrieved@15` filtered_n | 0.075 | [0.033, 0.125] | **[0.000, 0.167]** | **DIES UNDER CLUSTERING** |
| `cited` | 0.667 | [0.583, 0.750] | [0.542, 0.783] | holds |
| `grounded` | 0.000 | [0.000, 0.000] | [0.000, 0.000] | zero positives |

**This is the one claim that clustering alone kills, and it is the specific answer to "does clustering cross a threshold a claim depends on."**

At the `filtered_n` stage — the chunks that actually reach the language model — the naive interval is [0.033, 0.125], comfortably above zero. The clustered interval is **[0.000, 0.167]**. The lower bound moves from 0.033 to 0.000, a shift of 3.3 percentage points, and the interval width grows from 0.092 to 0.167 (design effect 1.82). Once the 4 phrasings of a situation are correctly counted as 1, **the data cannot rule out that the true layman retrieval rate at `filtered_n` is zero.** With 30 situations and 9 hits concentrated in 3 of them, that is the honest reading.

The spread across definitions is the other half of the story: 0.0% (`grounded`), 7.5% (`filtered_n`), 15.0% (`raw_15`), 66.7% (`cited`). A paper quoting any one of these without the other three is not reporting a result, it is choosing one.

#### CLAIM 3 — "the composite confidence score is worse than raw max_score"

| definition | restriction=none | excl. entity default | excl. filter null | one variant per situation |
|---|---|---|---|---|
| `retrieved@15` raw_15 | **−0.121 [−0.166, −0.075]** ✓ | −0.116 [−0.177, −0.051] ✓ | −0.156 [−0.210, −0.099] ✓ | −0.119 [−0.201, −0.037] ✓ |
| `cited` | −0.103 [−0.164, −0.041] ✓ | −0.026 [−0.149, 0.099] ✗ | −0.075 [−0.195, 0.047] ✗ | −0.121 [−0.237, 0.016] ✗ |
| `grounded` | −0.058 [−0.158, 0.045] ✗ | +0.219 [−0.115, 0.539] ✗ | −0.017 [−0.179, 0.144] ✗ | −0.075 [−0.236, 0.103] ✗ |

**Survives under `retrieved@15` in every restriction — this is the robust version of the claim.** Under `cited` it survives only on the full data and collapses under all three real restrictions. Under `grounded` it never holds, and under one restriction the point estimate even flips sign (+0.219), though with an interval so wide it establishes nothing.

Safe wording: *"the composite score discriminates retrieval success worse than raw max score alone (ΔAUROC −0.121, cluster-bootstrap 95% CI [−0.166, −0.075])."* Do not generalise it to answer quality — under the two answer-level definitions it does not hold.

#### One more thing the paper needs to disclose

The **`grounded` definition has 27 positives out of 617 (4.4%)**, and **zero** of them are in the layman set and zero in the paired IPC arm. Any analysis conditioned on `grounded` is running on almost no positive examples, which is why its intervals are enormous and why nothing is ever significant under it. It should be reported as a diagnostic, not used as the primary correctness definition.

---

### 6. What broke while computing this

1. **The width ratio was inverted, and it produced a false alarm on every headline value.** My first version flagged "clustered NARROWER" whenever `naive/clustered > 1`, which is backwards — that condition is the *healthy* one reversed. The smoke run duly reported the layman rate as narrowing under clustering, which is impossible for a mean over positively-correlated rows. Caught by checking the layman case against theory before trusting it: the analytic cluster-robust SE is 0.06297 against a naive 0.03260, a design effect of 1.932, and the bootstrap gives 1.933. Clustering had been *widening* the whole time. Fixed, direction now stated explicitly in the code, and CHECK 2 exists precisely to catch this class of error.

2. **The 3 legacy `criminal_*` rows are NOT already excluded from the 617.** The task brief stated they should be. They are not: `Q001`, `Q002`, `Q003` carry gold labels, survive the gold-label filter, and sit inside the headline 617. They also share a single `pair_id` (`P_murder`) *across two different query sets*, making them the only cluster in the data that spans query sets. Excluding them (n=614) changes nothing material — the AUROC diff moves from −0.121 to −0.120 — but the 617 is not the clean set it was described as.

3. **The 4 unlabelled rows are not what the brief called them.** Described as "4 unlabelled SMOKE rows". Only one (`SMOKE01`) is a smoke row; the other three are real queries — `G0107`, `G0190`, `D0094` — that failed to join to a gold record. They are correctly dropped, but they represent 3 lost real observations, not test scaffolding.

4. **Two other brief details did not match the data.** The dated set is 33 situations × 3 variants × 2 interventions = 197 rows, not "30 × 4"; the "30 situations × 4 variants" description belongs to the *layman* set. And `filter_applied is None` covers **208** rows, not 210.

5. **`ZeroDivisionError` in the check.** Degenerate zero-width intervals (layman `grounded`, which is 0/120 with no positives at all) produced a 0/0 width ratio. Guarded.

6. **The narrowings that are NOT a bug.** CHECK 2 asserts that clustering must widen. It fires on 8 AUROC values, and **4 of them are correct behaviour**: the within-situation correlation there is *negative*. In the contrastive sets the phrasings of a situation are **built to disagree** — the IPC-named and BNS-named versions of one murder question are designed to come out differently — so `paired_recodification` has a design effect of 0.64 and `paired_dated_conflict` 0.79. Resampling whole situations then *cancels* variance instead of adding it. Confirmed directly by splitting the data:

   | subset | AUROC naive width | clustered width | width_ratio |
   |---|---|---|---|
   | positively-correlated sets (generated + layman) | 0.0788 | 0.1146 | 0.688 (widens) |
   | contrastive sets (dated + recodification) | 0.1356 | 0.1133 | **1.197 (narrows)** |

   The restrictions `exclude_entity_default_used` and `exclude_filter_applied_null` delete the entire layman set and much of `generated`, leaving a remainder dominated by the contrastive sets — which is why narrowing appears there and nowhere else. The same effect explains why the paired IPC−BNS **gap** narrows under `cited` (`width_ratio` 1.406): the within-situation correlation between the two arms is **−0.328**.

7. **4 narrowings remain genuinely unexplained, and CHECK 2 is left FAILING because of them.** See section 7. I did not weaken the test until it passed.

---

### 7. What I could not compute, and why

| Wanted | Status | Why |
|---|---|---|
| Layman rate under `exclude_entity_default_used` | **NOT MEASURED** | The restriction removes **all 120** layman rows. Every single layman query used the neutral 0.30 entity-coverage default — 120/120. The layman set *is* the no-entity case, so "layman results excluding the neutral default" does not exist. |
| Layman rate under `exclude_filter_applied_null` | Computed but **useless** (n=4) | 116 of 120 layman rows had no corpus filter applied. The surviving 4 rows are reported with their n so nobody mistakes them for a result. |
| `grounded` design effect for the layman set and the paired IPC arm | **NOT MEASURED** | Zero positives (0/120 and 0/33). A statistic with no variance has no interval; the code writes empty rather than a plausible-looking number. |
| Why 4 AUROC narrowings persist | **UNRESOLVED** | All 4 are `auroc_composite` / `auroc_max_score` under `cited` and `grounded`, on the two restricted subsets, with width ratios 1.043–1.121. Ruled out: a resampler bug (CHECK 3 reproduces the analytic design effect to 4 significant figures, 1.933 vs 1.932) and Monte Carlo noise (the ratio is stable at 1.078–1.096 across five seeds). Not ruled out: **AUROC is a rank statistic**, and the design-effect argument used throughout this document is derived for a *mean*. The cluster-robust variance of AUROC depends on the covariance of placement values, which I did not derive. **Until that is settled, do not rely on the clustered AUROC intervals for these two restricted subsets.** The `restriction=none` AUROC intervals are unaffected and behave correctly (design effects 1.03–1.37). |
| Clustering across *sections* rather than situations | Not attempted | `P_IPC302` (paired) and `D_IPC302` (dated) are different `pair_id`s covering the same provision, so the two sets are treated as independent when arguably they are not. This would widen intervals further, never narrower. Flagged for `OPEN_QUESTIONS.md`. |

---

### 8. What surprised me

**The layman variants are the same sentence.** I expected four differently-worded questions per situation. They are one identical stem with a date phrase appended — "This happened last month." versus "This happened a while back". Nothing that a retriever keys on differs between them. The 93.3% unanimity is not a finding about robustness to phrasing; it is close to a tautology, and it means the layman set was always a 30-question benchmark wearing a 120-question label.

**The definition swing is larger than any effect being measured.** Moving from `grounded` to `cited` changes the score by **83 percentage points** (4.4% → 87.2%). The recodification gap — the paper's headline effect — is 54 points. The labelling choice is worth more than the phenomenon. That reframes what the contribution is: the measurement problem is at least as publishable as the system.

**Clustering does not always widen, and I had it backwards in code before I had it backwards in my head.** I had internalised "clustering widens intervals" as a law. It is a law only when rows inside a cluster *agree*. Half this project's query sets are deliberately contrastive, so their clusters *disagree*, and there clustering correctly tightens the estimate. My first implementation encoded the folk version, flagged the healthy cases as bugs, and would have had me report the layman interval as suspicious when it was the most correct number in the file.

**The generator hides the retriever's biggest failure.** The paired gap is +54 points at retrieval and −3 points at citation. The single most striking result in this task is not a number the system produces — it is the difference between two ways of scoring it, and it says the answer text cannot be used as evidence that retrieval worked.

---

# statute_consistency

Output file: `results/statute_consistency.csv`
Regenerate with: `./venv/Scripts/python.exe experiments/exp06_statute_consistency.py`
Verify with: `./venv/Scripts/python.exe experiments/check06_statute_check.py`
Owner: Wave 3 Subagent 1

---

## 1. ELI5 — what does this measure?

Ask the system a question and it fetches 15 passages. The three confidence
signals already in the system all ask the *same kind* of question about those
passages: **how similar are they to the question?** `top_k_mean` averages the
similarity of the best five. `score_gap` looks at how fast similarity falls
off. `entity_coverage` checks whether the section number the user typed shows
up in the text.

None of them asks the question a lawyer would ask first:

> **Did you look it up in the right book?**

India replaced three colonial-era codes on **1 July 2024**. The Indian Penal
Code became the Bharatiya Nyaya Sanhita; the Criminal Procedure Code became
the Bharatiya Nagarik Suraksha Sanhita. The old codes still govern anything
that happened *before* that date — that is what "savings provisions" means.
So the *same* question has two different right answers depending on **when the
incident happened**.

The two texts are near word-for-word identical, so similarity cannot tell
them apart. A system can be maximally confident and still be quoting a
repealed statute.

`statute_consistency` is the fourth signal. In one line:

> Of the passages we retrieved, **what fraction came out of a book that is
> actually allowed to answer this question**, given what the query says and
> when the incident happened?

1.0 means every passage came from an admissible statute. 0.0 means not one
did. It is a fraction, so it is always between 0 and 1.

### The worked example — one real query, real numbers

Query `D0001`, from the `paired_dated_conflict` set, run on 23 August 2026:

> *"What is the punishment for unlawful assembly – common object under
> **Section 149 of the Indian Penal Code**? **This happened last month.**"*

Two facts fight each other. The user **names the IPC**. The user also says
the incident was **last month** — July 2026, two years *after* the BNS came
into force. The date wins: the correct answer is **BNS 190**, not IPC 149.
That is the gold label the query set records.

Here is what each signal said:

| | value | reads as |
|---|---|---|
| `top_k_mean` | 0.7033 | very strong similarity |
| `score_gap` | 0.0947 | tight, consistent cluster |
| `entity_coverage` | **1.0000** | "found Section 149!" |
| **`composite` (deployed)** | **0.7895** | **HIGH tier** — answer confidently |
| retrieved sections | IPC 149, 143, 141, 151, 145, … | **all 15 chunks are IPC** |
| gold section BNS 190 retrieved? | **no** | |

Every generic signal is delighted. The system found Section 149, in the IPC,
with high similarity — and Section 149 IPC is exactly the provision the user
asked for. It is also the *wrong law for this incident*, and the system had
no way to notice.

Now the fourth signal, step by step:

| step | value |
|---|---|
| era implied by "last month" (July 2026) | `BNS_ERA` |
| codes in force then (from the Qdrant `in_force_from` / `in_force_until` payload) | `{BNS, CPA}` |
| statutes the query names | `{IPC}` |
| subject-matter family of the IPC | PENAL → `{IPC, BNS}` |
| **admissible set** = in-force ∩ family | **`{BNS}`** |
| retrieved chunks whose `statute_code` is in `{BNS}` | **0 of 15** |
| **`statute_consistency`** | **0.000** |

The deployed composite says 0.79. The fourth signal says 0.00. The fourth
signal is the one that is right.

A second, softer example — layman query `L0003`, no section number named,
incident dated to the BNS era, gold `BNS 64`:

| | |
|---|---|
| admissible set | `{BNS, CPA}` (no statute named → no family constraint) |
| retrieved corpora at raw_15 | CRPC 11, IPC 3, BNS 1 |
| `statute_consistency` | **1/15 = 0.067** |
| deployed `composite` | 0.4704 |

---

## 2. Technically

### The definition, and why this one

The specification in `docs/TARGET_ARCHITECTURE.md:348` is one line:

```
statute_consistency = fraction of retrieved chunks whose statute_code
                      is in the set implied by the query + date
```

"The set implied by the query + date" is the entire design decision, so it was
written down and **frozen before a single AUROC was computed**. Five variants
were computed and **all five are reported**; `A2` was declared primary in
advance. Nothing was added, dropped or changed after seeing a number — see
§6.

**What is in the corpus.** Read by scrolling Qdrant `legal_mvp` (1,899 points,
read-only). `corpus == statute_code` on **all 1,899** points, so the `corpus`
field in `experiments/stages.jsonl` *is* the `statute_code`:

| code | statute | `in_force_from` | `in_force_until` | points |
|---|---|---|---|---|
| IPC | Indian Penal Code, 1860 | 1862-01-01 | 2024-07-01 | 595 |
| CRPC | Code of Criminal Procedure, 1973 | 1974-04-01 | 2024-07-01 | 742 |
| BNS | Bharatiya Nyaya Sanhita, 2023 | 2024-07-01 | — | 424 |
| CPA | Consumer Protection Act, 2019 | 2020-07-20 | — | 138 |

The in-force windows are **read from the payload**, not written by me. The
BNSS, the BSA and the Evidence Act are **not in this corpus at all**.

**D(era) — the date-admissible set.** `{c : in_force_from(c) ≤ t < in_force_until(c)}`
evaluated at a representative date per era:

| era | representative date | D |
|---|---|---|
| `IPC_ERA` | 2024-06-30 | `{IPC, CRPC, CPA}` |
| `BNS_ERA` | 2024-07-01 | `{BNS, CPA}` |
| `UNKNOWN` | — | all four |

**The UNKNOWN branch is the important one.** 60 of the 120 layman queries
state no date, and 56 of those have gold that is correct under *either*
regime. Those are treated as **unconstrained by date** — never as errors.
Scoring a no-date query against one regime would manufacture a result out of
an annotation choice.

**F(named) — the query-admissible set.** From `retrieval.named_statutes`,
which the deployed system logged on every row. A named code implies its
**subject-matter family**, because the recodification renamed books without
moving subject matter: PENAL `{IPC, BNS}`, PROCEDURE `{CRPC, BNSS}`,
EVIDENCE `{IEA, BSA}`, CONSUMER `{CPA}`. Names nothing → all four.

**The five variants:**

| variant | admissible set A | deployable? |
|---|---|---|
| `A1_date_only` | D(era) | yes, with a date parser |
| **`A2_date_x_family` (PRIMARY)** | D(era) ∩ F(named); F(named) if empty | yes, with a date parser |
| `A3_family_only` | F(named) | yes |
| `A4_oracle_gold` | `expected_corpora` from the query set | **NO — reads the gold** |
| `A5_deployed_date` | A2 with the era taken **only** from the logged `date.era` | yes, no oracle at all |

The empty-intersection fallback **never fired** (0 rows, all variants).

**Where the era comes from** for A1/A2/A3: the logged `date.era` where present
(98 of 617 rows), else the query set's `applicable_regime`, else UNKNOWN.
`applicable_regime` is a human annotation *of the query text* — it records
what the query's stated date implies, which a working date parser would
recover. Using it on 519 rows **assumes a perfect date parser**, and that is
disclosed. `A5` exists precisely so the no-oracle version is on the record.

Then, per row and per stage:

```
statute_consistency = |{chunks with statute_code ∈ A}| / |chunks|
```

Every chunk carries a `statute_code`, so nothing is dropped.

### Everything else, briefly

* **Correctness** comes from `metrics_lib.correctness_label()` under all three
  definitions: `retrieved@k` (gold section in the top 15), `cited` (gold
  appears in the answer's citations), `grounded` (every citation supported).
* **AUROC** is `metrics_lib.auroc` (Mann-Whitney U with average ranks, so ties
  count 0.5). **Nothing is reimplemented.**
* **Bootstrap** N_BOOT = 10,000, SEED = 20260901, percentile intervals.
  Clustered intervals resample `pair_id` clusters (177 clusters over 617 rows;
  `pair_id` is present on all 617).
* **ECE** = 10 quantile bins, `metrics_lib.ece`.
* **Wilson** intervals from `metrics_lib.wilson`.

---

## 3. What the number came out as

n = **617** gold-labelled rows (621 after `load_logs()` dedupe, 4 dropped for
having no gold section). 177 `pair_id` clusters. Positives: **327** under
`retrieved@15` at `raw_15` / `reranked_15`, **304** at `filtered_n`, **533**
under `cited`, **27** under `grounded`.

### 3a. The headline — AUROC of `statute_consistency` (variant A2)

`retrieved@k`, k = 15. Naive 95% bootstrap CI, then the `pair_id`-clustered CI.

| stage | query set | n | AUROC | naive 95% CI | clustered 95% CI |
|---|---|---|---|---|---|
| `raw_15` | **ALL** | 617 | **0.685** | [0.656, 0.714] | [0.659, 0.709] |
| `raw_15` | `generated_retrieval` | 198 | 0.500 | [0.500, 0.500] | — |
| `raw_15` | `paired_recodification` | 99 | 0.500 | [0.500, 0.500] | — |
| `raw_15` | **`paired_dated_conflict`** | 197 | **0.830** | [0.782, 0.875] | [0.797, 0.867] |
| `raw_15` | `layman_situation` | 120 | 0.566 | [0.442, 0.680] | [0.474, 0.675] |
| `reranked_15` | ALL | 617 | 0.685 | [0.656, 0.714] | [0.659, 0.709] |
| `reranked_15` | `paired_dated_conflict` | 197 | 0.830 | [0.782, 0.875] | [0.797, 0.867] |
| `filtered_n` | **ALL** | 617 | **0.658** | [0.631, 0.684] | [0.634, 0.682] |
| `filtered_n` | `paired_dated_conflict` | 197 | 0.806 | [0.759, 0.851] | [0.768, 0.851] |
| `filtered_n` | `layman_situation` | 120 | 0.511 | [0.346, 0.658] | [0.397, 0.662] |

The 0.500 rows are **not measurements**. On `generated_retrieval` and
`paired_recodification` **no query states a date**, so the admissible set is
every code and the signal is **constant at 1.0**. AUROC of a constant is 0.5
by the tie rule. The CSV says so in the `notes` column of every such row.

`reranked_15` is identical to `raw_15` throughout: reranking reorders the same
15 chunks, and a fraction over a set does not care about order. That is a
correctness check, not a coincidence.

Under the other two correctness definitions, pooled:

| definition | stage | n | AUROC | naive CI | clustered CI |
|---|---|---|---|---|---|
| `cited` | `raw_15` | 617 | 0.668 | [0.613, 0.723] | [0.619, 0.723] |
| `cited` | `filtered_n` | 617 | 0.650 | [0.595, 0.705] | [0.599, 0.705] |
| `grounded` | `raw_15` | 617 | 0.599 | [0.583, 0.615] | [0.584, 0.614] |
| `grounded` | `filtered_n` | 617 | 0.588 | [0.573, 0.604] | [0.574, 0.602] |

`grounded` per query set is **NOT MEASURED** — with only 27 positives in 617
rows, several sets contain no positive at all.

### 3b. The ablation picture, now with four rows

`retrieved@k` / `raw_15` / pooled, n = 617:

| signal | blend weight | AUROC | naive 95% CI | clustered 95% CI | ECE |
|---|---|---|---|---|---|
| `max_score` | (not in blend) | 0.784 | [0.747, 0.819] | [0.732, 0.831] | 0.127 |
| `top_k_mean` | 0.55 | 0.757 | [0.719, 0.794] | [0.702, 0.807] | 0.111 |
| **`statute_consistency`** | **(new)** | **0.685** | **[0.656, 0.714]** | **[0.659, 0.709]** | **0.319** |
| `composite` (deployed) | — | 0.663 | [0.617, 0.710] | [0.605, 0.721] | 0.241 |
| `entity_coverage` | 0.30 | 0.581 | [0.538, 0.623] | [0.544, 0.618] | 0.270 |
| `gap_term` | 0.15 | 0.270 | [0.232, 0.311] | [0.219, 0.326] | — |

The five existing rows reproduce `results/ablation.csv` **to the sixth
decimal**; `check06` asserts it.

### 3c. Paired comparisons (`retrieved@k`, `raw_15`)

Paired bootstrap on the same rows, `paired_bootstrap_auroc_diff()`.
Positive = statute_consistency wins.

| query set | vs `composite` | p | vs `max_score` | p |
|---|---|---|---|---|
| ALL | +0.021 [−0.041, +0.084] | 0.497 | **−0.099** [−0.149, −0.048] | 0.0002 |
| **`paired_dated_conflict`** | **+0.359** [+0.252, +0.470] | 0.0000 | **+0.174** [+0.074, +0.276] | 0.0008 |
| `paired_recodification` | +0.147 [+0.009, +0.281] | 0.038 | −0.235 [−0.327, −0.133] | 0.0002 |
| `generated_retrieval` | −0.373 [−0.447, −0.285] | 0.0000 | −0.380 [−0.425, −0.330] | 0.0000 |
| `layman_situation` | −0.005 [−0.211, +0.207] | 0.980 | +0.014 [−0.169, +0.204] | 0.873 |

### 3d. The variants

`retrieved@k` / `raw_15` / pooled:

| variant | AUROC | 95% CI | note |
|---|---|---|---|
| `A1_date_only` | 0.685 | [0.656, 0.714] | **identical to A2 on every one of the 617 rows** |
| `A2_date_x_family` | 0.685 | [0.656, 0.714] | PRIMARY |
| `A3_family_only` | 0.500 | — | **constant at 1.0** — carries no information |
| `A4_oracle_gold` | 0.704 | [0.666, 0.740] | ORACLE — reads the gold; upper bound only |
| `A5_deployed_date` | 0.500 | — | **constant at 1.0** — identical to A3 |

### 3e. `entity_coverage`, computed both ways (n = 617)

| | logged (substring in chunk text) | recomputed (from `section_number` payload) |
|---|---|---|
| mean | 0.5778 | **0.5494** |
| distinct values | 0.00, 0.50, 1.00 | 0.00, 0.50, 1.00 |
| maximum | **1.00** | 1.00 |
| AUROC pooled, `retrieved@k`/`raw_15` | 0.5806 | **0.6050** |
| AUROC `generated_retrieval` | 0.8799 | **0.9854** |
| AUROC `paired_recodification` | **0.3857** (below chance) | 0.4136 |
| AUROC `paired_dated_conflict` | 0.4743 | 0.4943 |
| AUROC `layman_situation` | NOT MEASURED (constant 0.5) | NOT MEASURED (constant 0.5) |

Difference: mean signed **−0.0284** (payload minus logged), **18 rows of 617
change**, and **all 18 change downward**. Paired bootstrap of the AUROC
difference, pooled: **+0.0245**. On `generated_retrieval`: **+0.1055**.

The payload version is never *lower* than the substring version on any row,
because the substring rule can only ever *over*-count.

**The Wave 2 corrections, verified independently here:**

| claim | verdict |
|---|---|
| `entity_coverage` takes only {0.0, 0.5, 1.0} | **CONFIRMED** — 3 distinct values |
| never exceeds 1.0 | **CONFIRMED** — max is exactly 1.0 |
| no free 0.30 neutral default | **CONFIRMED** — the constant is `ENTITY_NEUTRAL = 0.5`, weighted 0.30, so it contributes 0.15, not 0.30 |
| AUROC is 0.581, not the 0.492 in the docs | **CONFIRMED** — 0.580565 |
| constant for 43.4% of queries | **CONFIRMED** — 267/617 = 43.27% sit at 0.5; the `entity_coverage_default_used` flag says 268/617 = 43.44% and the flag agrees with the value on 616 of 617 rows |
| exactly 0.500 on all 120 layman rows | **CONFIRMED** — 120/120 |
| 0.386 (below chance) on recodification | **CONFIRMED** — 0.385669 |

`docs/GAPS.md` #1 and #2 describe the **pre-fix** code (`entity_hits` over
chunks, default 1.0). `agents/retriever.py:110-135` no longer does that and
says so in its own comments. **`GAPS.md` is stale, the Wave 2 correction is
right, and one single log row — `req_id=40bd347de051`, an old
`criminal_unnumbered` run — still carries the pre-fix 1.0 default.** That one
row is the whole of the 0.5 maximum deviation reported in
`entity_coverage_substring_reconstruction_max_abs_dev`.

### 3f. The normaliser artefact rate

Population: **3,302** lines rewritten into `Section N.` form by
`ingest.chunk.SECTION_NORMALISE` across the four source PDFs in `tests/data/`,
extracted with PyMuPDF exactly as `ingest/extract.py` does. Sample: **100**
drawn without replacement, `numpy.random.default_rng(SEED=20260901)`, labels
stored in `NORMALISER_LABELS` in the experiment file. `check06` re-derives the
population 3,302 by two other routes (whole-page `findall`, and counting the
increase in occurrences of the literal `"Section "`).

| class | k / 100 | rate | 95% Wilson CI |
|---|---|---|---|
| GENUINE — the heading of a substantive provision | 36 | 0.360 | [0.273, 0.458] |
| CONTENTS — a row of the front ARRANGEMENT OF SECTIONS index | 47 | 0.470 | [0.375, 0.567] |
| FOOTNOTE — an amendment-footnote marker; the digits are not a section number at all | 17 | 0.170 | [0.109, 0.255] |
| **ARTEFACT (primary, strict) = CONTENTS + FOOTNOTE** | **64** | **0.640** | **[0.542, 0.727]** |
| ARTEFACT (lenient) = FOOTNOTE only | 17 | 0.170 | [0.109, 0.255] |

**Downstream survival.** Of the 64 sampled artefacts, **1** still appears in
Qdrant as a `(corpus, page, section_number)` triple. All 17 FOOTNOTE lines and
46 of the 47 CONTENTS lines were dropped by `is_contents_entry()` and
`footnote_verdict()` before indexing. **Artefact rate at rewrite time 64%;
artefact survival into the index 1/64 = 1.6%.** Both numbers are real and they
answer different questions.

#### Eight-plus real examples of each class

GENUINE — number, title, em-dash, then the provision (or, in the BNS, number
then provision directly):

| doc | page | n | line |
|---|---|---|---|
| a2019-35 | 12 | 5 | `5. Objects of Central Council.—The objects of the Central Council shall be to render advice on…` |
| a2019-35 | 27 | 60 | `60. Review by National Commission in certain cases.—The National Commission shall have the power to review…` |
| a2019-35 | 35 | 97 | `97. Manner of crediting penalty.—The penalty collected under section 21…` |
| BNS | 12 | 26 | `26. Nothing, which is not intended to cause death, is an offence by reason of any harm…` |
| BNS | 51 | 172 | `172. Whoever at an election applies for a voting paper on votes in the name of any other person…` |
| BNS | 58 | 201 | `201. Whoever, being a public servant, and being, as such public servant, charged with the preparation…` |
| IPC | 102 | 415 | `415. Cheating.—Whoever, by deceiving any person, fraudulently or dishonestly induces the person…` |
| IPC | 103 | 420 | `420. Cheating and dishonestly inducing delivery of property.—Whoever cheats and thereby…` |
| CrPC | 115 | 235 | `235. Judgment of acquittal or conviction.—(1) After hearing arguments and points of law…` |
| CrPC | 138 | 313 | `313. Power to examine the accused.—(1) In every inquiry or trial…` |

CONTENTS — right number, no body, immediately followed by the next numbered
title or a CHAPTER heading:

| doc | page | n | line |
|---|---|---|---|
| a2019-35 | 1 | 18 | `18. Powers and functions of Central Authority.` → `19. Power of Central Authority to refer matter…` |
| a2019-35 | 2 | 37 | `37. Reference to mediation.` → `38. Procedure on admission of complaint.` |
| IPC | 2 | 64 | `64. Sentence of imprisonment for non-payment of fine.` → `65. Limit to imprisonment…` |
| IPC | 4 | 140 | `140. Wearing garb or carrying token used by soldier, sailor or airman.` → `CHAPTER VIII` |
| IPC | 10 | 376 | `376. Punishment for rape.` → `376A. Punishment for causing death…` |
| IPC | 13 | 506 | `506. Punishment for criminal intimidation.` → `507. Criminal intimidation by an anonymous communication.` |
| CrPC | 1 | 18 | `18. Special Metropolitan Magistrates.` → `19. Subordination of Metropolitan Magistrates.` |
| CrPC | 5 | 128 | `128. Enforcement of order of maintenance.` |
| CrPC | 15 | 405 | `405. High Court's order to be certified to lower Court.` → `CHAPTER XXXI` |
| CrPC | 18 | 470 | `470. Exclusion of time in certain cases.` → `471. Exclusion of date on which Court is closed.` |

FOOTNOTE — the digits are a footnote marker, not a section number:

| doc | page | n | line |
|---|---|---|---|
| IPC | 15 | 5 | `5. The words "British India" have been successively amended by the A.O. 1948, the A.O. 1950…` |
| IPC | 20 | 8 | `8. The words "the territories comprised in" omitted by Act 48 of 1952, s. 3 and the Second Sch.` |
| IPC | 36 | 6 | `6. The words "or a Lieutenant-Governor" omitted by the A. O. 1937.` |
| IPC | 38 | 10 | `10. Subs. by the A. O. 1950, for "Queen".` |
| IPC | 41 | 2 | `2. Ins. by Act 25 of 2005, s. 44 (w.e.f. 23-6-2005).` |
| IPC | 69 | 1 | `1. Subs. by Act 8 of 1925, s. 2, for s. 292.` |
| IPC | 100 | 2 | `2. Explanation numbered as Explanation 1 by Act 38 of 1975, s. 9 (w.e.f. 1-9-1975).` |
| CrPC | 30 | 2 | `2. Ins. by s. 7, ibid, (w.e.f. 18-12-1978).` |
| CrPC | 130 | 1 | `1. Ins. by Act 25 of 2005, s. 24 (w.e.f. 23-6-2006).` |
| CrPC | 203 | 2 | `2. Subs. by s. 7, ibid. for the word "Ditto", occurring in column 4 relating to s.196…` |

### 3g. The paired check

`experiments/check06_statute_check.py` — **PASSED**, every assertion.

| check | result |
|---|---|
| row count after an independently-written dedupe | 617, matches |
| mean `statute_consistency` at `filtered_n`, server log vs replay | agrees to **0.000000** on every query set |
| chunk-level comparison of the two sources | 6 differing chunks in **5,879** slots = **0.102%**, 5 rows affected — all reported by `req_id` |
| exp06's ablation rows vs published `ablation.csv` | agree to **0.00e+00** on all five signals, pooled and per query set |
| normaliser population by two other regex routes | 3,302 = 3,302 = 3,302 |
| Wilson interval | reproduced |

---

## 4. How to read it

**AUROC** is "pick one query the system got right and one it got wrong at
random; how often does the signal score the right one higher?" 0.5 = a coin
flip. 1.0 = perfect separation. Below 0.5 = the signal is *anti*-informative.

**A 0.500 with a [0.500, 0.500] interval is not a measurement.** It means the
signal was **constant** on those rows. Read the `notes` column: it says so.
Constant-at-1.0 happens whenever the query states no date, because then both
regimes are admissible and nothing can be inconsistent.

**Naive vs clustered intervals.** The naive bootstrap resamples rows. But
three phrasings of one situation share a `pair_id` and are not independent
observations, so the clustered bootstrap resamples *situations*. Usually that
**widens** the interval. Here, on `paired_dated_conflict`, it **narrows** it:
naive [0.782, 0.875] is 0.093 wide, clustered [0.797, 0.867] is 0.070 wide, a
design effect of about **0.75**. That is expected, not a bug — Wave 2 measured
0.79 on this same set. Contrastive variants are *built* to disagree with each
other, which gives negative within-cluster correlation, which shrinks the
variance of a cluster mean. Wave 2 also flagged that clustered AUROC
intervals on restricted `cited`/`grounded` subsets narrowed unexplainably;
treat those rows with caution.

**ECE** (Expected Calibration Error) asks "when the signal says 0.8, is the
system right about 80% of the time?" `statute_consistency` scores 0.319, worse
than `composite` at 0.241 and `max_score` at 0.127. **This is not a defect and
should not be read as one.** `statute_consistency` is a *consistency fraction*,
not a *probability of being right*. It says "everything I fetched is from the
right book", which is necessary but nowhere near sufficient for a correct
answer. Reading it as a probability is a category error; the ECE is reported
because the brief asks for it, with this caveat attached in the CSV `notes`.

**Which stage.** `raw_15` and `reranked_15` are the same 15 chunks in
different orders, so this signal is identical on both. `filtered_n` is the
subset that survived the adaptive threshold and actually reached the model,
and the signal is consistently **weaker** there (0.685 → 0.658 pooled). The
filter throws away low-scoring chunks; when the retrieval went to the wrong
book, the wrong-book chunks are often the *high*-scoring ones, so filtering
concentrates the error rather than removing it.

---

## 5. What this means for the paper

### State it plainly

**Pooled, `statute_consistency` does not beat the generic signals.** It scores
0.685, statistically indistinguishable from the deployed `composite` (+0.021,
p = 0.50) and clearly *worse* than `max_score` (−0.099, p = 0.0002) and
`top_k_mean` (0.757). A headline of "the fourth signal wins" would be false
and must not be written.

**Conditionally, it is the only signal that works at all.** On
`paired_dated_conflict` — the 197 queries where the code the user names and
the date they give point at different statutes — it scores **0.830**, against
`composite` 0.471 and `max_score` 0.656. Paired: **+0.359 over the composite**
(p < 0.0001) and **+0.174 over max_score** (p = 0.0008). Both intervals
exclude zero comfortably. On that set the deployed composite is *below chance*
and the fourth signal is strong.

That is the honest claim, and it is a better claim than "wins on average",
because it comes with a **mechanism**: similarity signals cannot separate two
near-identical texts, and the fourth signal does not use similarity.

### Three structural findings that matter more than the AUROC

**(1) The signal is redundant with the retrieval filter that produced it.**
On **343 of 617 rows** the Qdrant corpus filter the query itself generated is
already inside the admissible set, so every retrieved chunk is admissible *by
construction* and the signal cannot fail. This is why `A5_deployed_date` —
the version using only the era the deployed date module actually output — is
**constant at 1.0 on all 617 rows** and carries zero information. When the
date module ran, it set the retrieval filter; the filter then guaranteed the
consistency the signal was supposed to check.

A confidence signal computed downstream of a filter derived from the same
inputs is a tautology. **The signal earns its keep only where the filter is
derived from something else than the date** — which is exactly the
`paired_dated_conflict` baseline arm, where the filter follows the *named*
code and the date says otherwise. That is the whole of its 0.830.

For the paper this is a design lesson worth stating: *a confidence signal must
be independent of the mechanism it is auditing.*

**(2) The date is the whole signal; the query contributes nothing.**
`A2_date_x_family` is **numerically identical to `A1_date_only` on every one
of the 617 rows**, and `A3_family_only` is constant. The subject-matter family
term does no work here, because the corpus filter already confines retrieval
to one book. If BNSS and BSA were in the corpus this would change. As it
stands, **`statute_consistency` on this corpus is a date-consistency signal
wearing a more general name.**

**(3) It is silent on more than half the evaluation.** On
`generated_retrieval` (198) and `paired_recodification` (99) no query states a
date, so the signal is constant. On `layman_situation` only 60 of 120 state
one, and the pooled layman AUROC is 0.566 with an interval crossing 0.5. The
signal covers **317 of 617 rows** in any informative sense. A deployment would
need a date parser running on every query — which the system has, but only
enabled in one intervention arm.

### The oracle ceiling

`A4_oracle_gold`, which reads the gold `expected_corpora` outright, scores
**0.704** — only 0.019 above the deployable A2's 0.685. **Perfect knowledge of
which statute should answer the question buys almost nothing over what a date
parser already provides.** That is a useful bound: there is no large headroom
being left on the table by an imperfect definition of "implied set".

### The two secondary results

**`entity_coverage` should be computed from the payload, not from chunk
text.** The payload version is better everywhere it differs: +0.0245 AUROC
pooled, **+0.1055** on `generated_retrieval` (0.880 → **0.985**). It changes 18
of 617 rows and every change is downward, because the substring rule can only
over-count. This is a one-line fix to `agents/retriever.py` with a measured
benefit — a clean, small, defensible contribution.

**The normaliser rewrites a table-of-contents row or a footnote marker into
`Section N.` form 64% of the time** [95% CI 54.2%–72.7%], but the downstream
`is_contents_entry()` / `footnote_verdict()` filters catch **63 of those 64**.
The chunking pipeline's front-matter defences are working. Report the 64% as
the rewrite-time rate *with* the 1.6% survival rate; the first number alone
would overstate the harm badly.

---

## 6. What broke while computing this

**Three things broke. All three are recorded, none was worked around.**

**(a) The primary variant turned out to be identical to a simpler one, and
the fully-deployable variant turned out to be constant.** `A2 ≡ A1` on all
617 rows; `A5 ≡ A3` and both constant at 1.0. I had pre-registered five
variants expecting them to separate. They did not. **Nothing was changed in
response.** The pre-registered definition stands, all five are reported, and
`variant_rows_differing` in the CSV records every pairwise identity so a
reader can see it rather than take my word.

**Nothing in this experiment was re-tuned after seeing an AUROC.** No train /
test split was needed, because no definition was adjusted post-hoc. If a
future wave changes the admissible-set rule after reading §3, it must refit on
a train split and report test-split performance only.

**(b) `check06` failed twice before passing, and both failures were mine, not
the data's.**

1. *Dedupe order.* I filtered goldless rows **before** deduplicating;
   `load_logs()` deduplicates first. That gave 620 rows instead of 617 —
   a query whose *last* occurrence has no gold survives one order and not the
   other. Fixed by matching `load_logs()`'s order, with a comment explaining
   why the order is load-bearing.
2. *Signal-name parsing.* `exp04` writes `signal=gap_term = 1-min(...)` in its
   notes; my parser split on `;` and produced the whole expression as a key,
   and separately I forgot to filter `query_set == "ALL"`, so per-query-set
   rows silently overwrote the pooled ones. The first symptom was
   `top_k_mean exp04 0.569172` — the *layman* value masquerading as the
   pooled one. Fixed; the check now also asserts the per-query-set values.

**(c) The `entity_coverage` reconstruction did not match on one row.** Max
absolute deviation 0.5 — traced to `req_id=40bd347de051`, an old
`criminal_unnumbered` run logged **before** `ENTITY_NEUTRAL` replaced the 1.0
default. **Reported, not absorbed:** the CSV names the `req_id`. The other 616
rows reconstruct to 0.0 deviation, which is what makes the payload comparison
trustworthy.

**A documented difference that is not a break.** The server log and the Qdrant
replay disagree on **6 chunks out of 5,879** slots (0.102%, 5 rows). Wave 2
documented one such disagreement in 608 and attributed it to a 5th-decimal
cosine difference flipping two near-tied hits at the adaptive threshold. Five
of the six are one chunk more or fewer *within the same corpus*; one
(`44cd74a7f90e`) swaps a CRPC chunk for a CPA chunk. **The mean
`statute_consistency` is unchanged to six decimals** on every query set,
because the differing chunks fall inside the same admissible set. Every
affected `req_id` is printed by `check06`.

---

## 7. What I could not compute, and why

| wanted | why not |
|---|---|
| `grounded` AUROC per query set | 27 positives in 617 rows. Several sets contain no positive at all, so AUROC is undefined. Emitted as **NOT MEASURED** with the positive/negative counts in `notes`. |
| A truly no-oracle `statute_consistency` on more than 98 rows | The deployed date module ran only in the `both` intervention arm — 98 of 617 rows after dedupe. Everywhere else `date.era` is null and `A5` falls back to UNKNOWN. Recovering the era from `applicable_regime` assumes a **perfect date parser** on 519 rows, which is disclosed rather than hidden. Measuring a real parser would need a re-run, which is out of scope here. |
| Whether the signal helps *in combination* with the other three | Different question from "does it discriminate alone", and it belongs to an ablation over the blend, not here. Nothing in this file changes the deployed 0.55/0.15/0.30 weights, and no reweighting was fitted. |
| A BNSS/BSA-aware admissible set | Neither statute is in the corpus. The PROCEDURE family after 1 July 2024 has **no** admissible member available, which is why the empty-set fallback exists. It never fired on this data, but a corpus that includes the BNSS would exercise it. |
| The 3 rows dropped by the dedupe rule | Disclosed limitation carried forward from Wave 2. 620 gold-labelled rows exist; `load_logs()`'s `(query_id, intervention)` rule keeps 617. Not fixed here, by instruction. |
| Per-chunk attribution of *why* a chunk was inadmissible | The signal is a fraction; it does not record which chunk failed and for which reason (wrong era vs wrong family). Worth adding if this becomes a deployed signal. |
| A clean split of "normaliser artefact" from "cross-reference" as the cause of `entity_coverage` false matches | Measured, and it is the *opposite* of the hypothesis — see §8. |

---

## 8. What surprised me

**1. The false `entity_coverage` matches are not normaliser artefacts at all.
They are cross-references inside genuine provisions.** The task brief
hypothesised that "page numbers and list items produce false matches" through
the `Section N.` rewriting. I inspected all 17 disagreeing rows with extracted
entities. **Every single one is a real section citing another real section.**

| query | asks for | matched chunk | the text that matched |
|---|---|---|---|
| `G0127` | Section 452, 453 | CrPC **454** | `Section 454. Appeal against orders under section 452 or section 453.—` |
| `G0061` | Section 72 | CPA **73** | `Section 73. Appeal against order passed under section 72.—` |
| `G0081` | Section 139 | CrPC **140** | `…where the Magistrate directs a local investigation by any person under section 139…` |
| `G0016` | Section 64 | BNS **199** | `…cognizable offence punishable under section 64, section 65, section 66, section 67…` |
| `P0031` | Section 354A | IPC **354E** | `…an offence under section 354, section 354A, section 354B, section 354C or section 354D…` |

The appeal provision names the provision appealed from. That is how statutes
are written. The substring rule cannot tell "this **is** section 452" from
"this **mentions** section 452", and a genuine 160-year-old drafting
convention, not a PDF-parsing bug, is what breaks it. The payload fix works
for exactly this reason: `section_number` says what a chunk **is**.

**2. The signal is structurally redundant with the mechanism it audits.** I
expected to measure how *well* the fourth signal discriminates. What I found
first is that on 343 of 617 rows it **cannot fail**, because the retrieval
filter was derived from the same query+date. The interesting number
(paired_dated 0.830) comes entirely from rows where the filter followed the
named code while the date said otherwise. This reframes the signal: it is not
a general-purpose consistency check, it is a **disagreement detector between
two things the query says**.

**3. The oracle buys almost nothing.** `A4_oracle_gold` reads the answer key
and scores 0.704 against the deployable 0.685. I expected a much larger gap
and was ready to report "the definition is the bottleneck". It is not — the
bottleneck is coverage (no date on half the queries), not precision of the
admissible set.

**4. The clustered interval is narrower, and that is correct.** On
`paired_dated_conflict` the design effect is ~0.75. My instinct was that
clustering always widens. It does not when variants within a cluster are
*constructed to disagree*: the conflict-IPC-named, conflict-BNS-named and
agree-control variants of one situation deliberately pull opposite ways, which
is negative within-cluster correlation, which shrinks a cluster mean's
variance. Wave 2 saw the same thing at 0.79 on this set.

**5. `entity_coverage` recomputed from the payload reaches 0.985 AUROC on
`generated_retrieval`.** That set is built by generating a query *from* a
section, so "did we retrieve the section the user named" is nearly the whole
of correctness there — and the payload version answers that question almost
perfectly, while the substring version leaks 0.105 of AUROC to cross-reference
false matches. It is the largest single improvement I found, and it is a
three-line change.

**6. The normaliser rewrites far more junk than I expected (64%) and the
pipeline catches almost all of it (63 of 64).** I went in expecting to report
a defect. The defensive filters in `ingest/chunk.py` — `is_contents_entry()`
and `footnote_verdict()`, both of which carry long comments explaining exactly
this problem — are doing their job. The honest report is that the normaliser
is noisy and the chunker is not.

---

## BM25 and hybrid retrieval
Output file: results/hybrid_comparison.csv
Regenerate with: `./venv/Scripts/python.exe experiments/exp07_hybrid.py` (then `./venv/Scripts/python.exe experiments/check07_hybrid_check.py`)
Owner: Wave 3 Subagent 2

---

### 1. ELI5 — what does this measure?

There are two completely different ways to find a paragraph in a pile of documents.

**Dense retrieval** is the one this project already uses. Every chunk of law is turned into a list of 1,536 numbers — a *vector* — that encodes what the chunk *means*. Your question is turned into a vector the same way, and the system returns the chunks whose vectors point in the most similar direction. It is a *meaning* search. It never looks at the literal words. "Punishment for cheating" and "penalty for fraud" land near each other even though they share no word.

**BM25** is the opposite. It is a *word* search — the ranking function behind classic search engines. It only asks: which of the words you typed literally appear in this chunk, how often, and how rare is each word overall? Two ideas do all the work:

| Term | Plain English | Why it matters here |
|---|---|---|
| **term frequency (tf)** | how many times your word appears in this chunk | a chunk that says "assembly" five times is probably about assemblies |
| **inverse document frequency (idf)** | how *rare* the word is across all 1,899 chunks | "the" appears in 1,720 of them and tells you nothing; "sanhita" appears in 30 and tells you almost everything |

BM25 multiplies the two and adds up over your query words, with a correction so that long chunks do not win just by being long.

**Why the paper needs this.** The project's headline finding is that when you ask about **BNS** — the *Bharatiya Nyaya Sanhita*, the new criminal code in force since 1 July 2024 — the system hands you text from the **IPC**, the *Indian Penal Code* it replaced. A reviewer will fire back:

> *"That is not a finding about Indian law. That is a finding about your choice of retriever. A plain word search would tell IPC 420 from BNS 318 instantly. You built the wrong system and called it a discovery."*

The only way to answer that is to **build the word search and run it on the same 1,899 chunks and the same 66 queries** — which is what this experiment does. And because the reviewer's next move is "then just combine the two", it also builds the combination.

**Reciprocal Rank Fusion (RRF)** is that combination. *Rank* means position in a result list: the best result is rank 1, the next is rank 2. RRF ignores the two systems' scores entirely — they are on incomparable scales — and looks only at ranks:

```
score(chunk) = SUM over each list of   1 / (60 + its rank in that list)
```

A chunk at rank 1 in both lists scores 1/61 + 1/61. A chunk at rank 1 in one list and missing from the other scores just 1/61. The constant 60 is not invented here; it is the value from **Cormack, Clarke & Buttcher, SIGIR 2009**, *"Reciprocal Rank Fusion outperforms Condorcet and individual rank learning methods"*. It deliberately flattens the top of each list so one system cannot dictate the answer alone.

Finally, a **confidence interval (CI)** is the honest range around a measured number. "97.0% [84.7, 99.5]" means: we saw 32 successes out of 33, and if we could repeat this with fresh queries of the same kind, the true rate is plausibly anywhere from 84.7% to 99.5%. Thirty-three queries cannot pin down a percentage to one decimal place, and the interval says so out loud.

---

### 2. Technically

**The setup, identical for all three arms.**

| Element | Value |
|---|---|
| Index | Qdrant collection `legal_mvp`, 1,899 chunks, scrolled READ-ONLY |
| Corpus shares | CrPC 39.1% · IPC 31.3% · BNS 22.3% · CPA 7.3% |
| Corpus filter | **DISABLED** in every arm (see below) |
| Query text | **raw** query, not the Router's `rewritten_query` |
| Retrieval depth | top 50 per arm — fusion input only |
| Evaluation window | top **15 chunks**, so every number here is comparable with the existing top-15 tables |
| Dense | `text-embedding-3-small`, 1536-d, cosine |
| BM25 | `rank_bm25.BM25Okapi`, k1=1.5, b=0.75, epsilon=0.25 (library defaults) |
| Fusion | RRF, k=60, Cormack et al. SIGIR 2009 |
| Seed / resamples | SEED=20260901, N_BOOT=10,000, imported from `metrics_lib` |

**Why the filter is off.** The Router reads the Act name out of the query and applies a hard Qdrant filter. With it on, an IPC-named query *cannot* return a BNS chunk, so the confusion matrix is guaranteed clean before any retrieval happens — the reason `scripts/ablate_filter.py` exists. BM25 has no filter concept at all. "Filter off" is therefore the only condition under which the three arms are the same experiment.

**Tokenisation — the crux.** BM25 sees only tokens. A tokeniser that strips numerals turns `Section 318(4)` into `section` and deletes the only signal that distinguishes one provision from another. The rule used here:

1. Lowercase; normalise the corpus's stray unicode dashes and quotes to ASCII (the PDFs contain `—` and a replacement character `�` that would otherwise fuse two words).
2. Scan for two token shapes, numerics preferred:
   - **numeric** — `\d+[a-z]{0,2}(?:\([0-9a-z]+\))*` — digits, then up to two letters, then any number of parenthesised groups.
   - **alphabetic** — `[a-z]+`.
   Everything else is a separator.
3. **Expand** each numeric token into its statutory ancestors. The subsection digit *alone* is not emitted.

| Input | Tokens produced |
|---|---|
| `Section 318(4).` | `section`, `318(4)`, `318` |
| `What is BNS 304B?` | `what`, `is`, `bns`, `304b`, `304` |
| `Section 41A CrPC` | `section`, `41a`, `41`, `crpc` |
| `s. 498A(1)(b)` | `s`, `498a(1)(b)`, `498a(1)`, `498a`, `498` |
| `Punishment for murder under Section 302 IPC` | `punishment`, `for`, `murder`, `under`, `section`, `302`, `ipc` |
| `Section 373. Appeal from orders requiring security—Any person,—` | `section`, `373`, `appeal`, `from`, `orders`, `requiring`, `security`, `any`, `person` |

**Why expand.** Section headings in the corpus are written bare — `Section 318.` — while queries and cross-references write `Section 318(4)`. Without expansion those two share no token and BM25 scores the correct chunk at exactly zero on the one term that identifies it. Expansion is applied identically to documents and to queries, so the match stays symmetric.

**Why not emit the bare subsection digit.** `4` appears in a large fraction of the 1,899 chunks. Its idf is near zero, so it can contribute almost nothing to the score while adding noise to the length normalisation. Dropping it costs no recall — the parent number `318` already localises the section — and keeps the query terms readable when debugging.

The resulting index: 1,899 documents, 6,355 distinct tokens, mean 156.3 tokens per chunk.

**Provenance, stated because a mixed table that hides it is worse than a slow honest one.** No recorded dense result matched the required conditions: the runs in `runs/` embedded the Router's `rewritten_query` (the query with LLM-extracted legal issues prefixed) and applied a corpus filter. Both are unavailable to BM25 and neither is what `ablate_filter.py` did. **The dense arm was therefore re-run fresh**, on raw query text with no filter. Every dense row in the CSV says so in `notes`, and the recorded numbers are emitted alongside under the separate metric name `recall_at_k_recorded_raw15` so the size of the difference is visible rather than buried.

One consequence worth stating: `paired_dated_conflict` is **99 queries here, not 197 rows**. Reading `app.py`, the date/mapper intervention acts *only* by rewriting `plan.target_corpora` — i.e. only through the corpus filter. With the filter disabled the two conditions are literally the same retrieval, so the 0.293 / 0.694 split has no counterpart in this table. Pooled `n` is 518 unique queries, not 617 logged rows.

---

### 3. What the number came out as

#### 3a. THE HEADLINE — does naming an Act get you that Act's text?

66 numbered paired queries, corpus filter disabled, top 15. *Dominant corpus* = which statute supplied most of the 15 chunks. Chance = that statute's share of the index.

| Query names | Arm | IPC | BNS | CrPC | CPA | **Correct** | 95% Wilson | Cluster CI | Chance |
|---|---|--:|--:|--:|--:|--:|---|---|--:|
| **IPC** | dense | **32** | 1 | 0 | 0 | **97.0%** | [84.7, 99.5] | [90.9, 100.0] | 31.3% |
| **IPC** | bm25 | 0 | 0 | **33** | 0 | **0.0%** | [0.0, 10.4] | [0.0, 0.0] | 31.3% |
| **IPC** | hybrid_rrf | 15 | 1 | 17 | 0 | **45.5%** | [29.8, 62.0] | [27.3, 63.6] | 31.3% |
| **BNS** | dense | 16 | **17** | 0 | 0 | **51.5%** | [35.2, 67.5] | [33.3, 69.7] | 22.3% |
| **BNS** | bm25 | 1 | **32** | 0 | 0 | **97.0%** | [84.7, 99.5] | [90.9, 100.0] | 22.3% |
| **BNS** | hybrid_rrf | 7 | **26** | 0 | 0 | **78.8%** | [62.2, 89.3] | [63.6, 90.9] | 22.3% |

Same 66 queries, single top-scoring chunk only:

| Query names | Arm | IPC | BNS | CrPC | CPA | **Top-1 correct** | 95% Wilson | Cluster CI | Chance |
|---|---|--:|--:|--:|--:|--:|---|---|--:|
| **IPC** | dense | **30** | 3 | 0 | 0 | **90.9%** | [76.4, 96.9] | [78.8, 100.0] | 31.3% |
| **IPC** | bm25 | 15 | 0 | 18 | 0 | **45.5%** | [29.8, 62.0] | [30.3, 63.6] | 31.3% |
| **IPC** | hybrid_rrf | **29** | 1 | 3 | 0 | **87.9%** | [72.7, 95.2] | [75.8, 97.0] | 31.3% |
| **BNS** | dense | 19 | 14 | 0 | 0 | **42.4%** | [27.2, 59.2] | [24.2, 60.6] | 22.3% |
| **BNS** | bm25 | 5 | **28** | 0 | 0 | **84.8%** | [69.1, 93.3] | [72.7, 97.0] | 22.3% |
| **BNS** | hybrid_rrf | 11 | **22** | 0 | 0 | **66.7%** | [49.6, 80.2] | [48.5, 81.8] | 22.3% |

**The number that matters: BNS-named accuracy moves off 51.5%, and it moves UP.**

| Arm | BNS-named dominant | Change vs dense | BNS-named top-1 | Change vs dense |
|---|--:|--:|--:|--:|
| dense | 51.5% [35.2, 67.5] | — | 42.4% [27.2, 59.2] | — |
| bm25 | **97.0%** [84.7, 99.5] | **+45.5 pts** | **84.8%** [69.1, 93.3] | **+42.4 pts** |
| hybrid_rrf | 78.8% [62.2, 89.3] | +27.3 pts | 66.7% [49.6, 80.2] | +24.2 pts |

And the cost, on the same 66 queries:

| Arm | IPC-named dominant | Change vs dense |
|---|--:|--:|
| dense | 97.0% [84.7, 99.5] | — |
| bm25 | **0.0%** [0.0, 10.4] | **−97.0 pts** |
| hybrid_rrf | 45.5% [29.8, 62.0] | −51.5 pts |

#### 3b. Gold-section Recall@15, MRR@15, nDCG@15, per query set

*Recall@k* = share of queries where at least one gold section appeared in the top k. *MRR* (mean reciprocal rank) = average of 1/(position of the first correct hit). *nDCG@k* = the same idea with a gentler log discount. All under the `retrieved@k` correctness definition, `metrics_lib` rank convention (chunks with no `section_number` are dropped — 406 of the 1,899 have none).

| Query set | n | Arm | **Recall@15** | 95% Wilson | Cluster CI | MRR@15 | nDCG@15 |
|---|--:|---|--:|---|---|--:|--:|
| generated_retrieval | 200 | dense | 0.645 | [0.577, 0.708] | [0.601, 0.687] | 0.5773 | 0.5943 |
| generated_retrieval | 200 | bm25 | 0.635 | [0.566, 0.699] | [0.573, 0.695] | 0.4572 | 0.4995 |
| generated_retrieval | 200 | hybrid_rrf | **0.650** | [0.582, 0.713] | [0.605, 0.693] | 0.5238 | 0.5539 |
| paired_recodification | 99 | dense | **0.737** | [0.643, 0.814] | [0.687, 0.798] | 0.5495 | 0.5945 |
| paired_recodification | 99 | bm25 | 0.576 | [0.477, 0.668] | [0.455, 0.687] | 0.3965 | 0.4399 |
| paired_recodification | 99 | hybrid_rrf | 0.717 | [0.622, 0.796] | [0.657, 0.778] | **0.5804** | **0.6138** |
| paired_dated_conflict | 99 | dense | **0.697** | [0.600, 0.779] | [0.616, 0.768] | 0.4429 | 0.5034 |
| paired_dated_conflict | 99 | bm25 | 0.434 | [0.341, 0.533] | [0.323, 0.556] | 0.2190 | 0.2695 |
| paired_dated_conflict | 99 | hybrid_rrf | 0.616 | [0.518, 0.706] | [0.505, 0.717] | 0.4114 | 0.4618 |
| layman_situation | 120 | dense | **0.150** | [0.097, 0.225] | [0.033, 0.275] | 0.0514 | 0.0740 |
| layman_situation | 120 | bm25 | 0.025 | [0.009, 0.071] | [0.000, 0.075] | 0.0111 | 0.0147 |
| layman_situation | 120 | hybrid_rrf | 0.108 | [0.064, 0.177] | [0.025, 0.208] | **0.0610** | 0.0725 |
| **ALL (pooled)** | 518 | dense | **0.558** | [0.515, 0.600] | [0.503, 0.610] | 0.4245 | 0.4564 |
| **ALL (pooled)** | 518 | bm25 | 0.444 | [0.402, 0.487] | [0.387, 0.501] | 0.2967 | 0.3319 |
| **ALL (pooled)** | 518 | hybrid_rrf | 0.531 | [0.488, 0.573] | [0.476, 0.583] | 0.4059 | 0.4362 |

Recall@k across k, compressed convention:

| Query set | Arm | k=1 | k=3 | k=5 | k=10 | k=15 |
|---|---|--:|--:|--:|--:|--:|
| generated_retrieval | dense | 0.525 | 0.625 | 0.630 | 0.645 | 0.645 |
| generated_retrieval | bm25 | 0.375 | 0.515 | 0.545 | 0.625 | 0.635 |
| generated_retrieval | hybrid_rrf | 0.470 | 0.570 | 0.600 | 0.645 | 0.650 |
| paired_recodification | dense | 0.465 | 0.636 | 0.667 | 0.727 | 0.737 |
| paired_recodification | bm25 | 0.303 | 0.485 | 0.505 | 0.566 | 0.576 |
| paired_recodification | hybrid_rrf | **0.505** | 0.626 | **0.687** | 0.717 | 0.717 |
| paired_dated_conflict | dense | 0.313 | 0.545 | 0.596 | 0.657 | 0.697 |
| paired_dated_conflict | bm25 | 0.131 | 0.263 | 0.313 | 0.414 | 0.434 |
| paired_dated_conflict | hybrid_rrf | 0.293 | 0.515 | 0.566 | 0.616 | 0.616 |
| layman_situation | dense | 0.025 | 0.058 | 0.100 | 0.133 | 0.150 |
| layman_situation | bm25 | 0.000 | 0.025 | 0.025 | 0.025 | 0.025 |
| layman_situation | hybrid_rrf | **0.042** | **0.075** | 0.100 | 0.108 | 0.108 |
| ALL | dense | 0.357 | 0.481 | 0.508 | 0.544 | 0.558 |
| ALL | bm25 | 0.228 | 0.347 | 0.373 | 0.434 | 0.444 |
| ALL | hybrid_rrf | 0.344 | 0.456 | 0.494 | 0.529 | 0.531 |

`recall_at_k_fraction_of_gold` (mean fraction of a query's gold sections found, for the 91 queries carrying 2–3 gold sections) and the `*_positional` rank convention are in the CSV as separate metric rows.

#### 3c. THE CEILING — found while running this, and it bounds everything above

| Query set | Gold reachable in the index | 95% Wilson |
|---|--:|---|
| generated_retrieval | 200/200 = 1.000 | [0.981, 1.000] |
| paired_recodification | 75/99 = 0.758 | [0.665, 0.831] |
| — IPC-named | 31/33 = 0.939 | [0.804, 0.983] |
| — **BNS-named** | **11/33 = 0.333** | [0.198, 0.504] |
| — neutral-topic | 33/33 = 1.000 | [0.896, 1.000] |
| paired_dated_conflict | 73/99 = 0.737 | [0.643, 0.814] |
| layman_situation | 96/120 = 0.800 | [0.720, 0.862] |
| **ALL pooled** | **444/518 = 0.857** | [0.824, 0.885] |

22 of the 33 BNS-named gold labels are **subsection** references — `BNS 103(1)`, `BNS 318(4)`, `BNS 356(2)` — while the index records only the bare section number, `103`, `318`, `356`. `metrics_lib.same_section()` is strict by default (its own docstring warns that lenient matching over-counts: `498A` would collapse onto `498`, a different offence), so those 22 queries **cannot be scored correct by any retriever**.

Gold-**section** recall on the paired set, split by variant, read against that ceiling:

| Variant | Ceiling | dense | bm25 | hybrid_rrf |
|---|--:|--:|--:|--:|
| IPC-named | 31/33 = 0.939 | 29/33 = 0.879 | 24/33 = 0.727 | 27/33 = 0.818 |
| **BNS-named** | **11/33 = 0.333** | **11/33 = 0.333** | 10/33 = 0.303 | **11/33 = 0.333** |
| neutral-topic | 33/33 = 1.000 | 33/33 = 1.000 | 23/33 = 0.697 | 33/33 = 1.000 |

On BNS-named queries, dense and hybrid retrieve **100% of what is retrievable**. The 0.333 is the gold labels' ceiling, not the retriever's failure.

#### 3d. Provenance contrast — recorded vs fresh dense

| Query set | Recorded dense `raw_15` (filter ON, rewritten query) | Fresh dense here (filter OFF, raw query) |
|---|--:|--:|
| generated_retrieval | 0.692 (n=198) | 0.645 (n=200) |
| paired_recodification | 0.737 (n=99) | **0.737** (n=99) |
| paired_dated_conflict | 0.492 (n=197 rows, both conditions pooled) | 0.697 (n=99 queries) |
| layman_situation | 0.150 (n=120) | **0.150** (n=120) |

#### 3e. Cost

| Item | Value |
|---|--:|
| Queries embedded | 518 unique (4 reported sets) |
| Tokens charged by the endpoint | **13,375** |
| Price | $0.02 / 1M (`text-embedding-3-small`) |
| Cost | **$0.000268 ≈ ₹0.024** |
| Generation (LLM answer) calls | **0** |

---

### 4. How to read it

**A worked example, before any abstraction.** Query **P0002**, a real BNS-named query where dense retrieval fails and BM25 does not:

> *"What is the punishment for unlawful assembly - common object under Section 190 of the Bharatiya Nyaya Sanhita?"*  — gold: `BNS 190`

| Rank | **Dense** (meaning) | **BM25** (words) | **Hybrid RRF** |
|--:|---|---|---|
| 1 | IPC 143 — Punishment.—Whoever is a member of an unlawful assembly… | **BNS 190** — If an offence is committed by any member of an unlawful assembly… | **BNS 190** |
| 2 | IPC 149 — Every member of unlawful assembly guilty of offence… | IPC 149 | IPC 149 |
| 3 | **BNS 190** | IPC 146 — Rioting… | IPC 141 |
| 4 | IPC 141 — Unlawful assembly.—An assembly of five or more persons… | IPC 141 | BNS 189 |
| 5 | BNS 189 | BNS 189 | IPC 146 |

Dense understands the *situation* perfectly — every one of its five results is about unlawful assembly — and then hands back the **repealed** IPC version at ranks 1, 2 and 4. It has no idea that "Bharatiya Nyaya Sanhita" is a *name* rather than a topic. BM25 does: `sanhita` has idf 4.12 and occurs in exactly 30 chunks, all of them BNS.

The fusion arithmetic, term by term, k=60:

| Chunk | Dense rank | BM25 rank | RRF score | Fused rank |
|---|--:|--:|--:|--:|
| **BNS 190** | 3 | 1 | 1/63 + 1/61 = **0.032266458** | **1** |
| IPC 149 | 2 | 2 | 1/62 + 1/62 = 0.032258065 | 2 |
| IPC 141 | 4 | 4 | 1/64 + 1/64 = 0.031250000 | 3 |
| BNS 189 | 5 | 5 | 1/65 + 1/65 = 0.030769231 | 4 |
| IPC 146 | 17 | 3 | 1/77 + 1/63 = 0.028860029 | 5 |

The correct chunk wins by **0.0000084**. That is how narrow the hybrid's victory is on this query, and it is a fair warning about how much weight the hybrid column can carry.

**Now the mechanism, and it is not what you would guess.** BM25's asymmetry is a fact about **drafting style**, measurable directly in the index:

| Token | Total chunks | IPC | BNS | CrPC | CPA | idf |
|---|--:|--:|--:|--:|--:|--:|
| `sanhita` | 30 | 0 | **30** | 0 | 0 | 4.12 |
| `bharatiya` | 8 | 0 | **8** | 0 | 0 | 5.41 |
| `nyaya` | 2 | 0 | **2** | 0 | 0 | 6.63 |
| `penal` | 110 | 23 | 2 | **82** | 3 | 2.79 |
| `indian` | 129 | 29 | 2 | **95** | 3 | 2.62 |
| `code` | 303 | 60 | 1 | **231** | 11 | 1.66 |

- The BNS **names itself** in its own operative text — "any section of this **Sanhita**". Those three tokens occur nowhere else in the corpus. Type "Bharatiya Nyaya Sanhita" and BM25 goes straight to the BNS.
- The IPC (1860) **never names itself**. The phrase "Indian Penal Code" appears in this corpus overwhelmingly inside the *Code of Criminal Procedure*, as cross-references — "an offence under the Indian Penal Code". So typing the Act's own name is, to a word search, a **CrPC-identifying phrase**. All 33 IPC-named queries have CrPC supply the plurality of their top 15. That is the 0.0%.

**But read the 0.0% carefully — it is a tail effect, not a head effect.** Query **P0001** (`Section 149 of the Indian Penal Code`, gold `IPC 149`):

| Rank | BM25 result |
|--:|---|
| 1 | **IPC 149** ✓ |
| 2 | BNS 190 |
| 3 | IPC 146 |
| 4 | IPC 141 |
| 5 | BNS 189 |
| … | ranks 6–15 fill with CrPC cross-reference chunks |

Top-15 composition: CrPC 8, BNS 4, IPC 3 → **dominant = CrPC = wrong**, even though rank 1 was right. This is exactly why BM25's IPC-named score is 0.0% on *dominant* but 45.5% on *top-1*, and why gold-section Recall@15 for the same queries is 24/33 = 0.727. **The dominant-corpus measure is a coarse instrument.** Report the two together or not at all.

**Reading the clustered intervals.** The 33 situations each appear as several phrasings, so the phrasings are not independent observations; `cluster_bootstrap()` resamples *situations*, not rows. As Wave 2 found, this does **not** always widen the interval here, because contrastive variants are built to disagree:

| Row | Naive width | Clustered width | Design effect |
|---|--:|--:|--:|
| IPC-named, dense, dominant | 0.148 | 0.091 | 0.62 |
| BNS-named, bm25, dominant | 0.148 | 0.091 | 0.62 |
| BNS-named, dense, dominant | 0.323 | 0.364 | 1.13 |
| BNS-named, hybrid, dominant | 0.271 | 0.273 | 1.01 |
| **All 66, bm25, dominant** | **0.234** | **0.045** | **0.19** |

That last row is the extreme case and it is not a bug. BM25 gets *exactly one* of each pair right — the BNS half always, the IPC half never — so every single one of the 33 situations contributes exactly 1/2. Resampling situations therefore produces almost no variance: the clustered interval is [0.455, 0.500] against a naive [0.368, 0.603]. Perfect negative within-cluster correlation, by construction.

**Two ordinary cautions.** Within the IPC-named and BNS-named subgroups each `pair_id` occurs exactly once, so the cluster bootstrap degenerates to an ordinary row bootstrap there — read the two intervals as one. And 33 is a small n: an interval like [62.2, 89.3] is genuinely 27 points wide.

---

### 5. What this means for the paper

**The objection, stated fairly:** *"An exact-word search would separate IPC 420 from BNS 318 trivially. Your cross-statute failure is an artefact of choosing a dense retriever, not a property of the recodification."*

**The answer is: partly right, and the part it gets right makes the paper better, not worse.**

**(i) On BNS-named queries the reviewer is correct, and it should be conceded in plain terms.** BM25 takes BNS-named dominant-corpus accuracy from **51.5% [35.2, 67.5] to 97.0% [84.7, 99.5]**, +45.5 points, intervals not remotely overlapping. Top-1 goes 42.4% → 84.8%. Naming the new code *does* carry a usable literal signal, and the dense retriever throws it away. Stated at its strongest: **the dense retriever is a bad choice for this task, and the paper should say so.**

**(ii) But the failure does not vanish — it moves.** BM25 destroys the other half. IPC-named dominant accuracy collapses from **97.0% to 0.0% [0.0, 10.4]**, below the 31.3% chance rate, 33 out of 33 queries landing in the *Code of Criminal Procedure*. On the full 66, BM25 scores 32/66 = 48.5% against dense's 49/66 = 74.2%. Neither retriever handles both statutes. That is a stronger claim than "dense retrieval is bad", and it is the claim to lead with.

**(iii) The hybrid does not rescue it either.** RRF lands between the two on the measure each arm dominates — BNS-named 78.8%, IPC-named 45.5% — and 62.1% overall, *below* dense's 74.2%. Fusion averages the two failure modes; it does not cancel them. On pooled gold-section Recall@15 the hybrid is 0.531 [0.488, 0.573] against dense 0.558 [0.515, 0.600]: no gain, and a loss on the layman set (0.108 vs 0.150).

**(iv) The mechanism is the actual contribution, and it is about legal drafting, not about retrievers.** The reason no lexical method can fix this is measurable in six numbers:

> The **BNS names itself** in its own operative text (`sanhita`: 30 chunks, all BNS). The **IPC does not** — the phrase "Indian Penal Code" appears in this corpus mostly inside the *CrPC*, as cross-references (`penal`: 82 CrPC chunks vs 23 IPC). So a word search follows "Bharatiya Nyaya Sanhita" to the BNS and follows "Indian Penal Code" to the Code of Criminal Procedure.

This generalises past this corpus and past this system. During a recodification, the **new** statute is lexically self-identifying and the **old** one is identifiable only through the cross-references that other statutes make to it — and those cross-references live in the *wrong* document. Retrieval over a mixed-vintage statute book is asymmetrically hard *by construction*, and the asymmetry flips depending on whether your retriever reads meaning or words. That is a finding about Indian legal recodification that no choice of retriever removes.

**(v) The honest framing for the paper.** Not *"dense retrieval confuses the IPC and the BNS"*. Instead:

> *Neither dense nor lexical retrieval can reliably route a query to the correct code across a recodification boundary, and fusing them does not help. Dense retrieval fails on the new code (51.5% [35.2, 67.5]); lexical retrieval fails catastrophically on the repealed code (0.0% [0.0, 10.4]); RRF fusion lands between the two and is worse overall than dense alone (62.1% vs 74.2%). The failures have different causes — semantic near-identity of recodified provisions on one side, asymmetric self-naming in statutory drafting on the other — so no reweighting of the same two signals fixes both. What the task needs is an explicit statute-and-date resolution layer, which is exactly what the Phase H mapper is.*

**(vi) An independent argument for that layer.** The corpus filter, when it is *correct*, already gives near-perfect corpus routing. Everything measured here is what happens when it is off. The experiment therefore says: **the routing decision must be made deliberately, not inferred from similarity or from word overlap.** That is a design conclusion the paper can defend with these numbers.

**(vii) A caveat that must travel with every recall number.** Only 444 of 518 gold labels (85.7%) are reachable at all under strict section identity, and on BNS-named queries only 11 of 33 (33.3%) are, because 22 gold labels name subsections (`BNS 318(4)`) that the index records only as bare sections (`318`). Dense and hybrid both achieve **11/33 — the entire ceiling**. Any recall figure on that subset must be quoted against 0.333 and not against 1.0, or it will read as a 67-point failure that is entirely an artefact of label granularity. This is a gold-label / ingestion issue, not a retrieval one, and it is reported rather than repaired — patching the gold would be exactly the thing this project's conventions forbid.

---

### 6. What broke while computing this

| # | What | Resolution |
|---|---|---|
| 1 | **The gold-reachability ceiling was not known before this run.** BNS-named gold-section recall looked like a 0.333 catastrophe across all three arms. It is not: 22 of 33 gold labels name a subsection the index does not record, so 0.333 *is* the ceiling and dense/hybrid saturate it. | Not a code fault. Added `gold_reachable_ceiling` rows to the CSV and check C6 in `check07_hybrid_check.py` asserting no arm exceeds its set's ceiling. Nothing was patched. |
| 2 | **BM25's IPC-named 0.0% initially looked like a tokenisation bug.** Zero out of thirty-three is the kind of number that usually means a broken index. | It is real, and the cause was confirmed by direct token counts (`penal` in 82 CrPC chunks vs 23 IPC). The independent re-implementation in C4 reproduces 0/33 exactly. |
| 3 | **The dense arm could not reuse recorded results.** `runs/` embedded `rewritten_query` with a corpus filter applied; neither condition is available to BM25 nor matches `ablate_filter.py`. | Re-ran dense fresh on raw text with no filter, disclosed in `notes` on every dense row, and emitted the recorded values separately as `recall_at_k_recorded_raw15`. |
| 4 | Qdrant point ids are UUIDs, not integers, so BM25 document indices and Qdrant ids needed an explicit map. | Documents sorted on `chunk_id` before indexing, giving a stable index that reproduces without being stored. |

Nothing failed silently, nothing was worked around, and `pytest tests/ -q` is **237 passed** — unchanged from baseline.

**All 17 paired checks pass**, including: BM25 index = exactly 1,899 documents; corpus shares matching `ablate_filter.py`'s chance baseline to 3 decimals; a hand-computed 4-document RRF toy (`[d1,d2,d3]` ⊕ `[d3,d1,d4]` → `d1,d3,d2,d4`) matching the code; RRF of a single list being the identity on toys *and* on all 66 real dense result lists; a second tokeniser written as a character scan rather than a regex agreeing with the first on 52 real chunks and all six documented examples; a second BM25 written out from the Okapi formula in plain Python reproducing 32/33 and 0/33 exactly; and the dense arm reproducing `ablate_filter.py`'s published 32/33, 17/33, 30/33, 14/33 to the query.

### 7. What I could not compute, and why

| Not computed | Why |
|---|---|
| **Whether BM25 fixes the gold-SECTION failure on BNS-named queries** — **NOT MEASURED** | Capped at 11/33 by the label-granularity ceiling in §3c. The corpus-level headline is measurable; the section-level one is not, on this subset, with these labels. |
| **Lenient (subsection→parent) recall** | `metrics_lib.recall_at_k` calls `same_section` strictly and exposes no `lenient` flag. Reimplementing it locally is forbidden by the standing rules. Reported the ceiling instead, which conveys the same information without a second identity rule. |
| **BM25 parameter sensitivity (k1, b)** | Library defaults only. Tuning them on this data would be fitting the retriever to the result. |
| **RRF k sensitivity** | Fixed at 60 per Cormack et al. Same reason. |
| **Weighted RRF** | Weighting the arms needs a held-out set to fit the weight on; with 33 queries per cell there is no room to split one. |
| **A BM25 arm with the corpus filter ON** | BM25 has no filter concept and the whole point was to remove it. |
| **paired_dated_conflict split by intervention** | Correctly absent: with the filter disabled the intervention is a no-op for retrieval (it acts only via `plan.target_corpora`). 99 queries, one result each. |
| **The 58-query legacy `eval/queryset.jsonl`** | Excluded to stay comparable with exp01's four reported sets. |
| **Answer-level metrics (`cited`, `grounded`)** | Zero generation calls by instruction. This is a retrieval experiment. |

### 8. What surprised me

1. **BM25 does not fix the failure — it inverts it.** The expected outcome was a modest improvement or none. Instead the two retrievers fail on *opposite* halves of the same 66 queries: dense 97.0/51.5 (IPC/BNS), BM25 0.0/97.0. The reviewer's objection turns out to be half right, and taking it seriously produced a better paper than defending against it would have.

2. **The IPC cannot be found by its own name.** `penal` appears in 82 CrPC chunks and 23 IPC chunks; `indian` in 95 and 29. A statute does not name itself in its operative text, so the phrase "Indian Penal Code" is, lexically, a *Code of Criminal Procedure* phrase. Meanwhile the 2023 BNS *does* name itself — "this Sanhita" — and nothing else in the corpus cites it yet, because it is new. The whole asymmetry falls out of drafting convention plus the age of the statute.

3. **Fusion made things worse overall.** RRF is usually a free win in the IR literature. Here it is 62.1% against dense's 74.2% on the headline and 0.531 vs 0.558 on pooled Recall@15. Averaging two systems that fail on complementary halves gives you a system that fails on both halves a bit.

4. **The RRF margins are tiny.** On P0002 the correct chunk beat the wrong one by 0.0000084. RRF scores live in a band about 0.016 wide with differences four orders of magnitude smaller; a single rank change anywhere reorders the top of the list.

5. **Two fresh dense numbers landed exactly on the recorded ones.** `paired_recodification` 0.737 and `layman_situation` 0.150, identical to the recorded `raw_15` values despite a different query text (raw vs rewritten) and a different filter setting. Coincidence at the aggregate level, not identity at the query level — but it is a reassuring sign that the fresh dense arm is the same retriever the project has been measuring all along.

6. **The clustered interval collapsed to almost nothing** on the pooled 66 BM25 row — [0.455, 0.500] against a naive [0.368, 0.603], design effect 0.19. It looks broken and is exactly right: BM25 scores precisely one of every pair correct, so every situation contributes the identical 1/2 and there is nothing left to resample.

7. **A third of the paired gold is unreachable by construction** and the project appears not to have known. That number bounds every recall figure on that set and needed finding before any of them are quoted in a paper.
