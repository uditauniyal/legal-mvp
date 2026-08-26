# Legal MVP — Current State

**Read this first.** Rewritten **2026-08-26** for whoever opens this repo cold — including a future Udita, or a Claude session with no memory of the last one.

The previous version of this file was written on 2026-08-17 and said *"no fixes have been applied."* That is no longer true. Phases E, F, G and H are done. If you are reading a printed or cached copy dated before 26 August, discard it.

---

## Where things stand, in one paragraph

The system is built, runs end to end, and has now been **measured properly for the first time**. Eight defects in the measuring equipment were fixed first (Phase E), four query sets were built (Phase F), a 419-query baseline was recorded (Phase G), and an intervention — a Date Resolver and a Statute Mapper — was built and measured against that baseline on 198 more queries (Phase H). **There is a real, defensible research finding**, plus two honest negative results. The test suite is at **142 passing**. Every number in `docs/results/` carries the git commit that produced it.

---

## The finding, in one table

Search with the corpus filter switched off, on 66 questions that each name their code outright. "Chance" is the share of the index that code occupies — what you would get by ignoring the question entirely.

| The question names… | found the right code | chance |
|---|---|---|
| the **IPC** — repealed 1 July 2024 | **97.0%** [84.7, 99.5] | 31.3% |
| the **BNS** — currently in force | **51.5%** [35.2, 67.5] | 22.3% |

A query saying *"Section 318(4) of the Bharatiya Nyaya Sanhita"* gets an **IPC** passage as its top result **19 times out of 33**. Cross-statute retrieval failure is real, and it is **directional — toward the repealed code**.

Reproduce: `python scripts/ablate_filter.py`

**The methodological point that matters more than the number:** the main evaluation table showed a *perfect* result — 33/33 and 33/33, zero errors — because the Router reads the Act name and applies a hard corpus filter, so an IPC-numbered query *cannot* return a BNS chunk. The diagonal was guaranteed before any vector was compared. **The routing was hiding the phenomenon the paper is about.** Any write-up must say this.

---

## Two more results

**The pipeline is barely retrieval-augmented for layman queries.** Gold provision retrieved **7.5%**, gold provision cited **85.0%**, ungrounded rate **83.8%**. The answers come from the language model's own knowledge of Indian law, not from the corpus. (`docs/results/PHASE_G.md`)

**Fixing retrieval did not fix the answer.** The Phase H intervention took correct-corpus routing from **0.0% → 100.0%** and wrong-era retrieval from **81.8% → 0.0%**, with the control unmoved. The answer's handling of the recodification moved by roughly 20 points and still fails a third of the time — and that delta is *not* statistically established at n=33. (`docs/results/PHASE_H.md`)

---

## Current facts

| | |
|---|---|
| Index | **1,899 chunks** — CrPC 742 (39.1%) · IPC 595 (31.3%) · BNS 424 (22.3%) · CPA 138 (7.3%) |
| Absent from corpus | **BNSS, BSA**, Constitution, Evidence Act, case law, NI Act, Contract Act |
| Embedding | `openai/text-embedding-3-small`, 1536-d, cosine, provider pinned to `openai` |
| Generation | `google/gemini-3.7-flash` via OpenRouter, provider pinned `google-ai-studio`, `temperature=0`, `seed=20260822` |
| Typical scores | **0.28–0.77**. Every threshold is tuned to this range |
| Tests | **142 passing** (`python -m pytest tests/ -q`) |
| Cost | ~$0.0059 (≈ ₹0.50) and ~25 s per query |
| Query sets | layman 120 · paired 99 · paired-dated 99 · generated 200 |

---

## Reading order

Start here, then:

| Doc | What it gives you |
|---|---|
| [`results/PHASE_G.md`](results/PHASE_G.md) | **The baseline.** Every table with 95% confidence intervals, plus an explicit "do not claim" section |
| [`results/PHASE_H.md`](results/PHASE_H.md) | **The intervention**, measured against that baseline |
| [`WORKLOG.md`](WORKLOG.md) | What happened and when. Append-only |
| [`DECISIONS.md`](DECISIONS.md) | Why things are the way they are. Append-only |
| [`OPEN_QUESTIONS.md`](OPEN_QUESTIONS.md) | What is unresolved, and how to settle each one |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | How the system works, plain language through line-level |
| [`DATAFLOW.md`](DATAFLOW.md) | One query traced with real values |
| [`GAPS.md`](GAPS.md) | The original 23 findings. **Now partly historical** — see below |
| [`RESEARCH_CONTEXT.md`](RESEARCH_CONTEXT.md) | The paper: framing, literature, supervisor's directive, venues |

⚠ **`GAPS.md`, `ARCHITECTURE.md`, `FILE_STRUCTURE.md` and `DATAFLOW.md` predate Phase E** and still describe defects that are fixed. Trust `WORKLOG.md` and `docs/results/` over them where they disagree.

---

## What is new since 2026-08-17

**Phase E — eight defects fixed.** Every one produced a *believable wrong number* rather than an error, which is why they survived.

| | What it was doing |
|---|---|
| E1 | 23 of 24 date rows scored **backwards** — citing current law counted as wrong |
| E2 | `panel_prose_jaccard` returned **0.0 on perfect grounding**, always |
| E3 | `entity_coverage` reached **5.0** on a 0–1 scale; a cap hid it |
| E4 | `top_score` read after reranking had scrambled the order |
| E5 | "vintage error" mislabelled; now split by direction |
| E6 | 14 contents entries + 13 footnotes indexed as law; **all 13 footnotes collided with a real section number** |
| E7 | Out-of-corpus query returned **HIGH confidence 0.73** |
| E8 | Router made the IPC **unreachable** unless named — would have decided the date experiment by default |

**Phase F — four query sets, 518 queries.** Including `eval/paired_queryset.jsonl` (33 verified IPC↔BNS pairs — the set that tests the thesis) and `eval/paired_dated_queryset.jsonl` (where the code named and the date given deliberately disagree).

**Phase G — 419 queries, 0 transport errors.** The baseline.

**Phase H — two new components, measured.**

| | File | What it does |
|---|---|---|
| Date Resolver | `core/dates.py` | Reads *when* the conduct happened → `IPC_ERA` / `BNS_ERA` / `BOTH_ERAS` / `UNKNOWN` |
| Statute Mapper | `core/statute_mapper.py` | Translates the citation to the code that governs, and moves the corpus filter |

Both are **off by default**. Mode is `baseline` / `date` / `mapper` / `both`, set per request or via the `INTERVENTION` environment variable, so the Phase G baseline stays reproducible.

**New data artifact:** `data/recodification_map.json` — 33 IPC→BNS mappings, each confirmed by pulling the target section out of this index and reading its bare-Act text, plus 10 CrPC→BNSS marked `unverified_not_in_corpus`.

---

## What must NOT be claimed

This list is as important as the findings. It is reproduced in both results documents.

| Claim | Why it fails |
|---|---|
| Anything from the **messiness** table | Runs backwards. Confounded — the clearest queries are the consumer ones whose gold is `CPA 2`, a definitions section that never retrieves |
| Any **citation-level** number where both codes appear | `core/citations.py` attributes a statute by proximity in the answer text. An answer citing **BNS 190** was recorded as `IPC Section 190` because "Indian Penal Code" appeared earlier. See `OPEN_QUESTIONS.md` Q8 |
| Any confidence **AUROC vs groundedness** as a headline | Only 27 of 419 answers were fully grounded |
| Anything about **BNS-era procedure** | The BNSS is not ingested; those golds are unreachable by construction |
| That the **Phase H answer improvement** is real | Intervals overlap: 39.4% [24.7, 56.3] vs 63.6% [46.6, 77.8] |

---

## Next, in order

1. **Bind each citation to the chunk that supports it** (`OPEN_QUESTIONS.md` Q8). The chunk payload already carries an authoritative `corpus` field. Unblocks three metrics at once. ~half a day.
2. **Re-run the Phase H comparison on the layman set.** The intervention is proven only on queries that name a code. The queries this project exists for name nothing.
3. **Re-chunk the BNS PDF** (Q9). With routing perfect, section-level retrieval is 78.8% into the IPC but **36.4%** into the BNS. The BNS PDF has no marginal notes, so chunks open mid-clause instead of with their subject. ~2 hours, and it is testable.
4. **Re-gold the CPA control rows** away from `CPA 2`, and vary messiness *within* topic.
5. **Then write.** Target: **ARR, 12 October 2026.**

Phase I (multilingual) remains optional and droppable. Nothing has changed about it.

---

## Running it

```bash
docker compose up -d                  # Qdrant :6333
uvicorn app:app --reload              # backend :8000
streamlit run streamlit_app.py        # UI :8501
python -m pytest tests/ -q            # 142 tests
```

Rebuild the index: `python scripts/reingest.py --dry-run` first, then without the flag.
Virtualenv is `venv/` (`./venv/Scripts/python.exe` on Windows).

### Two things not to do

⚠ **Do not `pip install -r requirements.txt`** unless it has been regenerated — the original listed none of this project's real dependencies.

⚠ **Do not run `fix_corpus_tags.py`.** It patches the database instead of the code. That is what hid the corpus-tagging defect for six months.

---

## Session continuity

The conversation transcript is a **local file**, not account-bound:

```
C:\Users\uniya\.claude\projects\C--Users-uniya-legal-mvp\<session-id>.jsonl
```

Retention is set to 3650 days in `.claude/settings.json`. `claude --resume` inside the project directory lists past sessions.

**But the repository is the real state, not the chat.** This file plus `docs/results/` and `WORKLOG.md` should be enough to resume with no conversation history at all. If they are not, that is a bug in the documentation, and fixing it takes priority over whatever else is queued.
