# Phase H — the intervention, measured

**Code:** `302e1f8` · **Index:** 1,899 chunks · **Date:** 2026-08-23 · **Reference date:** 2026-08-23
**Query set:** `eval/paired_dated_queryset.jsonl` — 99 queries, 33 verified IPC↔BNS pairs × 3 variants
**Runs:** `eval_2026-08-23_0353_302e1f8` (baseline) · `eval_2026-08-23_0410_302e1f8_both` (intervention)

Reproduce:

```bash
python scripts/compare_runs.py \
  --baseline     runs/eval_2026-08-23_0353_302e1f8 \
  --intervention runs/eval_2026-08-23_0410_302e1f8_both
```

Both runs cover the same 99 `query_id`s, at the same commit, against the same index. One variable changed: whether the Date Resolver and Statute Mapper were switched on.

---

## What the query set does

The Phase G paired set names a code in every query and gives a date in none. With no date the Date Resolver returns `UNKNOWN`, and on `UNKNOWN` the Statute Mapper deliberately changes nothing — so the intervention is a no-op there by construction and a comparison would measure nothing.

This set puts the two signals in **conflict**:

| Variant | N | Query | Gold |
|---|---|---|---|
| `conflict_ipc_named` | 33 | *"…Section 420 of the **Indian Penal Code**? This happened **last month**."* | **BNS 318(4)** |
| `conflict_bns_named` | 33 | *"…Section 318(4) of the **Bharatiya Nyaya Sanhita**? This happened **March 2023**."* | **IPC 420** |
| `agree_control` | 33 | *"…Section 420 of the **Indian Penal Code**? This happened **March 2023**."* | IPC 420 |

Gold follows the **date**, not the words. The control matters as much as the conflicts: if it moves, the intervention has learned a preference rather than a rule.

---

## Result 1 · Retrieval is fixed

These come from the `corpus` field on the retrieved chunks — ground truth from the index, not from parsing text.

**Correct corpus dominates the results**

| Variant | N | baseline | + intervention | delta |
|---|---|---|---|---|
| `conflict_ipc_named` | 33 | **0.0%** [0.0, 10.4] | **100.0%** [89.6, 100.0] | **+100.0 pp** |
| `conflict_bns_named` | 33 | **0.0%** [0.0, 10.4] | **100.0%** [89.6, 100.0] | **+100.0 pp** |
| `agree_control` | 33 | 100.0% [89.6, 100.0] | 100.0% [89.6, 100.0] | +0.0 pp |

**Wrong-era provision retrieved** (lower is better)

| Variant | N | baseline | + intervention | delta |
|---|---|---|---|---|
| `conflict_ipc_named` | 33 | **81.8%** [65.6, 91.4] | **0.0%** [0.0, 10.4] | **−81.8 pp** |
| `conflict_bns_named` | 33 | 36.4% [22.2, 53.4] | **0.0%** [0.0, 10.4] | −36.4 pp |
| `agree_control` | 33 | 0.0% | 0.0% | +0.0 pp |

The baseline retrieved the repealed provision in **81.8%** of the cases where the query named the IPC and the conduct was recent. After the intervention: **zero**. The control does not move.

**Gold provision retrieved** (strict match)

| Variant | N | baseline | + intervention | delta |
|---|---|---|---|---|
| `conflict_bns_named` (gold is an **IPC** section) | 33 | 0.0% | **78.8%** [62.2, 89.3] | **+78.8 pp** |
| `conflict_ipc_named` (gold is a **BNS** section) | 33 | 0.0% | **36.4%** [22.2, 53.4] | **+36.4 pp** |
| `agree_control` | 33 | 78.8% [62.2, 89.3] | 78.8% [62.2, 89.3] | +0.0 pp |

**The asymmetry is the interesting part.** Routing to the right corpus is now perfect in both directions, but *finding the right section inside it* succeeds 78.8% of the time when the target is an IPC section and only 36.4% when it is a BNS section — on the same 33 offences, with the same wording.

That is the Phase G result reappearing from a different direction. The BNS is 22.3% of the index against the IPC's 31.3%, and the BNS PDF carries no marginal notes, so its chunks begin with the first clause of the provision rather than its subject. Fixing the routing does not fix that; it is a corpus and chunking problem, not a routing one.

---

## Result 2 · The answer improves much less than the retrieval

Whether the answer tells the user the law changed — searched for repeal / replacement language, *"with effect from"*, *"1 July 2024"*, *"erstwhile"*, *"corresponding provision"*:

| Variant | N | baseline | + intervention | delta |
|---|---|---|---|---|
| `conflict_ipc_named` | 33 | 39.4% [24.7, 56.3] | 63.6% [46.6, 77.8] | +24.2 pp |
| `conflict_bns_named` | 33 | 51.5% [35.2, 67.5] | 66.7% [49.6, 80.2] | +15.2 pp |
| `agree_control` | 33 | 3.0% [0.5, 15.3] | 3.0% [0.5, 15.3] | +0.0 pp |

Both deltas point the right way, and the control stays flat at 3.0% — the system is not simply mentioning the recodification more often everywhere.

**But the intervals overlap** (39.4% [24.7, 56.3] against 63.6% [46.6, 77.8] share the range 46.6–56.3). At n=33 this is suggestive, not established. It needs a larger set before it can be claimed.

**The gap between Result 1 and Result 2 is itself the finding.** Retrieval went from 0% to 100% correct. The answer's handling of the change moved by roughly 20 points and still fails a third of the time. Fixing what the system *reads* does not fix what it *says* — which is the same conclusion Phase G reached from the ungrounded rate (83.8% on layman queries), now shown causally: we changed the inputs and the outputs barely followed.

---

## Two metrics that are UNUSABLE on this query set

`gold_cited` and `wrong_era_cited` are reported by `compare_runs.py` and **must not be used here.**

`core/citations.py` assigns a statute to a section number by proximity in the answer text. These answers legitimately mention both codes — the user asked about one and the governing law is the other — so attribution collapses. Measured on the intervention run, `conflict_ipc_named`:

| | |
|---|---|
| retrieval returned **BNS chunks only** | **100%** |
| answer mentions the BNS | 100% |
| answer mentions the IPC | 98% (the question named it) |
| extractor labelled some citation "IPC" | 92% |

Concretely, an answer citing **BNS 190** was recorded as `IPC Section 190` because the phrase "Indian Penal Code" appeared earlier in the text.

So `wrong_era_cited = 100%` cannot distinguish **"wrongly relied on repealed law"** from **"correctly explained that the law changed"** — opposite behaviours with the same measurement. The transition-language check above is the substitute, and it is a proxy, not a citation metric.

**Fixing this needs statute attribution from structure rather than proximity** — for example binding each citation to the retrieved chunk that supports it. That is the next piece of work, and until it exists no citation-level claim should be made on any query set where both codes appear.

---

## What is established

1. **The Statute Mapper eliminates wrong-era retrieval.** 81.8% → 0.0%, with the control unmoved. Routing to the governing code is 100% in both directions.
2. **Routing is not the whole problem.** With routing perfect, section-level retrieval is 78.8% into the IPC but 36.4% into the BNS. The remaining gap is corpus composition and chunking.
3. **Retrieval-side fixes do not propagate to the answer.** The largest possible retrieval improvement — 0% to 100% — moved the answer's handling of the recodification by ~20 points, and that delta is not yet significant at n=33.

## What is not established

- Any citation-level claim on this set (attribution is broken, see above).
- That the answer improvement is real — intervals overlap; needs a larger set.
- Anything about procedure. The BNSS is not ingested, so `CrPC → BNSS` translations resolve to a corpus that does not exist and fall back to the CrPC with a warning.

## Next

1. Bind citations to their supporting chunk so statute attribution stops depending on proximity.
2. Re-run the comparison on the layman set — the queries this project exists for, where no code is named at all.
3. Investigate BNS chunking: the missing marginal notes are a plausible cause of the 36.4%, and it is testable by re-chunking that one PDF.
