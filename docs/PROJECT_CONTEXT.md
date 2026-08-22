<!-- MIRRORED FILES — do not edit here.
     Source: C:\Users\uniya\.claude\projects\C--Users-uniya-legal-mvp\memory
     Synced: 2026-08-22 21:01 by scripts/sync_context.py -->

# Project Context

> **What this is.** Claude Code keeps persistent notes about this
> project — who is working on it, how they want to be worked with,
> the supervisor's directive, known defects, and cost measurements.
> Those notes live outside the repository, so they are mirrored here
> for anyone reading this project in another editor or handing it to
> another model.
>
> Each section below is one memory file, verbatim.

---

## Index

- [Udita's profile](udita-profile.md) — third-year IT student at Banasthali, solo on this project, learns from fundamentals up with diagrams and worked examples.
- [Mentor, not autopilot](mentor-not-autopilot.md) — she wants to be taught and to brainstorm, not handed code; explain before implementing.
- [Documentation is mandatory](documentation-is-mandatory.md) — non-negotiable continuous docs; WORKLOG / DECISIONS / OPEN_QUESTIONS protocol lives in CLAUDE.md.
- [legal-mvp research goal](legal-mvp-research-goal.md) — one artifact serving both her third-year project and a first conference paper.
- [Professor's directive, 6 Aug 2026](professor-directive-2026-08-06.md) — Prof. Nisheeth Joshi's five evaluation items; quality over early deadlines.
- [Known blocking defects](legal-mvp-known-defects.md) — confidence miscomputed, corpus tagging broken, routing drift mechanism; fix before measuring.
- [The 23 baseline runs](legal-mvp-baseline-runs.md) — predate confidence scoring; 6/7 answers cite unretrieved authority; pre-fix baseline only.

---

## `documentation-is-mandatory.md`

---
name: documentation-is-mandatory
description: Documentation is non-negotiable on legal-mvp — every session starts with full context and ends having recorded what changed
metadata: 
  node_type: memory
  type: feedback
  originSessionId: dadf5f93-17e2-4f71-9337-1fbedc0fd408
  modified: 2026-08-17T14:00:10.887Z
---

Udita's stated requirement, verbatim in substance: "whatever I do is heavily documented, so every session has complete context if I start a new one. Documentation is non-negotiable to me." She wants "loops of documentation and context running automatically" — the goal is that documentation upkeep is continuous and self-sustaining, not a one-time pass.

**Why:** She returned to this project after ~6–7 months away (Feb 2026 → Aug 2026) and could not reconstruct her own architecture or the reasoning behind her own design choices. That lost context cost her real time and nearly led her to run an evaluation on a system she misunderstood. She is also solo — there is no teammate to ask, so the documents *are* the teammate.

**How to apply:**
- The repo's documentation protocol lives in `CLAUDE.md` at the project root. Follow it.
- Three living documents, each with a distinct job — do not merge them:
  - `docs/WORKLOG.md` — dated session journal, newest first, append-only. What happened.
  - `docs/DECISIONS.md` — ADR-style. *Why* a choice was made, alternatives, consequences. Survives the code changing.
  - `docs/OPEN_QUESTIONS.md` — unresolved items. Resolved ones move to a Resolved section with the answer and date, never deleted.
- A code change is not finished until the affected doc is updated in the same pass.
- A design choice is not made until it has a `DECISIONS.md` entry.
- An unknown is not acceptable to leave in your head — it goes in `OPEN_QUESTIONS.md`.
- `SessionStart` / `Stop` hooks in `.claude/settings.json` automate the reminder loop, but they cannot make the content good. The discipline is the point.

Related: [[udita-profile]], [[mentor-not-autopilot]].

---

## `legal-mvp-baseline-runs.md`

---
name: legal-mvp-baseline-runs
description: The 23 recorded test runs in testing_results/ predate the confidence system — usable only as a labelled pre-fix baseline
metadata: 
  node_type: memory
  type: reference
  originSessionId: dadf5f93-17e2-4f71-9337-1fbedc0fd408
  modified: 2026-08-17T14:00:51.972Z
---

`legal-mvp/testing_results/` holds four Word documents recording **23 query runs** across four categories: Straightforward (7), Reasoning (4), Complex (6), Vague/Tricky (6). Duplicates of the same four files also sit in `C:\Users\uniya\Downloads`.

What they are, established 2026-08-17:

- **They predate the confidence system.** No `"confidence"` key appears in any captured Raw JSON, and every query returned exactly 15/15 citations — meaning `limit=15` with zero adaptive filtering. These ran before commit `ce1bded`.
- **Routing was wrong in almost every case.** Of the 11 runs where citations were captured, 10 drew all chunks from a single document, and only one (anticipatory bail under s.438 CrPC) hit the right corpus.
- **Citations do not support the answers.** Across the 7 straightforward queries, **6 answers cite statutory authority that was never retrieved** — including Acts absent from the corpus entirely (Negotiable Instruments Act, Indian Contract Act). The model was generating from parametric knowledge while the UI displayed unrelated CrPC pages as "Citations / Sources."
- **The refusal gate fired zero times** in all 23 runs.

**How to apply:** these runs can be reported as a **labelled pre-fix baseline**, but must never be mixed with post-fix numbers or presented as evaluating the current confidence system. Whether to keep them as a baseline or discard and re-run is still undecided — tracked in `docs/OPEN_QUESTIONS.md`.

The citation–answer mismatch is the strongest empirical finding available so far and is the likely core result of the paper (cf. Dahl et al. 2024, Magesh et al. 2025 on legal RAG hallucination).

Related: [[legal-mvp-known-defects]], [[legal-mvp-research-goal]].

---

## `legal-mvp-known-defects.md`

---
name: legal-mvp-known-defects
description: Three blocking defects in legal-mvp found 2026-08-17 that must be fixed before any evaluation numbers are meaningful
metadata: 
  node_type: memory
  type: project
  originSessionId: dadf5f93-17e2-4f71-9337-1fbedc0fd408
  modified: 2026-08-17T14:00:42.589Z
---

Found and verified on **2026-08-17**, before any of Prof. Joshi's evaluation work began. All three block measurement, so they come first. Full evidence, reproduction commands, and root-cause analysis are in `docs/GAPS.md`.

1. **Confidence is miscomputed.** `agents/retriever.py` divides a *chunk count* by an *entity count* when computing `entity_coverage`, so the value can exceed 1.0 and saturate the `min(confidence, 1.0)` clamp. Net effect: the confidence tier behaves as a binary "did entity matching fail" detector rather than a continuous three-signal composite. Calibration analysis and the weight ablation are meaningless until this is fixed.

2. **Corpus tagging is broken at ingest.** `ingest/chunk.py::guess_corpus()` leaves IPC 1860 at ~95% `"Unknown"` and the Consumer Protection Act at ~86% `"Unknown"`. `fix_corpus_tags.py` patched the *Qdrant database* but never the *code*, so any re-ingestion silently reverts to broken tags.

3. **Routing drift has a specific mechanism.** `agents/router.py` still maps `"consumer protection" → "Unknown"`, which after the database patch matches nothing; the retriever's fallback then silently drops the filter and searches an index that is ~48% CrPC by volume. That base-rate imbalance is the CrPC drift Udita reported to her supervisor — not the keyword-coverage problem she hypothesised.

A fourth item is **unconfirmed**: `.env` sets `MODEL_NAME=gpt-5.2` while `temperature=0` is passed in `clients/openai_client.py` and `agents/answer.py`. If that combination is rejected by the API, Intake and Answer both fail into silent fallbacks. Tracked in `docs/OPEN_QUESTIONS.md`.

**How to apply:** do not generate evaluation numbers before 1–3 are fixed and the corpus is re-ingested cleanly. Fixing the data without fixing the code is what caused defect 2 to persist invisibly for months.

Related: [[legal-mvp-baseline-runs]], [[professor-directive-2026-08-06]].

---

## `legal-mvp-research-goal.md`

---
name: legal-mvp-research-goal
description: "legal-mvp is both Udita's solo third-year project and her first conference paper attempt — one artifact, two sets of stakes"
metadata: 
  node_type: memory
  type: project
  originSessionId: dadf5f93-17e2-4f71-9337-1fbedc0fd408
  modified: 2026-08-17T14:00:19.022Z
---

`legal-mvp` (C:\Users\uniya\legal-mvp) is a five-agent RAG system for Indian legal Q&A — FastAPI + Qdrant + OpenAI + Streamlit. It serves two purposes at once:

1. Udita's **official third-year B.Tech project**, done solo while peers work in teams.
2. Her **first attempt at a peer-reviewed publication**, supervised by Prof. Nisheeth Joshi.

She described taking this on as "a herculean task" and wants to "take it to a grand level." Stakes are high and she has said everyone expects a lot of her.

**Why this matters for how to work on it:** decisions must serve both a defensible college project *and* a paper that survives review. That rules out shortcuts that would work for one but not the other — e.g. hard-coding results, patching the database instead of the code, or reporting numbers from a code version that no longer exists.

**Current framing (as of 2026-08-17):** the composite confidence score was originally seen as the contribution, but the literature (Self-RAG, CRAG, Adaptive-RAG) makes retrieval-quality gating well-trodden. Both Udita and her supervisor now agree the stronger contribution is a **rigorous empirical failure analysis** of a multi-agent legal RAG system on real Indian queries. See [[professor-directive-2026-08-06]].

Full background, literature list, and venue options are in `docs/RESEARCH_CONTEXT.md` in the repo.

Related: [[legal-mvp-known-defects]], [[legal-mvp-baseline-runs]].

---

## `llm-token-costs.md`

---
name: llm-token-costs
description: "What tokens cost on legal-mvp, why reasoning models bill far more than their visible output, and the max_tokens trap that causes silent failures"
metadata: 
  node_type: memory
  type: reference
  originSessionId: dadf5f93-17e2-4f71-9337-1fbedc0fd408
  modified: 2026-08-22T15:30:57.230Z
---

Measured 2026-08-22 against `google/gemini-3.7-flash` via OpenRouter (provider pinned to `google-ai-studio`).

## The basics

A **token** is a chunk of text, a bit smaller than a word. **100 tokens ≈ 75 English words.** You pay in both directions:

| | | Price |
|---|---|---|
| **Input** | question + retrieved chunks | $0.375 / million |
| **Output** | everything the model produces | $1.875 / million |

Output costs **5× input**. `max_tokens` is a **ceiling on output**, not a target — unused budget costs nothing.

## The trap: you pay for invisible thinking

`gemini-3.7-flash` is a **reasoning model**. Before writing anything visible it produces a private chain of thought. You never see it, you pay for every token of it, and **it counts against `max_tokens`**.

Measured, asking it to reply with exactly `PIPELINE OK` (~3 tokens visible):

```
max_tokens=20   ->  16 billed  ->  output was  'The'   (ran out mid-answer)
max_tokens=100  ->  91 billed  ->  output was  'PIPELINE OK'
max_tokens=400  ->  91 billed  ->  same
```

**A 3-token answer cost 91 tokens — roughly 30× its visible output.**

## Why this causes silent failures

`agents/intake.py` used `max_tokens=600`. A *simple* query consumed **422 of 600**. A complex one overflows, and then:

truncated JSON → `json.loads` throws → `intake.py` catches it → prints `[Intake] LLM CRASH` to a terminal nobody reads → substitutes `domain="General"`, `issues=[]` → the Router routes on a domain the LLM never produced.

Nothing in the output indicates this happened. Raised to 1500; `intake.fallback_used` in the run log now detects it.

## Cost per evaluation run

```
per query    ~8,500 in  ·  ~3,000 out (incl. thinking)
per 100-query run
   input   850,000 x $0.375/M  =  $0.32
   output  300,000 x $1.875/M  =  $0.56
                                  -----
                                  $0.88   (~Rs 75)
```

Twenty full runs ≈ **₹1,500**. Retrieval-only experiments (cross-statute confusion, routing comparison, chunk-size ablations) make **no generation calls at all** — embeddings only, at $0.02/M, so fractions of a rupee.

**Superseded once the run logger records `cost_usd` per call** — then use measured figures, not these estimates.

Related: [[legal-mvp-research-goal]], [[legal-mvp-known-defects]].

---

## `mentor-not-autopilot.md`

---
name: mentor-not-autopilot
description: "Udita wants Claude Code as a mentor who teaches, not a code vending machine — explain and brainstorm before implementing"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: dadf5f93-17e2-4f71-9337-1fbedc0fd408
  modified: 2026-08-17T14:00:00.968Z
---

Udita asked, in her own words, that Claude Code act "as my mentor, not just to do things what I ask, but actually help me to understand, think and brainstorm." She said explicitly: "I do not want to abuse the use of Claude Code. I want to actually understand thoroughly what I am building. I want to learn and grow."

**Why:** This is simultaneously her solo third-year college project and her first attempt at a published paper (see [[legal-mvp-research-goal]]). She has to defend this work and answer questions about it. Code she did not understand would be worse than useless — it would be a liability at evaluation and in peer review. She also genuinely wants the skill, not just the artifact.

**How to apply:**
- Explain the concept *before* writing the fix, not after. Teach the mechanism, then apply it.
- Show reasoning she can attack. Give a recommendation with the argument behind it so she can disagree, rather than a verdict.
- When she asks "what should I do," answer with a recommendation and the why — do not hand the decision back to her as a menu unless the choice genuinely turns on her preferences.
- Never dump a large diff without walking through what it does and why.
- Prefer showing her how to verify a claim herself over asserting it.
- Brainstorm *with* her. She asked for help thinking, not just help typing.

This is a permanent working agreement, not advice for one task. It applies to every session on this project.

Related: [[udita-profile]], [[documentation-is-mandatory]].

---

## `professor-directive-2026-08-06.md`

---
name: professor-directive-2026-08-06
description: "Prof. Nisheeth Joshi's five directives for legal-mvp (email 6 Aug 2026) — build eval set, add logging, measure, fix routing, ablate; quality over deadlines"
metadata: 
  node_type: memory
  type: project
  originSessionId: dadf5f93-17e2-4f71-9337-1fbedc0fd408
  modified: 2026-08-17T14:00:31.827Z
---

Prof. Nisheeth Joshi replied to Udita on **6 August 2026** with an explicit work order. His five items, in his order:

1. Build a well-annotated evaluation set — at least 50–100 representative legal queries with **ground-truth statutory sections**.
2. Add complete logging for all retrieval signals, confidence values, routing decisions, and retrieved sections.
3. Evaluate retrieval performance, confidence calibration, and answer correctness.
4. Investigate the routing issue and compare the current router against a **hybrid routing strategy**.
5. Perform an ablation on the confidence score components and compare against suitable baselines.

He also gave two framing judgements:

- He **agrees the confidence score alone is not the contribution**. The paper should be a rigorous empirical evaluation of confidence calibration, retrieval quality, routing behaviour, and failure analysis for an Indian legal RAG system.
- **"Prioritize the quality of the evaluation over meeting the earliest deadlines."** If substantial results are ready in time, consider NLLP (EMNLP workshop) or FIRE; otherwise ACL Rolling Review or JURIX. He said explicitly that a stronger paper beats a rushed submission.

His instruction was to begin the evaluation and logging work immediately, prepare results/figures/tables as they emerge, and decide the final narrative and venue afterwards.

**How to apply:** treat items 1–5 as the project backlog. But note the ordering constraint discovered on 2026-08-17: items 3 and 5 cannot produce meaningful numbers until the defects in [[legal-mvp-known-defects]] are fixed, because the confidence score is currently miscomputed. Item 2 (logging) is the true unblocker and should come first.

Both emails are preserved verbatim in `docs/RESEARCH_CONTEXT.md`. Experiments are specified in `docs/EVALUATION_PLAN.md`.

Related: [[legal-mvp-research-goal]].

---

## `udita-profile.md`

---
name: udita-profile
description: "Who Udita is — third-year B.Tech IT student at Banasthali Vidyapith, working solo on legal-mvp, learns best from fundamentals up"
metadata: 
  node_type: memory
  type: user
  originSessionId: dadf5f93-17e2-4f71-9337-1fbedc0fd408
  modified: 2026-08-17T13:59:51.807Z
---

Udita Uniyal is a third-year B.Tech Information Technology student at Banasthali Vidyapith (entered third year around August 2026). Her supervisor is Prof. Nisheeth Joshi.

She is working on `legal-mvp` **alone**. Most peers do their third-year project in teams; she does not have one, and expectations on her are high.

How she learns and wants to be taught:

- **Steadily, from fundamentals.** She says explicitly that she understands things slowly and needs concepts built up rather than assumed.
- **Concrete examples over abstractions.** Worked numbers, real values from her own system, traced end-to-end.
- **Diagrams and architectural clarity.** She reaches for structure first; a picture of how pieces connect lands better than prose.
- **Layered depth.** Plain-language pass first, then technical depth — so she can stop at any level and still hold a coherent picture.

She is not a beginner programmer — she built a five-agent RAG system — but she is new to research methodology, evaluation design, and the ML/IR concepts underneath RAG (calibration, reranking, embedding geometry).

See [[mentor-not-autopilot]] for how she wants me to work with her, and [[legal-mvp-research-goal]] for what she is building toward.

---
