# SCHEMA.md — what the data actually contains

**Wave 0, Task A.** 1 September 2026. Branch `metrics/sept-01`, clean tree, 142 tests passing at baseline.

Everything below was read from the real files. Nothing is taken from documentation.

**Three findings block parts of the plan as written.** They are marked BLOCKER and explained in section 6. Read that section before starting Task B.

---

## 1. The files

| Path | Files | Rows | What it is |
|---|---|---|---|
| `runs/<stamp>_<sha>/queries.jsonl` | 8 | **859** (859 unique `req_id`) | Written by the **server**, one record per query, 80 fields |
| `runs/eval_<stamp>_<sha>/eval_summary.jsonl` | 8 | **850** (only **521 unique** `query_id`) | Written by the **runner**, carries the gold labels |
| `eval/*_queryset.jsonl` | 5 | 576 | The query sets with gold sections |

The plan referred to `logs/`. That directory does not exist. The data is in **`runs/`**, which is gitignored and exists only on this machine plus `backup/pre-metrics/`.

---

## 2. Server log — `runs/<stamp>/queries.jsonl`

80 fields across 10 buckets. Full list with a real example value:

```
req_id                                    str    08c43909b308
timestamp                                 str    2026-08-23T04:26:46+05:30
query_id                                  str    D0094
query_raw                                 str    What is the punishment for criminal intimid...
git_sha                                   str    302e1f8

intake.scenario                           str    Criminal Intimidation Penalty
intake.persona                            str    Paralegal
intake.urgency                            str    Deferred
intake.complexity                         str    Low
intake.financial_status                   str    Unknown
intake.domain                             str    General
intake.issues                             list   []
intake.missing_facts                      list   ['Exact nature of the threat...']
intake.llm_ok                             bool   True
intake.fallback_used                      bool   False
intake.llm_error                          None

date.mode                                 str    both
date.era                                  str    BNS_ERA
date.resolved                             str    2026-07-23
date.evidence                             str    last month
date.rule                                 str    last_unit
date.ambiguous                            bool   False

router.target_corpus                      str    IPC
router.decision_path                      str    act_map_single
router.intent                             str    statute
router.entities                           list   ['Section 506']
router.boost_terms                        list   ['Section 506', 'Section 506.']
router.rewritten_query                    str    Section 506 What is the punishment...

mapper.mode                               str    both
mapper.target_corpora                     list   ['BNS']
mapper.original                           list   ['IPC 506']
mapper.governing                          list   ['BNS 351(2)', 'BNS 351(3)']
mapper.changed                            bool   True
mapper.rule                               str    translated_to_governing_code
mapper.warnings                           list   []
mapper.notes                              list   ['IPC 506: Split by severity.']

retrieval.filter_applied                  str    BNS
retrieval.filter_fallback_fired           bool   False
retrieval.n_retrieved                     int    15
retrieval.n_after_filter                  int    15
retrieval.scores_raw                      list   [0.612176, 0.562985, ...]
retrieval.max_score                       float  0.6122
retrieval.embed_provider                  str    OpenAI
retrieval.named_statutes                  list   ['IPC']
retrieval.unavailable_statutes            list   []
retrieval.partial_corpus_coverage         bool   False
retrieval.chunks                          list   [{doc, page, corpus, score, text_head}, ...]

confidence.top_k_mean                     float  0.5721
confidence.score_gap                      float  0.0511
confidence.entity_coverage                float  0.0
confidence.entity_coverage_default_used   bool   False
confidence.composite                      float  0.4391
confidence.refused                        bool   False
confidence.refusal_reason                 None

answer.refused                            bool   False
answer.prompt_variant                     str    HIGH          <- ALWAYS "HIGH". This is the tier bug.
answer.llm_ok                             bool   True
answer.llm_error                          None
answer.provider_name                      str    Google AI Studio
answer.model                              str    google/gemini-3.7-flash
answer.prompt_tokens                      int    3114
answer.completion_tokens                  int    2728
answer.answer_text                        str    (full answer)
answer.citations                          list   [{source, page, snippet}, ...]
answer.report_url                         str    /static/report_52641968.pdf

verifier.cited                            list   ['BNS Section 351', 'IPC Section 506', ...]
verifier.grounded                         list   ['BNS Section 351']
verifier.ungrounded                       list   ['IPC Section 506', ...]
verifier.out_of_corpus                    list   ['BNSS Section 173']
verifier.vintage_mismatches               list   [{cited, corpus_has, relation}, ...]
verifier.n_cited                          int    6
verifier.n_grounded                       int    1
verifier.n_ungrounded                     int    5
verifier.n_out_of_corpus                  int    1
verifier.ungrounded_rate                  float  0.8333
verifier.ungrounded_rate_lenient          float  0.3333
verifier.out_of_corpus_rate               float  0.1667
verifier.panel_prose_jaccard              float  0.0526
verifier.n_vintage_mismatch               int    1
verifier.n_cited_successor                int    1
verifier.n_cited_predecessor              int    0

total_latency_ms                          int    12540
```

**`answer.prompt_tokens` and `answer.completion_tokens` exist**, so per-query cost is computable retrospectively even though `cost_usd` was never logged.

---

## 3. Runner summary — `runs/eval_*/eval_summary.jsonl`

Carries the gold. 26 distinct keys:

```
query_id · pair_id · category · variant · numbering_scheme
expected_sections · expected_corpus · expected_corpora · also_relevant
gold_mode · gold_status · answerable_from_corpus · applicable_regime
date_stated · messiness · n_words · notes
counterpart_sections · counterpart_corpus · conflict
control_unchanged_statute · no_counterpart_dropped
intervention · req_id · confidence · n_citations · citation_audit
latency_s · error
```

**`req_id` is present on 850 of 850 rows** and is the join key to the server log.

---

## 4. The six questions, answered

### (a) Which fields record the retrieval signals?

All present on **859 of 859** rows:

| Signal | Field |
|---|---|
| top-k mean | `confidence.top_k_mean` |
| score gap | `confidence.score_gap` |
| entity coverage | `confidence.entity_coverage` |
| composite | `confidence.composite` |
| max score | `retrieval.max_score` |
| every raw score | `retrieval.scores_raw` |
| counts | `retrieval.n_retrieved`, `retrieval.n_after_filter` |

`confidence.entity_coverage_default_used` also exists, which lets the neutral-default cases be separated from measured ones.

### (b) Are the retrieved chunks stored? At which stage?

**Stored, but at ONE stage only — Stage C, after the adaptive filter.**

| Check | Result |
|---|---|
| `len(chunks) == len(scores_raw)` | **392** rows |
| `len(chunks) < len(scores_raw)` | **467** rows — the filter dropped some, and only survivors were stored |

`scores_raw` holds all 15 scores, but **the identities of the dropped chunks were never written.**

On ordering: `scores_raw` is sorted descending in **714** rows and unsorted in **145**. The unsorted ones are in rerank order — so `scores_raw` is captured *after* entity reranking, and Stage A ordering cannot be recovered for those 145.

### (c) How is a retrieved passage's section identified?

**It is not.** Chunk records carry exactly five keys:

```
['corpus', 'doc', 'page', 'score', 'text_head']
```

There is **no `section_number`**. It exists in the Qdrant payload but was never copied into the log.

Two recovery routes were tested and both fail:

| Route | Result |
|---|---|
| Join on `(doc, page)` to Qdrant | **Fails.** 376 of 495 distinct `(doc, page)` keys (**76.0%**) hold more than one section |
| Parse `text_head` | **Partial.** Only 1,354 of 1,674 sampled chunks (**80.9%**) begin with `Section N`. The remaining **19.1%** begin mid-provision, e.g. `"Explanation.—A threat to injure the reputation of any deceased person"` |

That 19.1% is exactly the counting bug: those chunks were scored as misses.

### (d) What links a query row to its gold section?

`eval_summary.jsonl` carries `expected_sections` on **850 of 850** rows, and `req_id` on **850 of 850**, which joins to the server log's `req_id`.

### (e) Is there a grouping field for phrasing and date variants?

**Yes — `pair_id`, on every query set.**

| Query set | Rows | Groups | Variants per group |
|---|---|---|---|
| `paired` | 99 | 33 | 3.0 |
| `paired_dated` | 99 | 33 | 3.0 |
| `layman` | 120 | 30 | 4.0 |
| `generated` | 200 | 80 | 2.5 |

`pair_id` is the `situation_id` the plan asks for. No reconstruction is needed. The `generated` set averages 2.5 because sections without a usable title get only the numbered phrasing.

### (f) How many rows have a gold label?

| Query set | Rows | With gold |
|---|---|---|
| `generated` | 200 | **200** |
| `paired` | 99 | **99** |
| `paired_dated` | 99 | **99** |
| `layman` | 120 | **120** |
| `queryset` (older, superseded) | 58 | 45 |
| **Total in the four current sets** | **518** | **518** |

---

## 5. Assumptions in the plan that were wrong

| Plan says | Reality |
|---|---|
| `logs/` | The directory is `runs/`. Corrected in the plan already |
| "the `section_number` field is in the Qdrant payload and was never read" | Accurate about Qdrant, but **it was also never logged**, so it cannot simply be read now. See BLOCKER 1 |
| "compute at all three retrieval stages" | Only **one** stage has chunk identities. See BLOCKER 2 |
| "anything resembling a `situation_id`… if not, reconstruct" | No reconstruction needed. `pair_id` exists everywhere |
| "~27 positives under `grounded`" | Consistent with the logs; `verifier.ungrounded_rate == 0` is computable per row |

---

## 6. BLOCKERS — read before Task B

### BLOCKER 1 — `section_number` cannot be read from the logs

Wave 1 Subagent 2 says: *"Replace every 160-character match with a payload read."*

**This is not possible from existing data.** The payload field was never logged, `(doc, page)` is ambiguous for 76% of keys, and `text_head` covers only 80.9%.

**Two options.**

**Option A — re-run retrieval only, capturing the payload.** Embedding calls only, no answers generated, so roughly **₹1** for all 518 queries. It produces a chunk record carrying `section_number`, and all three retrieval stages at once. This makes BLOCKER 2 disappear as well.

**Option B — accept 80.9% coverage** and disclose the ceiling in every retrieval number.

**Recommendation: Option A.** It is about one rupee, it does not touch `runs/` (new output only), and without it the counting-bug fix cannot actually be verified. Option B leaves a known 19.1% blind spot in the paper's central metric.

### BLOCKER 2 — only one retrieval stage is recoverable

| Stage | Scores | Chunk identities |
|---|---|---|
| A `raw_15`, score order | partial — sorted in 714 of 859 rows | **no** |
| B `reranked_15` | yes, `scores_raw` | **no** |
| C `filtered_n` | yes | **yes** |

Section 4.1 of the plan requires every retrieval metric at all three stages. **From existing logs, only Stage C is computable.** Option A above fixes this.

### BLOCKER 3 — 222 duplicated `query_id` rows

850 summary rows hold only **521 unique** `query_id`. Killed-and-resumed runs appended repeats.

```
generated_retrieval    320 rows   (set has 200)
paired_dated_conflict  303 rows   (set has  99)
layman_situation       120 rows   (set has 120)
paired_recodification  104 rows   (set has  99)
```

**Every loader must deduplicate on `query_id`, keeping the last occurrence.** Duplicates inflate both halves of every proportion, and unevenly — the repeats are whichever queries were mid-flight when a run was killed, which is a biased sample. `load_logs()` and `load_queryset()` must do this, not each caller.

---

## 7. Baseline recorded

| | |
|---|---|
| Branch | `metrics/sept-01` |
| Tree | clean |
| Tests passing | **142** |
| Directories created | `results/`, `experiments/` |
| Backup | `backup/pre-metrics/` — 42 files, 12 MB, untracked |

---

**STOP. Task A complete. Awaiting confirmation before Task B.**

The decision needed: **Option A or Option B for BLOCKER 1.**
