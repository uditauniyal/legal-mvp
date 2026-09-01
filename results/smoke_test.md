# GATE — smoke test

1 September 2026. Branch `metrics/sept-01`, after Wave 1.
Three numbers, computed with `experiments/metrics_lib.py`. Zero generation calls;
the only API spend was the ablation re-run, embeddings only, about ₹0.01.

**Verdict against the plan's gate table: the spine holds. Wave 2 may start.**

| Gate condition | Required | Measured |
|---|---|---|
| 97.0 / 51.5 survive the fixes | yes | **reproduced exactly** — 32/1 and 16/17 |
| positives under `retrieved@k` | 200 or more | **327** |
| positives still stuck at 27 | would mean the label is miswired | no — 27 is `grounded` only, as designed |

---

## 1. Does the headline survive the Wave 1 fixes?

Output file: `results/ablation_rerun_2026-09-01.txt`, `results/gate_smoke.json`
Regenerate with:
```
./venv/Scripts/python.exe scripts/ablate_filter.py
./venv/Scripts/python.exe experiments/gate_smoke.py
```
Owner: GATE (main agent)

### 1. ELI5 — what does this measure?

A *query set* here is 66 questions that each name their own law explicitly —
33 say "Indian Penal Code", 33 say "Bharatiya Nyaya Sanhita". The question is
simple: when a question names its code out loud, does the search engine bring
back text from that code, or from the other one?

*Chance* is the share of the index each code occupies. The IPC is 31.3% of the
1,899 stored passages. So a search engine that ignored the question completely
and picked passages at random would still land on IPC 31.3% of the time. Any
score above chance is signal; a score near chance means the Act name carried no
information at all.

### 2. Technically

`scripts/ablate_filter.py`, corpus filter DISABLED, `limit=15`, cosine
similarity over `text-embedding-3-small` (1,536 dimensions). A query is scored
correct when the *dominant* corpus among its 15 retrieved passages is the one
named. A second table repeats it on the single top-1 passage. Intervals are 95%
Wilson score intervals.

**Two filters exist and they must not be confused.** The *corpus filter*
restricts the Qdrant search to one statute before retrieval; the *adaptive score
filter* `max(top_score − 0.15, 0.35)` drops low scorers afterwards. This
experiment disables the FIRST. With it on, an IPC-named query physically cannot
return a BNS passage, so the question is unaskable.

### 3. What the number came out as

Dominant corpus among the top 15, corpus filter OFF, n=33 per row:

| Query names | → IPC | → BNS | correct | chance |
|---|---|---|---|---|
| Indian Penal Code (repealed 2024) | 32 | 1 | **97.0%** [84.7, 99.5] | 31.3% |
| Bharatiya Nyaya Sanhita (in force) | **16** | 17 | **51.5%** [35.2, 67.5] | 22.3% |

Top-1 passage only:

| Query names | → IPC | → BNS | correct |
|---|---|---|---|
| IPC | 30 | 3 | 90.9% [76.4, 96.9] |
| BNS | **19** | 14 | **42.4%** [27.2, 59.2] |

Definition: dominant-corpus match. Stage: `raw_15`, corpus filter off.
**Identical to `docs/results/PHASE_G.md` in every cell.**

A separate and DIFFERENT question — gold-section recall through the deployed
pipeline, corpus filter ON, `retrieved@15`, paired set, n=33 per cell:

| Stage | IPC-named | BNS-named |
|---|---|---|
| `raw_15` | 29/33 = 87.9% [72.7, 95.2] | 11/33 = 33.3% [19.8, 50.4] |
| `reranked_15` | 29/33 = 87.9% [72.7, 95.2] | 11/33 = 33.3% [19.8, 50.4] |
| `filtered_n` | 26/33 = 78.8% [62.2, 89.3] | 11/33 = 33.3% [19.8, 50.4] |

### 4. How to read it

Higher is better; compare each row against its own chance column, not against
the other row. A good result for the IPC row is what we see — 97% against 31%
chance means the Act name is doing real work. A suspicious result would be
either row sitting ON its chance value, or the BNS row exceeding the IPC row,
which would contradict every other measurement in this project.

The asymmetry is the finding. Naming the repealed code works almost perfectly.
Naming the code actually in force works barely half the time, and the misses do
not scatter — they land on the repealed code, 16 times out of 33.

### 5. What this means for the paper

This is the paper's central claim and it is unchanged by three bug fixes, a new
metric library, and a re-run against a live index. Reproducing 32/1 and 16/17
cell-for-cell after all of that is the strongest reproducibility evidence the
project has.

The deployed-pipeline table underneath it matters for a different reason: it
shows the same asymmetry (87.9% vs 33.3%) survives WITH the corpus filter on,
so the failure is not an artefact of switching a filter off to expose it.

### 6. What broke while computing this

Two things, both in code written in Wave 0, both caught here.

**(a) `same_section` raised `ValueError` on real data.** `normalise_section`
handles Sections; Constitution *Articles* and CPC *Orders*/*Rules* fell through
to a fallback that returned no `:` separator, and `same_section` splits on that
colon. 28 distinct such strings appear in the logs — `CONSTITUTION Article 226`
29 times. Fixed so they keep their kind word: `CONSTITUTION:ARTICLE226`, which
correctly does NOT equal Section 226.

**(b) The fix for (a) silently zeroed every retrieval metric.**
`ranked_sections()` returns strings ALREADY canonical, and `same_section()`
normalises them a second time — so the function is routinely called on its own
output. The old fallback was a no-op there by accident. The new one stripped the
statute prefix again and turned `BNS:190` into `BNS::190`. Result: 0/617 under
`retrieved@k`, nothing crashed, and every number looked like a real finding.
**This is the exact failure mode the gate exists to catch.** Fixed by making
`normalise_section` idempotent and pinning it with
`test_idempotent_on_its_own_output`.

Suite 229 → 237.

### 7. What I could not compute, and why

`ablate_filter.py` writes to standard output only, so the original 97.0/51.5 run
was never saved as data — the numbers existed in `docs/` and nowhere else. They
had to be regenerated against the live Qdrant collection rather than recomputed
from logs. Output is now captured at `results/ablation_rerun_2026-09-01.txt` so
this never recurs.

The three-stage table cannot reproduce 97.0/51.5, because `stages.jsonl` replays
the recorded corpus filter and every row is therefore already restricted to one
statute. Reporting a cross-statute number from it would produce something near
100% that means nothing.

### 8. What surprised me

The adaptive filter costs the IPC row 9.1 points (29 → 26 of 33) and the BNS row
nothing at all (11 → 11). It removes correct retrievals only where retrieval was
already working.

---

## 2. How many positives exist under each correctness definition?

Output file: `results/gate_smoke.json`
Regenerate with: `./venv/Scripts/python.exe experiments/gate_smoke.py`
Owner: GATE (main agent)

### 1. ELI5 — what does this measure?

A *positive* is a question the system got right. Statistics that compare right
answers against wrong ones need enough of each; with 27 rights out of 617 you
can compute a number, but it will swing wildly on a handful of rows.

"Right" has three meanings here and they are not interchangeable:

| Definition | Plain English |
|---|---|
| `retrieved@15` | the correct law section was among the 15 passages fetched |
| `cited` | the correct section appears in the answer's citations |
| `grounded` | every section the answer cited was actually in the fetched text |

`grounded` is the strictest: one unsupported citation anywhere fails the row.

### 2. Technically

`correctness_label(row, definition, k, stages)` — one switch, not three
implementations. n = 617 rows carrying a gold label, after deduplication on
`(query_id, intervention)` keeping the last occurrence. Intervals are 95%
Wilson.

### 3. What the number came out as

n = 617 labelled rows.

| Definition | Stage | Positives | Rate |
|---|---|---|---|
| `retrieved@15` | `raw_15` | **327** | 53.0% [49.1, 56.9] |
| `retrieved@15` | `reranked_15` | 327 | 53.0% [49.1, 56.9] |
| `retrieved@15` | `filtered_n` | 304 | 49.3% [45.3, 53.2] |
| `cited` | pre-fix parser (logged) | 533 | 86.4% [83.5, 88.9] |
| `cited` | post-fix parser (re-parsed) | 538 | 87.2% [84.3, 89.6] |
| `grounded` | — | **27** | 4.4% [3.0, 6.3] |

### 4. How to read it

There is no "good" value. This is a capacity check: does each definition have
enough positives to support the statistics built on it. 327 does. 27 does not —
any AUROC computed on 27 positives will have an interval roughly three times
wider than one computed on 327.

The suspicious result was the one that appeared on the first run: 0 positives
under every stage, which is not a finding but a wiring fault. See block 1, §6.

### 5. What this means for the paper

The gate's stated worry was that `retrieved@k` might come back at 27, meaning
the label was miswired. It came back at 327. The three definitions are genuinely
measuring three different things, and the strict one is strict for a real reason
rather than a bug.

This changes which claims can be made with power. Anything resting on `grounded`
alone carries 27 positives and must report that number beside it. Anything
resting on `retrieved@15` has 327 and can support a much sharper statement.

Reranking moves nothing (327 → 327): entity reranking reorders the same 15
passages, so a metric asking only whether the gold is *present* cannot detect
it. That is expected, and it is why rank-order metrics must be reported
separately in Wave 2.

### 6. What broke while computing this

The `same_section` crash and the idempotence regression, both recorded in
block 1 §6. Nothing else.

### 7. What I could not compute, and why

Nothing.

### 8. What surprised me

**The citation parser fix barely moved this number: 533 → 538, five rows.**
Wave 1 measured that the fix changes 15.9% of citation *units* and flips statute
attribution on 72 of them. But `cited` asks only whether the gold section
appears *somewhere* in the citation list, and most of the changes turn a
confident statute into UNKNOWN — which still matches, because an unattributed
reference matches on number alone. The fix will show up in statute-sensitive
metrics, not in this one. Worth stating in the paper so the fix is not oversold.

---

## 3. Is the composite confidence score really "worse" than raw max similarity?

Output file: `results/gate_smoke.json`
Regenerate with: `./venv/Scripts/python.exe experiments/gate_smoke.py`
Owner: GATE (main agent)

### 1. ELI5 — what does this measure?

The system produces a *confidence score* — a number meant to say how much to
trust an answer. It is a weighted blend of three signals (55/15/30). The
question is whether that blend beats simply reading the single highest
similarity score the search returned.

*AUROC* is the measure: pick one correct answer and one wrong answer at random;
AUROC is the probability the correct one has the higher score. 0.5 is a coin
flip — the score knows nothing. 1.0 is perfect separation.

The trap this block exists to avoid: two scores measured on the SAME questions
cannot be compared by looking at whether their intervals overlap. That
comparison ignores the pairing and is far too conservative. A *paired bootstrap*
resamples the questions 10,000 times and measures the DIFFERENCE each time,
which is the correct test.

### 2. Technically

`paired_bootstrap_auroc_diff(composite, max_score, labels, n_boot=10000,
seed=20260901)`. AUROC via Mann-Whitney U with average ranks so ties count 0.5.
Percentile bootstrap, two-sided p from the sign of the resampled difference
distribution.

### 3. What the number came out as

n = 617 in every row.

| Definition | Positives | composite AUROC | max_score AUROC | paired difference | p | Supported claim |
|---|---|---|---|---|---|---|
| `grounded` | 27 | 0.531 [0.449, 0.608] | 0.589 [0.489, 0.686] | −0.058 [−0.169, +0.056] | 0.3154 | **"no better than"** |
| `retrieved@15` (`raw_15`) | 327 | 0.663 [0.617, 0.710] | **0.784** [0.747, 0.819] | **−0.121** [−0.162, −0.080] | <0.0001 | **"worse"** |
| `cited` (post-fix) | 538 | 0.571 [0.500, 0.643] | 0.675 [0.602, 0.744] | −0.103 [−0.159, −0.046] | 0.0004 | **"worse"** |

### 4. How to read it

Higher AUROC is better. The column that decides the claim is the paired
difference and its interval. If that interval contains 0, the data cannot
distinguish the two scores and "worse" is not supportable — only "no better
than". If it excludes 0, "worse" is supportable.

A suspicious result would be an AUROC of exactly 0.500, or an interval so wide
it spans 0.4 to 0.9 — both indicate too few positives rather than a finding.

### 5. What this means for the paper

The README says the composite is "worse" (0.610 vs 0.663). **That word is
supported, and more strongly than the README claims — but only under the
definitions that have the positives to support it.**

Under `grounded`, with 27 positives, the honest statement is "no better than":
the difference is −0.058 with an interval crossing zero and p = 0.32. Under
`retrieved@15`, with 327 positives, the difference is −0.121 with an interval
nowhere near zero and p below 0.0001. Under `cited`, −0.103, p = 0.0004.

So the recommendation is to state the claim under `retrieved@15` as primary,
report all three, and say explicitly that the strict definition lacks the power
to resolve it. That is a stronger and more defensible negative result than the
current one-line README claim: **a single raw cosine similarity discriminates
better than the engineered three-signal blend, on 617 queries, at p < 0.0001.**

Note also that `max_score` reaches 0.784 under `retrieved@15`. That is a
genuinely useful confidence signal — which makes the composite's failure a
design finding rather than a "nothing works here" result.

### 6. What broke while computing this

Nothing beyond the two defects in block 1 §6.

### 7. What I could not compute, and why

**Which correctness definition produced the README's 0.610 / 0.663 is not
recorded**, and none of the three rows above reproduces that pair. This is the
same class of omission as the unlabelled retrieval-stage figures. The README
numbers should be treated as superseded rather than reconciled, and every future
figure must carry its definition. Flagged for Wave 4.

### 8. What surprised me

The composite scores 0.663 under `retrieved@15` — numerically identical to the
value the README attributes to `max_score`. Coincidence, since the populations
and definitions differ, but it is the kind of collision that invites a reader to
conclude the numbers were mixed up. Another reason to publish definition and
stage beside every value.
