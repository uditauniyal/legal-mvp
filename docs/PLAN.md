# PARALLEL PLAN + PROMPTS FOR CLAUDE CODE (technical)

1 September 2026. One file. Read section 1, then paste the waves in order.

**What changed from the last version:** concrete function signatures so five subagents cannot each invent their own AUROC; a discovery step because I do not know your log schema and neither should the prompt pretend to; the word "retrieved" disambiguated, because in your pipeline it has three possible meanings; a fixed CSV schema; fixed random seeds; and a mandatory explanation block that every subagent must fill for every output.

---

# 1. WHAT RUNS TOGETHER, WHAT CANNOT

You can wash five dishes at once. You cannot dry a dish before it is washed.

```
WAVE 0   DISCOVER SCHEMA + BUILD SHARED LIBRARY     SERIAL, alone
   |     ends by SHOWING YOU the schema it found
   v
WAVE 1   THREE BUG FIXES                            PARALLEL, 3 subagents
   v
GATE     SMOKE TEST — you read three numbers        SERIAL
   v
WAVE 2   FIVE METRIC FAMILIES                       PARALLEL, 5 subagents
   v                                                (the wave that pays)
WAVE 3   TWO EXPERIMENTS                            PARALLEL, 2 subagents
   v
WAVE 4   ASSEMBLE                                   SERIAL
```

**Why Wave 0 is serial and first.** Five subagents each writing their own AUROC gives five slightly different answers and tables that silently contradict each other. One tested implementation, imported by everyone. This is the most important rule here.

**Why Wave 0 now starts with discovery.** I have read your README but not your log files. I do not know their column names. A prompt that invents a schema produces code that silently reads the wrong field, which is defect E2 all over again. So the agent reads the real files, prints what it found, and shows you before building anything.

---

# 2. RULES THAT MAKE CONCURRENCY SAFE

1. **One owner per file.** Each subagent owns one script and one output path, named in advance. Two agents writing `results/metrics.csv` means one silently wins.
2. **Subagents never run git.** Concurrent git corrupts the repo. The main agent commits once per wave.
3. **Everyone imports `experiments/metrics_lib.py`.** Nobody reimplements. If a function is missing, stop and report.
4. **`runs/`, `eval/`, `data/`, Qdrant collection: read-only.** That data cost ₹1,728.
   `runs/` is gitignored and exists ONLY on this machine, with one backup at
   `backup/pre-metrics/`. Never write to either.
5. **Fixed seeds everywhere.** `SEED = 20260901`, `N_BOOT = 10000`. Reproducibility is a reviewer checkbox.

---

# 3. THE MANDATORY EXPLANATION BLOCK

This is the part that was missing. **Every subagent, for every output file it produces, appends one of these to `results/EXPLAIN.md`.** Not a paragraph. This exact shape, every heading present, every time.

```markdown
## <metric or experiment name>
Output file: <path>
Regenerate with: <exact command>
Owner: <subagent name>

### 1. ELI5 — what does this measure?
Two or three sentences for someone who has never met this term. Use an
analogy or a tiny worked example with real numbers. Do not use a term
without defining it in the same sentence.

### 2. Technically
The same thing stated precisely: the formula, the method name, the
reference if there is one.

### 3. What the number came out as
The value. Its sample size n. Its 95% confidence interval. Which
correctness definition was used. Which retrieval stage was used.
Never a number without all four.

### 4. How to read it
Is higher good or bad? What would a good result look like here? What
would a suspicious result look like — what should make me distrust it?

### 5. What this means for the paper
One paragraph. Which claim does this support, weaken, or kill?

### 6. What broke while computing this
Every error, including ones fixed in thirty seconds. If nothing broke,
write "nothing broke". Never omit this heading.

### 7. What I could not compute, and why
Or "nothing". Never omit this heading.

### 8. What surprised me
Anything that looked off, or that you should check by hand.
```

**A wave is not finished until every output has its block.** If a subagent reports back without one, send it back.

---

# 4. TERMS THIS PROJECT USES AMBIGUOUSLY — resolve them before computing

### 4.1 "Retrieved" has three meanings in your pipeline

Your retriever runs: Qdrant search `limit=15` → fallback → entity rerank (reorders) → adaptive filter (drops some) → chunks to the LLM.

So "the gold section was retrieved" could mean any of:

```
  STAGE A   raw_15         the 15 Qdrant returned, in score order
  STAGE B   reranked_15    same 15, reordered by entity match
  STAGE C   filtered_n     what survived the adaptive filter and
                           actually reached the language model
```

Your README's 68.0% / 71.7% / 15.0% figures were computed at one of these and it is not recorded which. **Every retrieval metric must be computed at all three stages and labelled**, and the run must report which stage reproduces the README figure. Rank-order metrics (MRR, nDCG) use Stage A unless stated, because Stage B has deliberately destroyed score order.

### 4.2 "Correct" has three definitions

Already specified, but they must be one function, not three implementations:
`retrieved@k` (gold section appears in the top k) · `cited` (gold section appears in the answer's citations) · `grounded` (the strict one, ~27 positives).

### 4.3 Section identity

Comparing `"IPC Section 302"` against `"Section 302"` and calling them different was defect E2, and it made a headline metric return zero for its entire existence. **One canonical `normalise_section()` in the library, used by everything.** It must handle: bare numbers, letter suffixes (`304B`), subsection forms (`318(4)`), and statute prefixes present or absent.

---

# 5. THE PROMPTS

---

## WAVE 0 — discovery, then the shared library (serial, ~1 h, free)

```
I am doing supervised research work on this repo toward a paper
submission. I am here and will answer questions, so ask me rather than
guessing or deciding for me.

This is my first research paper and I do not know most of these
statistical terms. Explaining things to me is a deliverable, not a
courtesy — see the EXPLANATION BLOCK rule below.

=== STANDING RULES, whole project ===
  - runs/, eval/, data/ and the Qdrant collection are READ-ONLY. New
    output goes to results/ and experiments/ only. That data cost 1,728
    rupees and cannot be cheaply regenerated.
  - runs/ is gitignored and exists ONLY on this machine. There is one
    backup at backup/pre-metrics/. It is the only copy of 1,728 rupees
    of measurements. Never write to either.
  - Experiments IMPORT the system. They never edit it.
  - Fixed seeds everywhere: SEED = 20260901, N_BOOT = 10000.
  - Every number carries: its value, its sample size n, its 95%
    confidence interval, the correctness definition used, the retrieval
    stage used, and the command that regenerates it.
  - Never write a number you expect. NOT MEASURED is a valid value.
  - Two attempts at any error, then stop and tell me what you tried.
    Never a third, never a refactor to work around it.
  - Do not tune anything to make a result look better.
  - Never invent a citation, arXiv ID or deadline.

=== EXPLANATION BLOCK RULE ===
For every output file produced anywhere in this project, append one
block to results/EXPLAIN.md with these exact eight headings, all of
them present every time:
  1. ELI5 — what does this measure?  (analogy or worked example with
     real numbers; no term used without defining it in the same sentence)
  2. Technically  (formula, method name, reference)
  3. What the number came out as  (value, n, 95% CI, correctness
     definition, retrieval stage)
  4. How to read it  (is high good or bad; what would a good result look
     like; what would a suspicious result look like)
  5. What this means for the paper  (which claim it supports, weakens or
     kills — one paragraph)
  6. What broke while computing this  (every error; "nothing broke" if
     none; never omit this heading)
  7. What I could not compute, and why  ("nothing" if none; never omit)
  8. What surprised me
A task is not complete until its explanation block exists.

=== DO NOT DO, ever, in this project ===
  - do NOT ingest the BNSS, BSA, Constitution or case law. It rebuilds
    the index and makes my 859 existing logged queries incomparable with
    new ones, destroying the base-rate control my main finding rests on.
    My README lists these as gaps, so this will look like an obvious
    improvement. It is not.
  - do NOT "fix" the router's consumer-protection bug or the corpus
    auto-tagging. They are the measured baseline and are described in
    the paper.
  - do NOT change the confidence weights (55/15/30) or the tier
    thresholds (55/38). They were fixed in February 2026 before any
    score was ever logged, which proves they were not tuned on the
    evaluation data. That is a methodological strength; changing them
    destroys it.
  - do NOT re-run ingestion, swap the embedding model, or refactor.
  - do NOT create new .md files beyond results/RESULTS.md and
    results/EXPLAIN.md.
  - do NOT write the paper or draft anything for my supervisor.

=== TASK A — discovery. Do this FIRST and STOP when done. ===
Do not write any metric code yet.

  1. Confirm branch metrics/sept-01, clean tree. Create results/ and
     experiments/. Run the test suite; log the pass count as baseline.
  2. Read the ACTUAL run-log files under runs/ and the ACTUAL eval/*.jsonl files. Do not
     assume anything from documentation. Write experiments/SCHEMA.md
     recording, for each file: its real path, its row count, every
     column or key name, the data type, and one real example value.
  3. Answer these specific questions in SCHEMA.md, from the data:
     a) Which fields record the retrieval signals (top_k_mean,
        score_gap, entity_coverage, max_score, composite confidence)?
     b) Are the retrieved chunks stored per query? At which pipeline
        stage — the raw 15 from Qdrant, after entity reranking, or after
        the adaptive filter? If more than one stage is stored, say which
        fields hold which.
     c) How is a retrieved passage's section identified — is the Qdrant
        payload section_number present in the logs, or only chunk text?
     d) What field links a query row to its gold section?
     e) Is there anything resembling a situation_id that groups the 3
        phrasings of a paired query, or the 4 date variants? If not, how
        can grouping be reconstructed — a shared pair id, an index
        pattern, something else?
     f) How many rows have a gold label, per query set?
  4. Then STOP and show me SCHEMA.md. Do not proceed to Task B until I
     confirm.

If any of my assumptions above turn out to be wrong about your data,
say so plainly rather than working around it.

=== TASK B — build experiments/metrics_lib.py (after I confirm) ===
ONE implementation of each metric. Later waves run several subagents
concurrently; if each writes its own AUROC they will disagree slightly
and my tables will silently contradict each other.

Implement exactly these signatures. Use numpy/pandas/scikit-learn;
do not add heavy dependencies.

  # --- loading, using the real schema from Task A ---
  load_logs(path) -> pd.DataFrame
  load_queryset(path) -> pd.DataFrame
  normalise_section(s: str) -> str
      # canonical form. Must handle bare numbers, letter suffixes
      # (304B), subsections (318(4)), and statute prefixes present or
      # absent. Comparing "IPC Section 302" to "Section 302" and calling
      # them different was a real defect here that made a headline
      # metric return zero for its whole existence.

  # --- correctness, ONE switch, not three implementations ---
  correctness_label(row, definition: str, k: int = 10) -> int
      # definition in {"retrieved@k", "cited", "grounded"}
      # raises ValueError on anything else

  # --- retrieval. ranked = section ids best-first; gold = one id ---
  recall_at_k(ranked, gold, k) -> float
  precision_at_k(ranked, gold, k) -> float
  reciprocal_rank(ranked, gold) -> float        # 0.0 if gold absent
  ndcg_at_k(ranked, gold, k) -> float           # binary gold, IDCG = 1.0

  # --- discrimination ---
  auroc(scores, labels) -> float
  auroc_bootstrap_ci(scores, labels, n_boot=N_BOOT, seed=SEED,
                     cluster_ids=None) -> (point, lo, hi)
      # if cluster_ids given, resample CLUSTERS not rows
  paired_bootstrap_auroc_diff(scores_a, scores_b, labels,
                              n_boot=N_BOOT, seed=SEED,
                              cluster_ids=None) -> dict
      # {"diff", "ci_lo", "ci_hi", "p_two_sided"}
      # PAIRED because both scores are measured on the same queries.
      # Use this rather than comparing two independent CIs by eye.
      # DeLong is optional; paired bootstrap is sufficient and simpler.

  # --- calibration ---
  reliability_bins(scores, labels, n_bins=10, strategy="quantile")
      -> pd.DataFrame[bin, n, mean_score, accuracy, gap]
      # QUANTILE (equal-mass) bins are the default deliberately: my
      # confidence values cluster in roughly 0.35-0.75, so equal-width
      # bins would leave most bins empty and one bin holding everything.
  ece(scores, labels, n_bins=10, strategy="quantile") -> float
  brier(scores, labels) -> float
  platt_scale(train_scores, train_labels, test_scores) -> np.ndarray
      # logistic regression on the single score feature

  # --- selective prediction ---
  risk_coverage_curve(scores, labels) -> pd.DataFrame[coverage, risk, threshold]
  aurc(scores, labels) -> float
  coverage_at_risk(scores, labels, max_risk=0.10) -> float

  # --- clustering ---
  cluster_bootstrap(df, stat_fn, cluster_col, n_boot=N_BOOT, seed=SEED)
      -> (point, lo, hi)

=== TASK C — known-answer tests, BEFORE any real data ===
Write tests/test_metrics_known_answers.py and make it pass. Feed each
function data whose correct answer is known in advance:
    AUROC, perfectly separable labels        must equal 1.0
    AUROC, shuffled random labels            must be 0.5 +/- 0.05
    MRR, gold always at rank 2               must equal 0.5
    Recall@1, gold always first              must equal 1.0
    Recall@k must be monotone non-decreasing in k
    ECE on perfectly calibrated synthetic data must be near 0.0
    precision_at_k == recall_at_k / k        for single-gold input
    normalise_section("IPC Section 302") == normalise_section("Section 302")
    paired_bootstrap on identical inputs     diff = 0, p near 1.0

If any fails, that implementation is wrong and every number it would
ever produce is worthless. Stop and tell me; do not work around it.

Then write the explanation block for metrics_lib to results/EXPLAIN.md,
explaining each function in plain English. Then commit.
```

**You check before Wave 1:** did the known-answer tests pass, and does SCHEMA.md match what you believe about your own data?

---

## WAVE 1 — three bug fixes in parallel (3 subagents, ~1 h, free)

```
Spawn THREE subagents concurrently. Give each the standing rules, the
do-not-do list, and the explanation block rule.

Concurrency rules for all three:
  - each owns ONLY the files listed in its task, and touches nothing else
  - no subagent runs git; you commit once after all three report
  - each writes its own test file; they do not share test files
  - each appends its explanation block to results/EXPLAIN.md, and its
    ELI5 must say what was silently going wrong and what changes now

SUBAGENT 1 — tier bug
  Owns: agents/answer.py, tests/test_tier_bug.py
  agents/answer.py sets prompt_variant to "HIGH" and never updates it,
  so 369 of 859 records (43%) log the wrong tier. The disclaimer was
  applied correctly; only the log is wrong. Derive the logged tier from
  the actual confidence value at the moment of logging.
  Tests: 0.30 -> LOW, 0.45 -> MEDIUM, 0.60 -> HIGH, and a boundary test
  at exactly 0.55 and exactly 0.38.

SUBAGENT 2 — the adaptive filter investigation
  Owns: experiments/exp08_filter.py -> results/filter_analysis.csv
  REPURPOSED 1 Sept. The original task was a "counting bug" fix. Wave 0
  proved there was no bug: the text-parsing rule recovered the section
  correctly 4,906 times out of 4,906, a 0.0% error rate. The 7.5% vs
  15.0% discrepancy was a STAGE confusion, not a defect.

  Wave 0 surfaced a real finding instead. The adaptive filter costs
  generated 2%, paired 4%, paired_dated 8% -- but layman 50%. [CORRECTED 1 Sept, post-measurement: the real losses are 1.5, 3.0 and 4.1 percentage points; layman 7.5 pp = 50% relative. The "8%" was mine and was never in WORKLOG, which said 2-4%.] Find out
  why, and how much it costs.

  a) For every query where the gold section was in raw_15 but NOT in
     filtered_n: what score did that gold chunk have, and what was the
     threshold that cut it?
  b) The threshold is max(top_score - 0.15, 0.35). For each cut, which
     arm was binding -- the relative one or the 0.35 floor? Report the
     split per query set. Hypothesis: the floor does nearly all the
     damage on layman queries because their top scores sit near 0.40.
  c) Counterfactual sweep: recompute what recall WOULD have been at
     floors of 0.35, 0.30, 0.25, 0.20 and no floor, per query set, with
     confidence intervals.

  To be explicit, because it looks like it violates a standing rule:
  this is ANALYSIS, not tuning. Do NOT change the deployed 0.35 floor
  anywhere in the system. Measure what other floors would have done,
  report it, change nothing.

  Input: experiments/stages.jsonl, which already holds all three stages
  with authoritative section_number.

SUBAGENT 3 — citations binding bug
  Owns: core/citations.py, tests/test_citations_bug.py
  core/citations.py binds a statute to a section number by proximity in
  the answer text, so an answer citing BNS 190 is recorded as "IPC
  Section 190" when "Indian Penal Code" appeared earlier in the
  paragraph. My answers legitimately mention both codes, which is
  exactly when this breaks. Two metrics were already retired over it.
  Bind statute to section only when both appear in the same citation
  unit; where no statute is attributable, return an explicit UNKNOWN
  rather than guessing.
  Tests: an answer mentioning both codes parses correctly; a bare
  "Section 190" with no statute nearby returns UNKNOWN, not a guess.

core/verifier.py contains two functions, provisions_from_chunks and
reattribute, that are complete but called by nothing. Leave them. Do not
revert this file — its last committed state is broken and was fixed on
this branch.

Then run the full suite, compare to the Wave 0 baseline, commit, and
give me all three explanation blocks together.
```

---

## GATE — smoke test (serial, 20 min, free). Stop here.

```
Before any large analysis, compute exactly three numbers using
metrics_lib, write results/smoke_test.md with a full explanation block
for each, and STOP.

1. Do my headline figures survive the fixes? Re-derive IPC vs BNS
   retrieval accuracy — previously 97.0% and 51.5% — with 95% CIs.
   Report it at all three retrieval stages (raw_15, reranked_15,
   filtered_n) and say which stage reproduces the README figure.

2. Under correctness definition "retrieved@k" instead of "grounded",
   how many positives are there across all 518 labelled rows? It was 27
   under the strict definition. I expect 200 or more under this one.
   Report the count under all three definitions.

3. Compare composite confidence against raw max_score by AUROC using
   paired_bootstrap_auroc_diff. Report the difference, its CI, and the
   p-value. My README says the composite is "worse" (0.610 vs 0.663).
   With 27 positives that word may not survive. Tell me whether the
   supported claim is "worse" or "no better than".

Then STOP. Do not start the metrics suite. I want to look first.
```

| What you see | Meaning | Do |
|---|---|---|
| 97/51 survive, positives 200+ | Spine holds | Run Wave 2 |
| Headline moved | Claim needs restating | Tell me the new numbers first |
| Positives still 27 | Correctness label wired wrong | Stop; Wave 2 would inherit it |

---

## WAVE 2 — five metric families in parallel (5 subagents, ~1 h, free)

```
Smoke test looks right. Spawn FIVE subagents concurrently.

Rules for all five:
  - every one IMPORTS experiments/metrics_lib.py. Nobody reimplements a
    metric. If something is missing from the library, STOP and tell me
    rather than writing your own version.
  - each owns ONE script and ONE output file, named below. No two write
    the same path.
  - no subagent runs git.
  - ZERO generation calls. All of this computes from existing logs.
  - each writes a paired check script experiments/check_NN_*.py that
    re-derives at least one of its own values by an independent route
    and asserts agreement.
  - each appends a full explanation block to results/EXPLAIN.md.

EVERY output CSV uses this exact long-format schema, so Wave 4 can
simply concatenate them:
  metric, query_set, definition, stage, k, value, n,
  ci_lo, ci_hi, cluster_ci_lo, cluster_ci_hi, notes
Leave a column empty rather than renaming it or inventing a new one.

SUBAGENT 1 — retrieval metrics
  experiments/exp01_retrieval.py -> results/retrieval_metrics.csv
  Recall@k, Precision@k, MRR, nDCG@k for k in 1,3,5,10,15, per query
  set, AT ALL THREE STAGES (raw_15, reranked_15, filtered_n), under all
  three correctness definitions. Rank-order metrics (MRR, nDCG) use
  raw_15 as primary since reranking deliberately destroys score order —
  report the others but say this in notes.
  In the explanation block, state that with a single binary gold per
  query, Precision@k equals Recall@k/k exactly and nDCG@k is a monotone
  function of reciprocal rank, so both are reported for completeness
  rather than for information.

SUBAGENT 2 — routing analysis
  experiments/exp02_routing.py -> results/routing_confusion.csv
  4x4 routing confusion matrix across IPC, BNS, CrPC, CPA on the layman
  set. Re-derive the 2x2 IPC/BNS matrix with CIs. Also recompute the
  base-rate control: each corpus's share of the index against its share
  of layman retrieval, with the over-representation ratio. That control
  is what makes the CrPC claim falsifiable, so it must survive the fixes.

SUBAGENT 3 — calibration
  experiments/exp03_calibration.py -> results/calibration.csv
                                      results/reliability_diagram.png
  Reliability diagram with QUANTILE bins, binning stated in the caption.
  ECE, Brier, risk-coverage curve, coverage at 10% risk, AURC.
  Then Platt scaling on a 60/40 stratified split, ECE before and after
  on the test split only.
  In the explanation block, make clear that my composite score was never
  a probability — it is a weighted sum of cosine similarities — so
  explain what ECE on it does and does not tell me, and whether Platt
  scaling makes it usable as one.

SUBAGENT 4 — ablation
  experiments/exp04_ablation.py -> results/ablation.csv
  AUROC per signal with bootstrap CIs.
  Leave-one-out: recompute the composite three times, each with one
  signal removed and THE REMAINING WEIGHTS RENORMALISED TO SUM TO 1.
  State in the explanation that this is a DIFFERENT question from the
  per-signal-alone AUROCs already in my README: "does this signal carry
  information alone" versus "does removing it hurt the combination".
  Weight sweep over the three weights in 0.05 steps summing to 1; report
  the argmax and whether it puts any signal at or near zero.

SUBAGENT 5 — robustness and clustering
  experiments/exp05_robustness.py -> results/robustness.csv
  Re-run the core analyses under all three correctness definitions, and
  log the positive count under each. If conclusions differ across
  definitions, that is a finding — report all three, never pick one.
  Clustering: paired set is 33 situations x 3 phrasings; dated set is
  30 x 4. Phrasings of one situation are NOT independent observations.
  Use cluster_bootstrap on situation_id (reconstructed per SCHEMA.md if
  the field does not exist) and report naive and clustered intervals
  side by side so the difference is visible.

When all five report, commit and give me the five explanation blocks
together.
```

---

## WAVE 3 — two experiments in parallel (2 subagents, ~1.5 h, ~₹2)

```
Spawn TWO subagents concurrently. Same rules, same CSV schema, same
explanation blocks. Both are retrieval-only. Tell me before any batch
of more than 100 generation calls; I do not expect any.

SUBAGENT 1 — statute_consistency
  experiments/exp06_statute_consistency.py
      -> results/statute_consistency.csv
  Build the fourth confidence signal specified at
  docs/TARGET_ARCHITECTURE.md line 352 and never built. It measures
  whether the retrieved passages came from the book the question
  implies. My three existing signals only inspect similarity numbers;
  this one inspects whether the answer is in the right book at all.
  Compute over the existing query sets, retrieval only. Add it as a
  fourth row to the ablation table with AUROC, bootstrap CI, ECE.

  Both outcomes are results. If it beats the generic signals, that is a
  contribution. If it does not, that is a stronger negative result. Do
  NOT tune it to win. If you adjust it at all after seeing its AUROC,
  refit on a train split, report test-split performance only, and say so
  in the explanation block.

  Also: recompute entity_coverage from the section_number payload field
  rather than substring-matching chunk text. The section normaliser
  rewrites any line starting with a number and a full stop into
  "Section N.", so page numbers and list items produce false matches —
  a known confound on the signal measured at 0.492. Report both ways.
  Then sample 100 normaliser-rewritten lines, classify each as genuine
  section heading or artefact, and report the artefact rate with a CI.

SUBAGENT 2 — BM25 and hybrid
  experiments/exp07_hybrid.py -> results/hybrid_comparison.csv
  BM25 index over the same 1,899 chunks using rank_bm25. No API cost.
  Tokenisation: lowercase, but KEEP digits and subsection markers —
  section numbers are the entire point here, so do not strip numerals
  or punctuation inside forms like 318(4).
  Retrieve top 50 from each of dense and BM25, then fuse with Reciprocal
  Rank Fusion: score(d) = sum over lists of 1/(60 + rank_i(d)), k=60,
  citing Cormack, Clarke and Buttcher, SIGIR 2009. Do not invent a
  constant. Evaluate at k up to 15 so it is comparable with existing
  numbers.
  Report retrieval metrics for three configurations: dense alone, BM25
  alone, hybrid.

  The number I care about: does BNS-named query accuracy move off 51.5%?
  This answers the sharpest objection my paper will face — that
  exact-match search would separate IPC 420 from BNS 318 trivially, so
  the failure might be an artefact of choosing a dense retriever. Either
  direction publishes. Tell me which, and by how much, with CIs.

Commit when both report; give me both explanation blocks.
```

---

## WAVE 4 — assemble (serial, 30 min, free)

```
One agent, no subagents.

Concatenate every results/*.csv into results/RESULTS.md as tables, one-
line captions, regenerating command beside each. No prose, no plans, no
summary of effort. Every number carries n, CI, definition and stage.

Verify before writing that every file path you reference exists on disk.
If something did not run, the field reads NOT MEASURED — never a
plausible placeholder.

Then check results/EXPLAIN.md is complete: one block per output file,
all eight headings present in each. List any that are missing rather
than writing them yourself from memory.

Finally, list separately at the bottom of RESULTS.md:
  - every number that CHANGED from what my README currently publishes:
    old value, new value, which bug fix caused it
  - every known-answer test or assertion that failed
  - everything that could not be computed, and why

Commit.
```

---

# 6. TIME AND COST

| Wave | Wall clock | Cost |
|---|---|---|
| 0 discovery + library | ~1 h | free |
| 1 bug fixes | ~1 h | free |
| Gate | 20 min | free |
| 2 metrics | ~1 h | free |
| 3 experiments | ~1.5 h | ~₹2 |
| 4 assemble | 30 min | free |
| **Total** | **~5 h 20 m** | **~₹2** |

Serial this is roughly 8 hours. Nearly all the saving is Wave 2.

Wave 0 plus Wave 1 plus the gate is a sensible first sitting, and it is where your attention matters most.

---

# 7. WHEN IT GOES WRONG

**A subagent reports the same error twice.** By the rules it stops. Read what it tried. Usually a path differs from documentation, which is why Wave 0 inventories real paths first.

**Two subagents wrote the same file.** Rule 1 broken. Check `git status`, find the missing output, re-run that subagent alone.

**Tables disagree with each other.** Rule 3 broken — somebody reimplemented instead of importing. Find it, delete its version, re-run against `metrics_lib`.

**Known-answer tests fail in Wave 0.** Stop everything. That is the protocol working. A broken metric produces believable wrong numbers, which is exactly how this project lost six months.

**An explanation block is missing.** The task is not done. Send it back rather than accepting the numbers — the block is where you find out that a number was computed at the wrong stage.
