# Phase G — first clean evaluation

**Code:** `5184e78` (runs) · `3b8381c`+ (analysis) · **Index:** 1,899 chunks · **Date:** 2026-08-23
**Model:** `google/gemini-3.7-flash` via OpenRouter, provider pinned `google-ai-studio`, `temperature=0`, `seed=20260822`
**Embeddings:** `openai/text-embedding-3-small`, provider pinned `openai`, 1536-d, cosine
**Scale:** 419 queries across three sets, 0 transport errors

Reproduce:

```bash
python scripts/analyze_eval.py --runs runs/eval_2026-08-23_0215_5184e78 \
                                      runs/eval_2026-08-23_0231_5184e78 \
                                      runs/eval_2026-08-23_0256_5184e78
python scripts/ablate_filter.py
```

These are the **first numbers from code with no known metric defects.** Everything before `36ec68d` is void — see `docs/WORKLOG.md` 2026-08-23 for the eight fixes and what each was silently producing.

Every proportion carries a **95% Wilson interval** — the range the true value plausibly lies in. At n≈33 those are ±15 points wide. Read the overlap, not the point estimate.

*The analyzer deduplicated 120 repeated rows. `eval_summary.jsonl` is append-only and killed-then-resumed runs re-append; duplicates would inflate both halves of every k/n proportion, and unevenly, since the repeats are whichever queries were in flight when a run died.*

---

## The three query sets

| Set | N | What it is | What it tests |
|---|---|---|---|
| `generated_retrieval` | 200 | question built **from** a section, so the gold is certain by construction | the instrument, under ideal conditions |
| `paired_recodification` | 99 | 33 verified IPC↔BNS provision pairs × 3 phrasings | **the thesis** |
| `layman_situation` | 120 | 30 real distress situations × 4 date conditions | **the claim** |

---

## The headline: cross-statute retrieval failure is real, and asymmetric

`python scripts/ablate_filter.py` — corpus filter disabled, retrieval only, 66 queries that each name their code explicitly. "Chance" = the share of the index that code occupies, i.e. how often it would win if retrieval ignored the question entirely.

| Query explicitly names | → IPC | → BNS | correct | chance |
|---|---|---|---|---|
| **the Indian Penal Code** (repealed 2024) | 32 | 1 | **97.0%** [84.7, 99.5] | 31.3% |
| **the Bharatiya Nyaya Sanhita** (in force) | **16** | 17 | **51.5%** [35.2, 67.5] | 22.3% |

Top-1 chunk only:

| Query names | → IPC | → BNS | correct |
|---|---|---|---|
| IPC | 30 | 3 | 90.9% [76.4, 96.9] |
| BNS | **19** | 14 | **42.4%** [27.2, 59.2] |

**A query saying "Section 318(4) of the Bharatiya Nyaya Sanhita" gets an IPC chunk as its top result 19 times out of 33.**

Naming the IPC lifts retrieval from 31.3% chance to 97%. Naming the BNS lifts it from 22.3% to 51.5% — real, but weak, and the misses land overwhelmingly on the repealed code rather than scattering across the index. The failure is **directional**.

### Why the main evaluation appeared to show the opposite

The joined run reported a **perfect** confusion matrix — 33/33 and 33/33, zero off-diagonal. That is not a result. The Router reads the Act name and applies a hard Qdrant filter:

```
ipc_numbered   filter=IPC     33
bns_numbered   filter=BNS     33
neutral_topic  filter=None    33
```

With the filter on, an IPC-numbered query **cannot** return a BNS chunk. The diagonal was guaranteed before any vector was compared — it measures a keyword lookup.

**The routing was hiding the phenomenon the paper is about.** This is the most important methodological point in this document.

---

## E0 · Is this actually retrieval-augmented?

| Query set | N | gold **retrieved** (strict) | (lenient) | gold **cited** | gap |
|---|---|---|---|---|---|
| generated (ideal conditions) | 200 | **68.0%** [61.2, 74.1] | 69.0% | 98.5% [95.7, 99.5] | +30.5 pp |
| paired | 99 | 71.7% [62.2, 79.6] | 93.9% | 100.0% [96.3, 100.0] | +28.3 pp |
| **layman** | 120 | **7.5%** [4.0, 13.6] | 8.3% | **85.0%** [77.5, 90.3] | **+77.5 pp** |

Two separate findings here.

**First — even under ideal conditions retrieval misses a third of the time.** The generated queries are built *from* the section and name its number outright: *"What does Section 378 of the Indian Penal Code provide?"* Retrieval still fails to return that section 32% of the time. That is a ceiling on everything else.

**Second — for layman queries the pipeline is barely retrieval-augmented.** A worked example from the run:

```
query      "i was sexually assaulted ... it has been long time now"
gold       IPC 376
retrieved  IPC 354, CrPC 473, CrPC 303        <- 376 is absent
cited      IPC 354, 354A, 376, 376(2), CrPC 473, CrPC 357A, LSA 12
grounded   IPC 354, CrPC 473                  <- only these two
```

It **cited IPC 376 without retrieving it.** It names the right provision nine times in ten while retrieval supplies it once in ten. The answers come from the language model's own knowledge of Indian law, not from the corpus. Confirmed independently below: **83.8%** of what layman answers cite is absent from the passages the model was given.

*Strict vs lenient: lenient lets a sub-section match its parent — right for "BNS 318(4)" against a chunk headed "Section 318", wrong for "IPC 498A" against "IPC 498", since 498A is a separate offence inserted in 1983. Strict is the floor and is what every claim uses.*

---

## E1b · With no code named, which code does it reach for?

`neutral_topic` asks *"What is the law on X in India?"* — no section, no Act. There is no correct answer without a date, so this measures **lean**.

| | share |
|---|---|
| dominated by **IPC** (repealed) | **81.8%** [65.6, 91.4] |
| dominated by BNS (in force) | 18.2% [8.6, 34.4] |
| retrieved the repealed IPC provision | **93.9%** [80.4, 98.3] |
| retrieved the current BNS provision | 36.4% [22.2, 53.4] |

Asked a neutral question about Indian criminal law, the system answers out of the repealed code five times out of six.

---

## E2 · The date experiment — the system does not use the date

30 situations × 4 date conditions. Non-control, answerable rows only.

| variant | N | gold retrieved | gold cited | corpus correct |
|---|---|---|---|---|
| `no_date` | 28 | 7.1% [2.0, 22.6] | 96.4% [82.3, 99.4] | 35.7% [20.7, 54.2] |
| `ipc_era` "in March 2023" | 28 | 10.7% [3.7, 27.2] | 89.3% [72.8, 96.3] | 28.6% [15.3, 47.1] |
| `bns_era` "last month" | 23 | 8.7% [2.4, 26.8] | **60.9%** [40.8, 77.8] | **17.4%** [7.0, 37.1] |
| `vague` | 28 | 10.7% [3.7, 27.2] | 92.9% [77.4, 98.0] | 46.4% [29.5, 64.2] |

Retrieval is flat across all four — stating when it happened changes nothing, as expected since **there is no Date Resolver**. This is the "before" baseline Phase H is measured against.

The `gold cited` column is the interesting one. It holds near 90–96% everywhere **except** `bns_era`, where it falls to 60.9%. Told the conduct happened last month — so the BNS governs — the system is markedly worse at naming the provision that actually applies, because it keeps reaching for the IPC.

**Controls (CPA, untouched by the recodification):** 0.0% gold retrieved in all four conditions. Flat, as a control should be, but at zero — the gold label `CPA 2` is the Act's *definitions* section, a poor retrieval target. **This gold needs rewriting before the control means anything.**

---

## E3 · Citation grounding

| Query set | N | cited/answer | ungrounded | out-of-corpus | panel↔prose Jaccard | cited successor |
|---|---|---|---|---|---|---|
| generated | 200 | 6.9 | 0.519 | 0.143 | 0.218 | **0.81** |
| paired | 99 | 6.5 | 0.623 | 0.127 | 0.192 | 0.58 |
| layman | 120 | 8.2 | **0.838** | 0.121 | 0.115 | 0.48 |

- **ungrounded** — cited but not present in the retrieved passages. Not the same as *wrong*: a provision can be correct law and still be ungrounded.
- **panel↔prose Jaccard 0.115–0.218** — the "Sources" list shown to the user overlaps the provisions the prose cites by 12–22%. A user who diligently checks every listed source will mostly not find the provision the answer relied on. *(This metric returned 0.0 on perfect grounding until `36ec68d`; these are the first real values it has produced.)*
- **cited successor 0.48–0.81 per answer** — on the generated set, four answers in five cite a BNSS or BSA provision while the index holds only the CrPC. One-directional: `cited_predecessor` is **0.00** everywhere.

---

## E4 · Does confidence detect any of this?

AUROC — the probability the score ranks a good answer above a bad one. **0.5 means the score carries no information whatsoever.** 419 queries, 27 fully grounded.

| | AUROC | positives |
|---|---|---|
| **`entity_coverage` vs fully grounded** | **0.492** | 27/419 |
| composite confidence vs fully grounded | 0.610 | 27/419 |
| `score_gap` vs fully grounded | 0.645 | 27/419 |
| `top_k_mean` vs fully grounded | 0.659 | 27/419 |
| **raw max similarity vs fully grounded** | **0.663** | 27/419 |

Two results here, both negative, both worth reporting.

**1. `entity_coverage` is worthless.** 0.492 is chance. One of the three signals in the composite score contributes nothing — and it carries 30% of the weight.

**2. The composite is worse than the raw number it was built to improve on.** Combining three signals (0.610) performs *below* simply using the top similarity score (0.663). The weighting is destroying information rather than adding it.

**Only 27 of 419 answers (6.4%) were fully grounded** — every provision they cited was actually in the retrieved passages.

Two rows must **not** be read as success:

| | Why it is confounded |
|---|---|
| composite vs gold retrieved = 0.927 | Both are largely proxies for *"did the query name a section"*. E7 shows the same split directly. It detects query type, not answer quality. |
| composite vs gold cited = 0.761 | The model cites the gold ~90% of the time regardless, from memory (see E0). |

---

## E5 · Refusal — the gate never fired

**0 refusals out of 419**, including all 5 rows whose gold is unreachable because the BNSS is not ingested.

This is the E7 design behaving exactly as documented. The gate keys on **named statutes**, and no layman query names one. It was built that way because a similarity threshold provably cannot work here: the highest out-of-corpus score (0.519, Hindu Marriage Act) exceeds five of six in-corpus scores, the lowest being 0.278 (`docs/DECISIONS.md`, corpus-boundary ADR).

Honest statement: **the system has no working abstention mechanism for the queries it will actually receive.** The gate covers only users who name an Act.

---

## E6 · Messiness — confounded, do not report

| messiness | N | gold retrieved | gold cited | mean confidence |
|---|---|---|---|---|
| 1 (fairly clear) | 20 | 0.0% [0.0, 16.1] | 85.0% | 0.451 |
| 2 (typical) | 57 | 0.0% [0.0, 6.3] | 84.2% | 0.465 |
| 3 (very fragmented) | 38 | 26.3% [15.0, 42.0] | 92.1% | 0.465 |

Runs **backwards** — the messiest queries retrieve best. A confound, not a finding: messiness 1 is dominated by the well-written consumer scenarios whose gold is `CPA 2`, a definitions section that never retrieves. Topic and messiness are entangled.

Fixing it needs messiness varied *within* topic — the same situation written three ways — which the set does not do.

---

## E7 · Routing

| decision path | N | gold retrieved |
|---|---|---|
| `act_map_single` (Act named → filtered) | 211 | **65.9%** [59.2, 71.9] |
| `no_match` (no Act named → no filter) | 208 | 49.0% [42.3, 55.8] |

Filter fallback fired: **0/419** — the stale `ACT_MAP` entry fixed in Phase E is confirmed gone.

Naming a statute is worth ~17 points. But note this understates the gap for real users: restricted to the layman set alone the split is 28.9% vs 85.7%, because the generated set names sections everywhere.

---

## What this changes

**Established, and strong enough to build a paper on:**

1. **Cross-statute retrieval failure exists, is asymmetric, and favours the repealed code** — 97.0% vs 51.5% when the code is named explicitly.
2. **The routing filter hides it.** A system that looks correct only because it was never given the chance to be wrong.
3. **For layman queries the pipeline is barely retrieval-augmented** — 7.5% retrieved vs 85.0% cited, 83.8% ungrounded.
4. **The composite confidence score is worse than a single raw similarity number**, and one of its three signals is at chance.
5. **Retrieval has a hard ceiling of ~68%** even when the query names the section it wants.

**Not established. Do not claim:**

- Anything from the messiness table — confounded with topic.
- Any effect of the CPA controls — the gold label is a definitions section.
- Anything about procedural queries in the BNS era — the BNSS is not ingested.

**Next, in order:**

1. Re-gold the CPA control rows away from `CPA 2`.
2. Vary messiness within topic so E6 becomes interpretable.
3. Run the filter ablation across the layman set too, not just the paired set.
4. Then Phase H — Date Resolver and Statute Mapper — measured against these baselines.
