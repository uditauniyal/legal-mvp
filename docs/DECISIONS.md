# Decision Log

**Why this exists.** Code shows *what*. This shows *why*. When you return in six months and wonder "why is `target_corpus` set to `None` for civil queries?", the answer should be here rather than requiring you to re-derive it from source.

**Format:** lightweight ADRs (Architecture Decision Records), newest first. Never delete an entry — supersede it, and link forward.

### Template

```markdown
## ADR-0NN · Title
**Date:** YYYY-MM-DD · **Status:** Accepted | Superseded by ADR-0MM | Reconsidering

**Context.** What situation forced a choice.
**Decision.** What was chosen.
**Alternatives.** What else was on the table, and why it lost.
**Consequences.** What this costs, including the bad parts.
```

> **ADR-001 to ADR-009 are reconstructed** from code, comments, and the architecture PDF — no contemporaneous record was kept. Dates come from git. Where the rationale is inferred rather than documented, it says so. **This reconstruction is exactly the work this log exists to make unnecessary next time.**

---

## ADR-011 · Understand before fixing
**Date:** 2026-08-17 · **Status:** Accepted

**Context.** Returning after ~6 months, the architecture was no longer understood. A review had surfaced three blocking defects, and the temptation was to fix them immediately — the evaluation is on a deadline.

**Decision.** Write the full documentation set first. No source changes until the architecture is re-understood and `GAPS.md` has been read adversarially and challenged.

**Alternatives.**
- *Fix first, document after* — faster to visible progress, but fixes to a system you don't understand tend to be wrong, and there'd be no baseline description to check them against.
- *Fix and document together* — the documentation ends up describing intent rather than behaviour, which is precisely how the architecture PDF drifted from the code.

**Consequences.** Roughly a day before any code changes. In exchange: an independent description of actual behaviour to check fixes against, and a genuine basis for disagreeing with the review's conclusions rather than accepting them. The documentation itself became the discovery mechanism — measurements 1–3 in `WORKLOG.md` only emerged from writing `DATAFLOW.md` and `FILE_STRUCTURE.md` carefully.

---

## ADR-010 · Three living documents, not one journal
**Date:** 2026-08-17 · **Status:** Accepted

**Context.** Documentation must be continuous and non-negotiable, so that any session starts with full context. The question was how to structure the running record.

**Decision.** Three files with distinct jobs: `WORKLOG.md` (what happened, chronological, append-only), `DECISIONS.md` (why, by topic, supersede-not-delete), `OPEN_QUESTIONS.md` (unresolved, with resolved items retained in a Resolved section).

**Alternatives.**
- *One combined journal* — less to maintain, but the "why" gets buried in chronology. The failure we're preventing is precisely "I know I decided this, I can't find where" — a chronological search over months is the wrong tool.
- *Two files (worklog + decisions)* — loses the open-questions channel, which is where things like the `gpt-5.2` uncertainty would otherwise evaporate between sessions.

**Consequences.** Three files to maintain, but two are append-only and therefore cheap. Split by how you'll search later: *when* → worklog, *why* → decisions, *what's unresolved* → open questions. Resolved questions move to a Resolved section rather than being deleted, so the file doubles as a record of settled uncertainty.

---

## ADR-009 · Regex override on top of LLM persona classification
**Date:** ~2026-01-22 (`1ccbecb`) · **Status:** Accepted · *Reconstructed*

**Context.** The Intake LLM classifies `user_persona` as Layman or Paralegal. It was misclassifying technically-phrased queries as Layman.

**Decision.** After the LLM returns, run a 16-pattern regex sweep (`Section \d+`, `FIR`, `Bail`, `Quash`, `CrPC`, `IPC`, `BNS`, …). Any match forces `Paralegal`, overriding the LLM. Applied on both the success and fallback paths.

**Alternatives.** Prompt engineering alone — attempted (the prompt contains explicit "AUTOMATIC TRIGGER" instructions) and evidently insufficient, which is why the deterministic override exists.

**Consequences.** One-directional: it can promote to Paralegal, never demote. A layman quoting a section number they googled is classified as a professional. Low cost currently, because `user_persona` only affects display — but it would matter if persona ever drove behaviour.

---

## ADR-008 · Composite confidence replacing mean-of-15
**Date:** 2026-02-25 (`ce1bded`) · **Status:** Accepted, **under revision** · *Reconstructed from the architecture PDF §7*

**Context.** Confidence was the simple mean of all 15 retrieved scores. This conflated distinct situations: 3 strong hits among 12 mediocre chunks averaged to the same ~0.44 as 15 uniformly mediocre chunks.

**Decision.** A weighted composite of three signals — top-5 mean (0.55), score-gap consistency (0.15), entity coverage (0.30) — clamped to [0, 1], driving tiered prompts at 0.55 / 0.38.

**Alternatives** (inferred, not documented): max score alone — too easily fooled by one lucky hit; an LLM-judged relevance score — extra cost and latency per query, and non-deterministic.

**Consequences.** The three signals are a sound decomposition and the reasoning is right. Two implementation problems undermine it (see `GAPS.md` #1, #2): the entity term divides chunks by entities so it can exceed 1.0, and its neutral default of 1.0 grants 0.30 free whenever no section is cited. Net effect: the composite functions as a binary entity-match detector.

**Superseding decision pending** — see `OPEN_QUESTIONS.md` Q4. Keep this implementation behind a flag; the ablation in `EVALUATION_PLAN.md` E5 needs it as a comparison.

---

## ADR-007 · Streamlit as a separate process
**Date:** ~2025-09-08 (`d8b0ba6`) · **Status:** Accepted · *Reconstructed*

**Context.** The system needed a UI.

**Decision.** A standalone Streamlit app on port 8501 talking to FastAPI on 8000 over HTTP, importing nothing from the backend.

**Alternatives.** Server-rendered templates via the existing Jinja2 setup — less interactive, and would couple UI to backend.

**Consequences.** Forces the API to be genuinely usable by any client; the UI could be replaced wholesale. Costs: two processes to start, and duplicated logic — the confidence thresholds `0.55`/`0.38` appear in both `agents/answer.py` and `streamlit_app.py` and can silently drift apart.

---

## ADR-006 · Monolithic in-process agents
**Date:** ~2026-01-19 (`0e44d28`) · **Status:** Accepted · *Reconstructed*

**Context.** The five-agent architecture could have been services or in-process classes.

**Decision.** Python classes calling each other directly. Qdrant is the only external dependency.

**Alternatives.** Microservices — independent scaling and deployment, at the cost of network latency and orchestration complexity, neither justified at this scale.

**Consequences.** Simple to run, debug, and reason about. One failure domain; no independent scaling. Correct for a research system.

---

## ADR-005 · Single-valued corpus filtering
**Date:** ~2026-01-19 (`0e44d28`) · **Status:** Accepted, **should be revisited** · *Reconstructed*

**Context.** The Router must decide which corpus to search. Queries may reference one Act, several, or none.

**Decision.** `target_corpus` is one string or `None`. One match → filter to it. Multiple matches → `None` (search everything). No match → domain fallback.

**Alternatives.** A Qdrant `should` clause matching any of several corpora — supported by the API, not used.

**Consequences.** No middle ground between "one corpus" and "all corpora". A "compare IPC and CrPC" query searches all 1,011 chunks including irrelevant ones, rather than the 695 that are actually BNS-or-BNSS. Given the index is 48.1% CrPC, dropping the filter has a strong base-rate effect (`GAPS.md` #5). A `should` clause is the natural fix.

---

## ADR-004 · Refuse only when zero chunks survive
**Date:** ~2026-02-25 (`ce1bded`) · **Status:** Accepted, **effectiveness questioned** · *From the architecture PDF §12.2*

**Context.** Given a confidence score, should low confidence trigger refusal?

**Decision.** No. Refusal fires only when zero chunks pass filtering. Low confidence produces an answer with a strong disclaimer.

**Rationale, quoted:** *"Even general guidance pointing toward the right type of lawyer is more helpful than flat refusal."*

**Alternatives.** Refuse below a confidence threshold — safer against wrong advice, but leaves users with nothing, and the population this system serves often has no alternative source of guidance.

**Consequences.** **The principle is defensible; the implementation does not achieve it.** Because `retriever.py:123` forces at least 3 chunks through whenever 3 exist, and the unfiltered fallback searches the whole collection, refusal is structurally unreachable on a populated index — 0 refusals in 23 recorded runs (`GAPS.md` #9). The stated fail-safe is "zero *usable* chunks"; the implementation checks "zero chunks exist." Those are different guarantees.

---

## ADR-003 · ~450-token chunks, one sentence of overlap
**Date:** ~2025-09-06 (`0d87a24`) · **Status:** Accepted · *Reconstructed*

**Context.** Documents must be split before embedding.

**Decision.** ~450 tokens, split on sentence boundaries, one sentence carried forward as overlap. Tokens approximated by whitespace word count.

**Rationale, from the architecture PDF §12.5:** empirically determined — shorter chunks split provisions across boundaries; longer chunks produce semantically broad embeddings.

**Consequences.** A uniform budget applied to provisions ranging from one line to several pages, so long provisions still fragment. The word-count approximation understates real token counts for legal text (which is dense in punctuation and numerals), so actual chunks run somewhat longer than 450 tokens.

---

## ADR-002 · `text-embedding-3-small`
**Date:** ~2025-08-26 (`c1c9bcb`) · **Status:** Accepted, **untested** · *From the architecture PDF §12.3*

**Context.** Choice of embedding model.

**Decision.** `text-embedding-3-small` (1536-d) over `-large` (3072-d).

**Rationale, quoted:** ~1/5 the cost, *"with sufficient discrimination for legal text… Legal queries occupy a narrow semantic space, reducing the marginal benefit of higher-dimensional embeddings."*

**Consequences.** The rationale is plausible but **was never tested** — no comparison was run. It is also a hard coupling: 1536 is baked into `ensure_collection(dim=1536)`, so changing model means recreating the collection and re-embedding everything. Worth noting that `EVALUATION_PLAN.md` E4 proposes InLegalBERT as an alternative — a domain-pretrained encoder is the more interesting comparison than `-large`.

---

## ADR-001 · Deterministic regex routing, not an LLM
**Date:** ~2026-01-19 (`0e44d28`) · **Status:** Accepted, **under scrutiny** · *From the architecture PDF §12.1*

**Context.** The Router decides which corpus to search and which sections to extract. This could be an LLM call or pattern matching.

**Decision.** Entirely deterministic — `ACT_MAP` keyword lookup plus regex entity extraction. No LLM.

**Rationale, quoted:** *"routing errors could lead to citing the wrong statute… Regex is deterministic, sub-millisecond, and predictable."* A routing error happens *before* retrieval, so it cannot be recovered from downstream.

**Alternatives.** LLM-based routing — more flexible on unusual phrasing, but non-deterministic, adds latency and cost, and fails in ways that are hard to trace.

**Consequences.** The reasoning is sound and the determinism has been genuinely useful — every routing failure found in the 2026-08-17 review was traceable to a specific line. The cost is real: queries without a keyword get no filter and fall through to the domain fallback, which conflates criminal with penal (`GAPS.md` #6). Measured routing accuracy on the pre-fix baseline: **1 of 11**.

This is exactly what Prof. Joshi's item 4 targets. Note the fix is probably *not* "use an LLM" — it is better keyword coverage, a corrected fallback, and hybrid dense+sparse retrieval, which preserves determinism where it matters. Superseding decision expected after `EVALUATION_PLAN.md` E4.

---

## ADR-00X · The corpus boundary is checked by NAME, not by similarity score
**Date:** 2026-08-23 · **Status:** Accepted

**Context.** The refusal gate was unreachable. `refused = len(filtered) == 0`, and the score filter always keeps at least three chunks, so the system never refused anything. An out-of-corpus Negotiable Instruments Act query came back at HIGH confidence 0.73.

The obvious fix is a similarity threshold: refuse when the best score is too low.

**The measurement that ruled that out.** 15 probe queries against the rebuilt index:

```
in corpus,     lowest max score   0.278   "my landlord is not returning my deposit"  (CPA IS indexed)
out of corpus, highest max score  0.519   "grounds for divorce under the Hindu Marriage Act"
nonsense,      highest max score  0.208   "how do I bake a chocolate cake"
```

The out-of-corpus query scores **higher than five of six in-corpus queries**. The distributions are not merely overlapping — they are inverted. Separation between the lowest legitimate query and the highest out-of-corpus one is **−0.241**. Any threshold catching the Hindu Marriage Act query also rejects most real work.

**Decision.** Check the boundary by **named statute**. Parse the query for Act names via `core.citations.named_statutes()` and compare against `CORPORA_IN_INDEX`. Refuse only when EVERY named Act is missing; flag `partial_corpus_coverage` when some are present. Record `refusal_reason` on every run so refusals can be counted by cause.

Keep a score floor at 0.25, documented explicitly as a **garbage filter for non-legal input**, never as a corpus check.

**Rationale.** Naming is the one signal that is not noisy. If the user says "Negotiable Instruments Act" and we never indexed it, that is certain rather than probabilistic. A similarity score is a statement about geometry, not about coverage, and this measurement shows it carries no coverage information at all in this setting.

**Consequences.**
- The gate fires only when a statute is NAMED. Layman queries name nothing — "husband beats me, what can I do" mentions no Act — so this cannot help them. That is a real hole, stated rather than papered over with a threshold, and it is what the Date Resolver and Statute Mapper address in Phase H.
- The inverted-distribution result is itself a finding for the paper: the standard approach to RAG abstention fails at exactly the boundary that matters here. It also strengthens E3 (does confidence detect anything?) with a mechanism rather than just an AUROC.
- 15 probe queries justify the design; they do not establish the number. Phase G measures it properly.

---

## ADR-00Y · The Router applies no corpus filter when no Act is named
**Date:** 2026-08-23 · **Status:** Accepted, supersedes part of ADR-001

**Context.** `if "Criminal" in context.predicted_legal_domain: target_corpus = "BNS"`.

**Decision.** `target_corpus = None`, decision path `domain_fallback_criminal_no_filter`.

**Rationale.** Two errors lived in that one line.

1. "Criminal" was treated as a synonym for the PENAL code. Arrest, bail, FIR and jurisdiction are PROCEDURE, so procedural queries were filtered into a corpus that cannot answer them (`GAPS.md` #6).
2. More seriously, it **silently decided the experiment**. Which penal code governs depends on when the conduct happened — before 1 July 2024 the IPC, on or after it the BNS. The Router has no date. Hard-coding BNS made the IPC unreachable for every query that did not name it by number, and laypeople never name a code. Every "This happened in March 2023" query would have been answered out of the code that did not yet exist, and Phase G would have measured the default rather than the system.

**Consequences.** Searching unfiltered is not free: the CrPC is 39% of the index and now competes on every criminal query. That is the base-rate confound already flagged in `EVALUATION_PLAN.md` E4, and it must be reported. An honest confound beats a hidden decision. This unfiltered path is the **baseline** the Phase H interventions get measured against.
