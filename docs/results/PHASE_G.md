# Phase G — first clean evaluation

**Code:** `5184e78` (evaluation runs) · `0bd0659` (analysis) · **Index:** 1,899 chunks · **Date:** 2026-08-23
**Model:** `google/gemini-3.7-flash` via OpenRouter, provider pinned to `google-ai-studio`, `temperature=0`, `seed=20260822`
**Embeddings:** `openai/text-embedding-3-small`, provider pinned to `openai`, 1536-d, cosine

Reproduce:

```bash
python scripts/analyze_eval.py --runs runs/eval_2026-08-23_0215_5184e78 runs/eval_2026-08-23_0231_5184e78
python scripts/ablate_filter.py
```

These are the **first numbers from a version of the code with no known metric defects.** Everything before commit `36ec68d` is void — see `docs/WORKLOG.md` 2026-08-23 for the eight fixes and what each was producing.

Every proportion carries a **95% Wilson interval**. At n≈33 those intervals are roughly ±15 points wide. Read the overlap, not the point estimate.

---

## The headline: cross-statute retrieval failure is real, and it is asymmetric

`python scripts/ablate_filter.py` — corpus filter disabled, retrieval only, 66 queries that each name their code explicitly.

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

Naming the IPC lifts retrieval from a 31.3% chance baseline to 97%. Naming the BNS lifts it from 22.3% to 51.5% — real, but far weaker, and the misses land overwhelmingly on the repealed code rather than being spread across the index. The failure is **directional**: the system is pulled toward the IPC.

### Why the main evaluation appeared to show the opposite

The joined run reported a **perfect** confusion matrix — 33/33 and 33/33, zero off-diagonal. That is not a result. The Router reads the Act name and applies a hard Qdrant filter:

```
ipc_numbered   filter=IPC     33
bns_numbered   filter=BNS     33
neutral_topic  filter=None    33
```

With the filter on, an IPC-numbered query **cannot** return a BNS chunk. The diagonal was guaranteed before any vector was compared. It measures a keyword lookup, not retrieval.

This is the single most important methodological point in this document: **the filter was hiding the phenomenon the paper is about.**

---

## E0 · Is this actually retrieval-augmented?

| Query set | N | gold retrieved (strict) | gold retrieved (lenient) | gold **cited** | gap |
|---|---|---|---|---|---|
| layman | 120 | **7.5%** [4.0, 13.6] | 8.3% [4.6, 14.7] | **85.0%** [77.5, 90.3] | **+77.5 pp** |
| paired | 99 | 71.7% [62.2, 79.6] | 93.9% [87.4, 97.2] | 100.0% [96.3, 100.0] | +28.3 pp |

A worked example from the run:

```
query      "i was sexually assaulted ... it has been long time now"
gold       IPC 376
retrieved  IPC 354, CrPC 473, CrPC 303        <- 376 is absent
cited      IPC 354, 354A, 376, 376(2), CrPC 473, CrPC 357A, LSA 12
grounded   IPC 354, CrPC 473                  <- only these two
```

The system **cited IPC 376 without retrieving it.** For layman queries it names the right provision about nine times in ten while retrieval supplies it about once in ten. The answers are coming from the language model's own knowledge of Indian law, not from the corpus.

Confirmed independently by the citation audit below: **83.8%** of everything the layman answers cite is not in the passages the model was given.

The retrieval step is close to decorative for exactly the users this system exists to serve.

*Strict vs lenient: lenient lets a sub-section match its parent, which is right for "BNS 318(4)" against a chunk headed "Section 318" but wrong for "IPC 498A" against "IPC 498" — 498A is a separate offence inserted in 1983. Strict is the floor and is what any claim uses.*

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

Retrieval is flat across all four — stating when it happened changes nothing, which is expected because **there is no Date Resolver**. This is the "before" baseline the Phase H intervention gets measured against.

The interesting column is `gold cited`. It holds near 90–96% in every condition **except** `bns_era`, where it falls to 60.9%. When told the conduct happened last month — so the BNS governs — the system is markedly worse at naming the provision that actually applies, because it keeps reaching for the IPC.

**Controls (CPA, untouched by the recodification):** 0.0% gold retrieved in all four conditions. Flat, as a control should be, but the level is zero — the gold label `CPA 2` is the Act's *definitions* section, a poor retrieval target. That gold needs rewriting before the control means anything.

---

## E3 · Citation grounding

| Query set | N | cited/answer | ungrounded | out-of-corpus | panel↔prose Jaccard | vintage: cited successor |
|---|---|---|---|---|---|---|
| layman | 120 | 8.2 | **0.838** | 0.121 | 0.115 | 0.48 |
| paired | 99 | 6.5 | 0.623 | 0.127 | 0.192 | 0.58 |

- **ungrounded** — cited but not present in the retrieved passages. Not the same as *wrong*: a provision can be correct law and still be ungrounded.
- **panel↔prose Jaccard 0.115** — the "Sources" list shown to the user overlaps the provisions the prose actually cites by about 11%. A diligent user who checks every listed source will mostly not find the provision the answer relied on. *(This metric returned 0.0 on perfect grounding until commit `36ec68d`; these are the first real values it has ever produced.)*
- **cited successor 0.48–0.58 per answer** — roughly every second answer cites a BNSS/BSA provision while the index holds only the CrPC. Direction is one-way: `cited_predecessor` is **0.00** everywhere.

---

## E4 · Does confidence detect any of this?

AUROC — probability the score ranks a good answer above a bad one. 0.5 = no information.

| | AUROC | positives |
|---|---|---|
| composite vs gold retrieved | 0.939 | 103/219 |
| composite vs gold cited | 0.710 | 201/219 |
| composite vs fully grounded | 0.744 | **2/219** |
| top_k_mean vs fully grounded | 0.861 | 2/219 |
| score_gap vs fully grounded | 0.770 | 2/219 |
| entity_coverage vs fully grounded | 0.614 | 2/219 |
| raw max similarity vs fully grounded | 0.825 | 2/219 |

**Two caveats that make most of this table unusable as it stands:**

1. **Only 2 of 219 answers were fully grounded.** Every "vs fully grounded" row rests on two positive examples. Those AUROCs are noise and must not be reported as findings. The number that matters here is the 2/219 itself.
2. **`composite vs gold retrieved` = 0.939 is confounded.** Confidence is driven by `top_k_mean`, and both confidence and retrieval success are largely proxies for *"did the query name a section"*. The score is detecting query type, not answer quality. E7 shows the same split directly.

A properly powered version needs a graded quality label rather than an all-or-nothing one.

---

## E5 · Refusal — the gate never fired

**0 refusals out of 219**, including all 5 rows whose gold is unreachable because the BNSS is not ingested.

This is the documented limitation of the E7 design behaving exactly as documented. The gate keys on **named statutes**, and no layman query names one. It was built that way because 15 probe queries showed a similarity threshold cannot work here — the highest out-of-corpus score (0.519, Hindu Marriage Act) exceeds five of six in-corpus scores, the lowest of which is 0.278 (`docs/DECISIONS.md`, ADR on the corpus boundary).

So the honest statement is: **the system has no working abstention mechanism for the queries it will actually receive.** The gate covers only the case where a user names an Act by name.

---

## E6 · Messiness — confounded, do not report yet

| messiness | N | gold retrieved | gold cited | mean confidence |
|---|---|---|---|---|
| 1 (fairly clear) | 20 | 0.0% [0.0, 16.1] | 85.0% | 0.451 |
| 2 (typical) | 57 | 0.0% [0.0, 6.3] | 84.2% | 0.465 |
| 3 (very fragmented) | 38 | 26.3% [15.0, 42.0] | 92.1% | 0.465 |

This runs **backwards** — the messiest queries retrieve best. It is a confound, not a finding: messiness 1 is dominated by the well-written consumer scenarios whose gold is `CPA 2`, a definitions section that is never retrieved. Topic and messiness are entangled in the current set.

Fixing this needs messiness varied *within* topic — the same situation written three ways — which the set does not currently do.

---

## E7 · Routing

| decision path | N | gold retrieved |
|---|---|---|
| `no_match` (no Act named → no filter) | 149 | 28.9% [22.2, 36.6] |
| `act_map_single` (Act named → filtered) | 70 | **85.7%** [75.7, 92.1] |

Filter fallback fired: **0/219** — the stale `ACT_MAP` entry fixed in Phase E is confirmed gone.

The gap is the whole problem in one line. Name a statute and retrieval works. Describe your situation in your own words and it does not.

---

## What these results change

**Confirmed, and strong enough to build a paper on:**
1. Cross-statute retrieval failure exists, is asymmetric, and favours the **repealed** code (97% vs 51.5%).
2. The routing filter *hides* it — a system that looks correct only because it never had the chance to be wrong.
3. For layman queries the pipeline is barely retrieval-augmented: 7.5% retrieved vs 85.0% cited, 83.8% ungrounded.

**Not yet established, and must not be claimed:**
- Anything from the messiness table (confounded).
- Any confidence AUROC against groundedness (2 positives).
- Anything about procedural queries in the BNS era (the BNSS is not ingested).

**Next, in order:**
1. Re-gold the CPA control rows away from the definitions section.
2. Build a graded answer-quality label so E4 has more than two positives.
3. Vary messiness within topic so E6 is interpretable.
4. Then Phase H: Date Resolver and Statute Mapper, measured against these baselines.
