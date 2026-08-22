# Open Questions

Unresolved items. **Nothing here gets deleted** — when a question is settled it moves to [Resolved](#resolved) with the answer and the date, so this file is also a record of settled uncertainty.

**Why it exists:** returning after six months, the costly gaps weren't forgotten *answers* — they were forgotten *questions*. Things half-noticed and never written down.

### Template

```markdown
## QNN · The question
**Raised:** YYYY-MM-DD · **Blocks:** what · **Effort to settle:** how long

**Why it matters.** …
**How to settle it.** …
**Current lean.** …
```

---

# Open

## Q1 · Does `gpt-5.2` reject `temperature=0`?
**Raised:** 2026-08-17 · **Blocks:** possibly everything · **Effort:** 2 minutes

**Why it matters.** `.env` sets `MODEL_NAME=gpt-5.2`. Both LLM call sites pass `temperature=0` — `clients/openai_client.py:15` (Intake) and `agents/answer.py:119` (Answer). GPT-5-family models reject non-default temperature with a 400.

If that's happening, both agents are failing into silent fallbacks: Intake returns a hardcoded `CaseContext` with `domain="General"` and `issues=[]`; Answer returns `"I'm sorry, I encountered an error generating the answer."` Both print and continue — nothing surfaces in the response.

Consequences if true: the domain fallback in `GAPS.md` #6 never fires (routing is blunter than described), and **every run made under this configuration is void**, including possibly the 23 baseline runs. It would also change the answer to Q2.

**How to settle it.**
```bash
python -c "from clients.openai_client import chat_json; print(chat_json([{'role':'user','content':'hi'}]))"
```

**Current lean.** Unknown — my probe couldn't reach the network. The architecture PDF says GPT-4o-mini throughout, so this is likely an untracked `.env` change made after February. Whatever the answer, pin the model explicitly and record it in `DECISIONS.md`.

---

## Q2 · Keep the 23 recorded runs as a baseline, or discard?
**Raised:** 2026-08-17 · **Blocks:** how results are framed · **Effort:** a judgement call, once Q1 is settled

**Why it matters.** `testing_results/` holds 23 runs across four categories. They contain the strongest evidence gathered so far — 6/7 answers citing unretrieved authority, 10/11 wrong-corpus routings. But they **predate commit `ce1bded`**: no `confidence` key in any captured JSON, and 15/15 citations everywhere, meaning zero adaptive filtering. They evaluate a system that no longer exists.

**Options.**

| | Pro | Con |
|---|---|---|
| **Keep as labelled pre-fix baseline** | Real evidence; the before/after delta is compelling; already collected | Confidence values are absent, so no calibration comparison; a reviewer may object to comparing across code versions |
| **Discard and re-run everything** | Clean, single code version, fully logged | Loses nothing recoverable — the *queries* can be reused, only the recorded outputs are lost |

**Current lean.** Reuse the **query text**, discard the **recorded outputs**. The queries are good and were written without knowledge of the failures, which makes them honest test cases. The outputs can't support calibration claims and inviting a cross-version comparison is a needless reviewer target. Re-running 23 queries after logging lands is cheap.

Depends on Q1: if the model was erroring, the runs are void regardless and this decides itself.

---

## Q3 · Ingest case law, or scope the evaluation to statutes?
**Raised:** 2026-08-17 · **Blocks:** `EVALUATION_PLAN.md` E1 composition · **Effort:** hours to decide, days to execute

**Why it matters.** The corpus is four statutes. No case law, no Constitution, no Evidence Act. Queries needing judgments — like the recorded *"Summarize Narinder Singh vs State of Punjab"* — can only ever fail.

The Router can already route to a `Judgments` corpus, and `intent = "case_law"` exists. The architecture anticipated case law that was never ingested.

**Options.**
- **Scope to statutes.** Honest, bounded, defensible: "we evaluate statutory retrieval." Requires excluding case-law queries from the eval set or marking them `answerable_from_corpus: false`.
- **Ingest judgments.** More realistic and enables the `Judgments` path — but adds a large, differently-structured corpus, and judgment text is far more heterogeneous than statutory text, likely shifting the whole score distribution the thresholds were tuned to.

**Current lean.** **Scope to statutes for this paper.** The contribution is failure analysis of routing, calibration, and citation support — all demonstrable on four statutes. Adding case law mid-evaluation introduces a confound and burns weeks. Keep unanswerable case-law queries in the set marked `answerable_from_corpus: false`; they test refusal, which is itself a finding. Note it in Limitations.

---

## Q4 · How should the entity-coverage neutral default be fixed?
**Raised:** 2026-08-17 · **Blocks:** `EVALUATION_PLAN.md` P5, E3, E5 · **Effort:** a design decision plus a few lines

**Why it matters.** Separate from the counting bug (`GAPS.md` #1), which is mechanical. When no entity is extracted, `entity_coverage = 1.0` and the signal pays its full 0.30 — which, against a HIGH threshold of 0.55, means essentially every no-entity query lands in HIGH. That is the majority of layman queries, the system's core population. See the worked trace in `DATAFLOW.md`: an arrest query retrieving chunks about child trafficking scores 0.66 HIGH.

**Options.**

| Approach | How | Trade-off |
|---|---|---|
| **Renormalise** | Drop signal 3; rescale signals 1 and 2 to sum to 1.0 | Clean, principled. Changes the meaning of the number across query types — two queries with the same score were computed differently |
| **Penalty not bonus** | Start from signals 1+2; *subtract* for missing entities | Never inflates. Compresses the range; needs re-tuning thresholds |
| **Explicit state** | Report `entity_coverage: null` and a separate `has_entities` flag; two tier tables | Most honest, best for the paper — you can report calibration separately for entity and non-entity queries. Most work |
| **Neutral = mean of others** | Set signal 3 to the weighted mean of signals 1–2 | Contributes neither bonus nor penalty. Simple, slightly ad hoc |

**Current lean.** **Explicit state** for the research, because it gives two clean sub-populations to calibrate separately — likely a more interesting result than a single curve. If that's too much work, **renormalise**, and disclose it.

Whichever is chosen needs a `DECISIONS.md` entry superseding ADR-008, and the old implementation kept behind a flag for the E5 ablation.

---

## Q5 · Confirm two venue deadlines
**Raised:** 2026-08-17 · **Blocks:** submission planning · **Effort:** 20 minutes of searching

**Why it matters.** Two entries in `RESEARCH_CONTEXT.md` are unconfirmed:
- **Insights from Negative Results in NLP** @ EMNLP — "expected around September." Possibly the most natural home if the work is framed as failure analysis.
- **CODS 2026** (ACM India, Gandhinagar, December) — "deadline not yet announced."

**How to settle it.** Check both CFPs. Also re-confirm ARR's 12 October cycle date.

**Current lean.** ARR on 12 October is the primary target regardless — it's late enough to do the work properly and lets the venue be chosen after reviews. These two are alternatives, not the plan.

---

## Q6 · Should `README.md` be reconciled now or after the fixes?
**Raised:** 2026-08-17 · **Blocks:** nothing · **Effort:** an hour

**Why it matters.** `README.md` documents `retrieve/mmr.py` (doesn't exist), claims the Retriever does MMR and evidence packing (it does neither), and lists the orphaned `retrieve/` and `answer/` trees as live. It is the first thing a visitor to the repo reads.

**Current lean.** **After the fixes.** Rewriting it now means rewriting it twice, and `docs/` already carries accurate information. Logged in `STATE.md` as deferred. If the repo is shared with anyone before then, add a one-line pointer to `docs/STATE.md` at the top.

---

# Resolved

*Nothing yet. When a question is settled, move it here with the answer, the date, and what changed as a result.*

### Template

```markdown
## QNN · The question ✅
**Raised:** YYYY-MM-DD · **Resolved:** YYYY-MM-DD

**Answer.** …
**Evidence.** …
**Changed as a result.** … (link the ADR or commit)
```

---

## Q4 — How should the entity-coverage neutral default be fixed?
**Raised:** 2026-08-17 · **Settled:** 2026-08-23

**Answer: make it 0.5 and keep the flag.**

When no entity is extracted the signal is UNKNOWN, not perfect. It used to be 1.0, handing its full 0.30 weight to every query naming no section. Since the HIGH tier starts at 0.55, that free 0.30 alone carried mediocre retrieval over the line — and layman queries, the ones this project exists for, name a section almost never. The system was most confident exactly where it had least evidence.

`ENTITY_NEUTRAL = 0.5` neither rewards nor punishes a signal that could not be computed. `entity_coverage_default_used` is still logged on every run, so the ablation can recompute the old behaviour offline without re-querying.

Measured effect: a no-entity query on mediocre scores `[0.41, 0.40, 0.39, 0.39, 0.38]` went from clearing HIGH to **0.5017**, below the threshold.

Rejected alternatives: *renormalise the remaining weights* (makes runs with and without entities incomparable, breaking the E6 ablation); *penalise with 0.0* (punishes a query for a property of the extractor rather than of the retrieval).

---

## Q7 — Should the corpus be extended to the BNSS and BSA?
**Raised:** 2026-08-23 · **Blocks:** 5 layman rows, all 10 CrPC→BNSS map entries · **Effort:** ~1 hour ingest + rebuild

**Why it matters.** The index holds IPC, BNS, CrPC and CPA. The BNSS (procedure) and BSA (evidence) are absent, so any query about post-2024 procedure is unanswerable **by construction** — not because the system failed, but because we never loaded the law. Those rows currently carry `answerable_from_corpus: false` and are scored as refusal tests rather than retrieval tests.

**Why it was NOT done in Phase E.** It is a scope change, not a defect fix, and the plan is frozen through Phase G. Adding a corpus mid-stream would also make the Phase G numbers incomparable with the baseline they are meant to establish.

**Current lean.** Do it between G and H, so the intervention phase has a symmetric corpus: with the BNSS present, both halves of the CrPC↔BNSS pair become measurable and the paired set roughly doubles. Decide after seeing whether the IPC↔BNS result is strong enough on its own.
