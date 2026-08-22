<!-- MIRRORED FILE — do not edit here.
     Source: C:\Users\uniya\.claude\plans\streamed-cuddling-milner.md
     Synced: 2026-08-22 21:01 by scripts/sync_context.py -->

> **This is a mirror.** The live plan lives in Claude Code's plan
> directory and is copied here so the repository is self-contained
> for anyone reading it outside Claude Code.

---

# Plan — From broken prototype to a submittable paper

## Context

Udita has a working-but-broken 5-agent RAG system for Indian legal Q&A, now fully documented (`docs/`). She has read most of that documentation and reports ~50% understanding — the docs were written far denser than she asked for, which is a failure on my part and is corrected in Phase 0 below.

Three things changed on 2026-08-18:

1. **Her OpenAI key is dead.** She has an OpenRouter key. Research confirms OpenRouter added an embeddings endpoint in July 2026 and serves `openai/text-embedding-3-small` at the same price — so **the existing Qdrant collection stays valid and nothing needs re-embedding.** But OpenRouter load-balances across providers by default, which is a documented reproducibility hazard (a NeurIPS 2025 paper's claims were invalidated by exactly this). Everything must be pinned.

2. **The venue landscape is now known.** NLLP 2026's extended deadline expires ~17:30 IST on 19 Aug — unreachable with n=11 queries. The Insights workshop closed 8 June. FIRE 2026 (31 Aug, ISI Kolkata, 9pp, ACM, in India) is the near target; ARR (12 Oct) is the realistic anchor. ICON 2026's deadline is unpublished and must be retrieved.

3. **The contribution has to move.** Research shows three of her assumed contributions are already published, at larger scale, in 2026:
   - "Retrieval failure causes legal RAG hallucination" — Legal RAG Bench (Mar 2026) and Das et al. (14 Aug 2026, four days ago)
   - Wrong-document retrieval — named **DRM** by Reuter et al. at NLLP 2025
   - Confidence/calibration for RAG — saturated (6+ papers in 2026)

**What is genuinely unclaimed, and what this plan is built around:** on 1 July 2024 India replaced the IPC (511 sections) with the BNS (358 sections) overnight. Both remain operative depending on offence date. 164 years of case law, and *every* Indian legal NLP resource (ILDC, InLegalBERT, LeSICiN, NyayaAnumana), use the old numbering. Existing temporal-legal-RAG work (French tax, German statutes) assumes a **versioned single instrument with linear amendment history**. India is a **cross-instrument, many-to-many, non-monotonic remapping** — version-aware retrieval architecturally cannot solve it.

Her corpus already contains **both IPC 1860 and BNS 2023**. The routing bug she found is not a bug to be embarrassed about — it is the phenomenon, and she has already observed it. **Her biggest defect is her paper.**

Working title: *When the Code Changes: Cross-Statute Retrieval Failure and Phantom Citation in Indian Legal RAG after the IPC→BNS Recodification*

**Framing rule for everything below:** the 5-agent system is the *measurement instrument*, described in one paragraph. Never the contribution.

---

## Phase 0 — Fix my documentation failure (half a day)

**`docs/START_HERE.md`** — ~1,000 words, genuinely plain English, one diagram, zero jargon. What the system does, the five steps, the three things that are broken, what we do next. This becomes the entry point; the dense docs become reference material rather than required reading.

Add a **"in one sentence"** box at the top of each existing doc.

Going forward: plain English by default, short sentences, worked examples before abstractions. Recorded as a memory update to `mentor-not-autopilot`.

---

## Phase 1 — Unblock (2–3 days)

Nothing here changes findings; all of it is prerequisite.

**1.1 · OpenRouter migration** (`clients/openai_client.py`, `core/config.py`, `.env`)
- Base URL + key swap. **Embeddings stay `openai/text-embedding-3-small`, pinned:** `provider: {only: ["openai"], allow_fallbacks: false}`. Existing collection untouched.
- Generation pinned to `google/gemini-2.5-flash` (supports `temperature`, `seed`, and structured JSON — GPT-5-class models silently *drop* temperature, which would make the methods section false). Set `require_parameters: true` so unsupported settings error instead of vanishing.
- **Banned:** `openrouter/auto`, `~model-latest`, `:nitro`, `:floor`, `:exacto`.
- Log `provider_name`, `model`, `total_cost` from `/api/v1/generation` on every call.
- Resolves `OPEN_QUESTIONS.md` Q1 (the `gpt-5.2`/`temperature=0` question) — record as an ADR.

**1.2 · Structured logging** — `core/logging.py` exists unused. One JSONL record per query with the schema in `EVALUATION_PLAN.md` §P2, plus the four silent-failure flags (`intake.fallback_used`, `router.decision_path`, `retrieval.filter_fallback_fired`, `confidence.entity_coverage_default_used`) and now `provider_name`. **This is Prof. Joshi's item 2 and the true unblocker.**

**1.3 · `requirements.txt`** — regenerate from venv. Drop the unused CV stack *and* the five unused LangChain packages (installed, zero imports).

**1.4 · Real tests** (`tests/test_router.py` currently raises on line 1) — pytest over `route()`, `compute_confidence()` (including the pathological entity cases), `guess_corpus()`.

**1.5 · Fix routing + confidence clusters**, then **re-ingest cleanly** and delete `fix_corpus_tags.py`. Per `GAPS.md` #1–7. Keep the old confidence implementation behind a flag — the ablation needs it.

---

## Phase 2 — The evaluation set (3–4 days) — *the single highest-leverage work*

**≥100 queries.** n=11 is fatal at any venue; the credible floor in 2026 legal-RAG work is ~100 (Legal RAG Bench), with 142–312 typical.

**The design *is* the experiment.** Build **paired queries**: the same legal question phrased once with IPC numbering and once with BNS numbering.

> *"What is the punishment for cheating under Section 420 IPC?"*
> *"What is the punishment for cheating under Section 318 BNS?"*

Same offence, different statute, different section number. A dense retriever has almost no signal to separate them. That pairing is what no existing paper has run.

Schema per query: `query_id`, `text`, `pair_id`, `numbering_scheme` (IPC/BNS/neutral), `category`, `expected_corpus`, `expected_sections`, `answerable_from_corpus`, `phrasing_register` (layman/technical), `notes`.

Composition: ~40 IPC↔BNS paired (20 pairs) · 20 procedural (CrPC) · 15 consumer · 15 unanswerable (tests refusal) · 10 multi-corpus comparison.

**Ground truth annotated before seeing any output.** Deliverables: `eval/queryset.jsonl` + `eval/ANNOTATION_GUIDE.md`.

**Ask Prof. Joshi to source a law student or faculty member to validate ~30 queries and the gold labels.** Every credible paper in this field has expert validation; almost no Indian system paper does. Cheapest available differentiator.

---

## Phase 3 — Experiments (3–4 days)

Comparison axes are **mandatory** — a single-system study with no comparison reads as a system report.

| # | Experiment | Produces |
|---|---|---|
| **E1** | **Cross-statute confusion.** On paired queries: does an IPC-numbered query retrieve BNS text and vice versa? Confusion matrix over predicted×expected corpus. | The headline table |
| **E2** | **Phantom citation.** Extract every provision cited in each answer; check whether it appears in the chunks sent to the LLM. Report citation precision, unsupported rate, out-of-corpus rate, and a fourth India-specific class: **wrong-numbering-scheme citations** (right law, wrong code). | The headline finding |
| **E3** | **Does confidence detect any of this?** AUROC of the composite score vs. citation-groundedness. If ≈0.5, the weakest part of the system becomes a genuine negative result. | Turns a liability into a contribution |
| **E4** | **Routing comparison** — routed vs. flat-index (free, isolates the failure) vs. BM25 vs. hybrid (RRF). Report the base-rate confound: unfiltered search over a 48.1%-CrPC index. | Prof. Joshi's item 4 |
| **E5** | **Ablations that rule out "bad config"** — embedding model, chunk size, top-k, reranking on/off. If the failure survives all of them it is architectural; if not, that is a better finding. | Pre-empts the obvious reviewer objection |
| **E6** | **Confidence ablation** — drop each signal, plus old buggy version, plus naive mean-of-15 baseline. | Prof. Joshi's item 5 |
**Report confidence intervals, not bare fractions.** With n=11, a 91% failure rate has a 95% CI of roughly [59%, 100%] — that is why the current numbers are anecdote.

---

## Phase 3B — Architectural intervention (3–4 days) — *yes, we change the code*

A paper that only says "here is what breaks" is weaker than one that says "here is what breaks, here is a fix, here is the measured gain." Three new components, each justified by a specific finding from Phase 3 and each measured as its own comparison axis. **Nothing is added that is not measured.**

**3B.1 · Statute-Mapping Agent — the novel one, and the paper's proposed solution**

Given an extracted entity like `Section 420 IPC`, resolve it across the recodification (`→ Section 318 BNS`) using a curated IPC↔BNS mapping table, and search **both** corpora. This is the direct answer to the cross-statute failure that is the paper's core finding. No existing system does it, because no one has framed the Indian recodification as a retrieval problem.

Requires building an **IPC↔BNS section mapping table** as a data artifact (derivable from the BPRD/UP Police comparison tables). That table is itself a citable resource contribution.

**3B.2 · Corrective retrieval loop — the first real agentic behaviour**

After retrieval, judge whether what came back is actually on-topic. If not, act: widen or change the corpus filter and search again, up to N attempts. This is Corrective-RAG (Yan et al.) applied to the routing failure, and it is the first point in the system where a component *observes a result and decides what to do next* — the thing the current pipeline cannot do.

**3B.3 · Verifier Agent — does double duty**

Check that each provision cited in the answer actually appears in the retrieved chunks; flag or strip those that don't. This is simultaneously a system improvement *and* the measurement instrument for E2. Same code produces the paper's headline number and the fix for it.

**Framework decision: hand-roll it, do not adopt LangGraph.**
The loop is ~150 lines of plain Python. LangGraph is genuinely designed for cyclic agent graphs and would be a reasonable choice — but the entire value of this project is the bespoke logging schema, and LangGraph's tracing is opinionated in ways that would fight it. Reviewers do not care which framework was used; they care that every decision is inspectable. Hand-rolled stays inspectable. (Revisit only if the loop grows beyond ~3 states.) Record as an ADR.

**Measured as:**

| | Comparison |
|---|---|
| **E7** | Baseline pipeline vs. + statute mapping |
| **E8** | Baseline vs. + corrective loop (and both together) |
| **E9** | Unsupported-citation rate before vs. after the verifier |

Keep the original pipeline runnable behind a flag throughout — it is the baseline every number is measured against.

---

## Phase 4 — Write (4–5 days)

Structure: Intro (access to justice + recodification) → Related work (**must cite** Reuter/DRM, Magesh, Legal RAG Bench, Das et al., Prior et al., Cymbler et al., plus the Indian system papers being critiqued) → System in one paragraph → Evaluation setup → Results → **Failure analysis (the core)** → Discussion → **Ethics + Limitations**.

Non-negotiables learned from the research:
- **Ethics section is effectively mandatory** — NLLP explicitly rejects sensitive-task papers that omit it. Laypeople acting on wrong statutory citations is a real harm.
- **Anonymised code + data** (anonymous.4open.science for review).
- **Never ROUGE for correctness.** If LLM-as-judge is used, validate against human labels on a subsample and report agreement.
- **No jurisdictional overclaim** — "in this corpus, under this configuration, X% of queries exhibit Y."
- Name the failure modes. *Cross-statute retrieval failure* and *phantom citation* are the candidate names.

**Figure 1** = the arrest-query trace from `DATAFLOW.md`. It carries the whole argument.

---

## Venue strategy

**Do the work; pick the venue when results exist** — which is exactly what Prof. Joshi already advised.

**The Oct–Nov window is real and it is the right target.** There are four genuine deadlines in it, which means ~8–11 weeks of runway rather than a 12-day scramble. FIRE is *not* worth panicking over.

| Venue | Deadline | Conference | Verdict |
|---|---|---|---|
| **NLLP 2026** | ~17:30 IST, 19 Aug | Oct, Budapest | **Skip.** Unreachable with n=11; a rejection burns the venue for this cycle. |
| **FIRE 2026** | 31 Aug | 17–20 Dec, Kolkata | **Only if Phases 1–3 fly.** 12 days. Don't force it. |
| **JURIX 2026** | 5 Sep | 8–10 Dec, Toulouse | Mandatory in-person (~₹1.5–2.5 L). Only with funding. |
| **ICON 2026** | **unpublished** | 20–23 Dec, Guwahati | **Retrieve the CFP today** (Drive link on icon2026.org). ACL Anthology, in India, lower bar. Likely Sep–Oct. |
| **ECIR 2027 short** | **12 Oct** | Mar 2027, UK | ~8 weeks. 6pp. Strong IR venue. |
| **ARR** | **12 Oct** | → NAACL/COLING 2027 | **Primary anchor.** Reviews reusable for main conferences *and* for workshops' fast-track routes. |
| **ECIR 2027 reproducibility** | **2 Nov** | Mar 2027, UK | ~11 weeks. **Requires a pivot** — the track excludes evaluating your own system, but explicitly welcomes *failure to reproduce others'*. See below. |
| **CODS 2027** | TBA (~late 2026) | — | Watch; poor topical fit. |
| **Insights 2027** | ~Jun 2027 | — | Ideal conceptual home. Backup. |

**Primary plan: ARR, 12 October.** ~8 weeks. Comfortable for Phases 0–4. Reviews are reusable, so it is the lowest-risk shot with the highest ceiling.

**Optional second paper, ECIR reproducibility, 2 Nov:** several published Indian legal RAG systems (LegalEase in Springer 2025, Domain-Partitioned Hybrid RAG, LawPal, HyRAG) report 70–90% success on ≤40 synthetic questions using ROUGE or unvalidated LLM-as-judge. Re-evaluating them on a proper 100+ query expert-labelled IPC/BNS set — and showing the numbers don't hold — is a legitimate second paper using the *same* evaluation set. Only if Phases 1–4 finish early.

Report to Prof. Joshi at the end of Phase 1 — the routing diagnosis and corpus-tagging measurement are concrete progress on his item 4 and worth sharing before full results.

---

## Tooling (1 hour, do alongside Phase 1)

**Install:**
- **arXiv MCP** — `uv tool install "arxiv-mcp-server[pdf]"` then `claude mcp add`. Literature search, read specific LaTeX sections of papers, BibTeX export, standing alerts on the subfield. Highest research value of anything here.
- **`pyright-lsp`** — type checking; catches the class of bug that produced the `top_score` corruption.
- **`context7`** — hosted, version-correct docs for qdrant-client / FastAPI / OpenAI SDK.
- **`obra/superpowers`** — **user's decision, for development work only, not research.** `/plugin install superpowers@claude-plugins-official`. Caveats to state plainly at install time and then not re-litigate: its `SessionStart` hook has an open Windows bug (#2105) where it can fail *silently*, so verify it actually loaded; it adds ~2s to session start on Windows (#2081); Windows Defender may flag it (#2143, assessed false positive); and its `subagent-driven-development` / autonomous-execution skills conflict with the "explain before implementing" rule in `CLAUDE.md` — **`CLAUDE.md` wins on this project.** Its `test-driven-development` and `systematic-debugging` skills are the genuinely useful parts and map onto Phase 1.4.

**Evaluation harness as code, not as a skill** *(user's instruction)* — `scripts/run_eval.py`: reads the query set, POSTs each to `/query`, collects JSONL, captures the git SHA, refuses to run on a dirty working tree, writes results and appends a `WORKLOG.md` entry. Better as code than as a skill anyway: it ships in the repo, reviewers can read it, and it goes in the artifact release.

**Add a `PreToolUse` guardrail hook** enforcing the two ⚠ rules in `CLAUDE.md` (never run `fix_corpus_tags.py`, never `pip install -r requirements.txt`).

## Subagent use

Delegate to subagents wherever the work is parallel or context-heavy, keeping the main thread for reasoning and teaching:

| Task | Why delegate |
|---|---|
| Literature triage (read 30 abstracts → 5-line verdicts) | Keeps 30 papers of text out of the main context |
| Building the IPC↔BNS mapping table from BPRD/UP Police sources | Mechanical, high-volume extraction |
| Drafting query-set candidates per statute | Parallel across 4 statutes, then reviewed by Udita |
| Running experiment sweeps and reporting deltas | Long-running, output is a summary not a transcript |
| Adversarial review of results before submission | Independent perspective; catches overclaiming |

Rule: subagents do **analysis, search, and drafting**. Code changes and design decisions stay in the main thread where they get explained.

**Embedding insurance (~2 h):** also embed the 1,011 chunks locally with `BAAI/bge-m3` (pinned HF revision) into a second Qdrant collection. CPU-only, ~15 min, free, never expires. Gives a provider-independent path that survives any API death — her OpenAI key dying mid-project is the argument — and a free API-vs-local ablation for E5.

---

## Constraints

- **Fix code, never data.** `fix_corpus_tags.py` is why a defect hid for six months.
- **One variable at a time.** Every result carries its git SHA.
- **Never mix pre-fix and post-fix numbers.** The 23 existing runs are a labelled pre-fix baseline only.
- **Explain before implementing.** Every change gets walked through in plain English first.
- **Documentation protocol** (`CLAUDE.md`) applies to every step.

## Verification

1. Phase 1: `/healthz` green, one query end-to-end producing a complete JSONL record with `provider_name` populated, corpus audit showing 100% correct tags and zero phantom corpora, `pytest` green.
2. Phase 2: 100+ rows validated against the schema; ~30 expert-validated; annotation guide reproducible by a second person.
3. Phase 3: every number regenerable from logs by a script in-repo, with git SHA.
4. Phase 4: page limit, anonymity, ethics section, and reference completeness checked against the target venue's CFP before submission.
5. **The real test:** Udita can explain the contribution, the method, and the limitations in her own words without reading from a doc.
