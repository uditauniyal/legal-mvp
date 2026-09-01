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
