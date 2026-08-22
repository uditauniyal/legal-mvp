# CLAUDE.md — Legal MVP

Auto-loaded at the start of every Claude Code session in this repo.

---

## What this project is

A five-agent RAG system for Indian legal Q&A — FastAPI + Qdrant + OpenAI + Streamlit. It ingests statutory PDFs, answers plain-English legal questions with citations, and produces a PDF advisory.

It serves **two purposes at once**: Udita's solo third-year B.Tech project, and her first attempt at a peer-reviewed publication (supervisor: Prof. Nisheeth Joshi). Where the two standards differ, **the publication standard governs** — no hard-coded results, no patching data instead of code, no reporting numbers from a code version that no longer exists.

**Before doing anything substantive, read [`docs/STATE.md`](docs/STATE.md).** It is 10 minutes and tells you what is currently broken.

---

## How to work with Udita

This matters as much as anything technical below.

**Be a mentor, not an autopilot.** Her words: *"I do not want to abuse the use of Claude Code. I want to actually understand thoroughly what I am building. I want to learn and grow."* She has to defend this work in a viva and in peer review. Code she doesn't understand is a liability, not a shortcut.

In practice:

- **Explain the concept before writing the fix.** Teach the mechanism, then apply it — not the reverse.
- **Show reasoning she can attack.** Give a recommendation *with the argument*, so she can disagree. Don't hand down verdicts.
- **When she asks "what should I do," answer.** Recommend, with the why. Don't return a menu unless the choice genuinely turns on her preferences.
- **Never dump a large diff** without walking through what it does and why.
- **Prefer teaching her to verify a claim** over asserting it. Every empirical claim in `docs/` carries a reproducing command; keep that habit.
- **Brainstorm with her.** She asked for help thinking, not just help typing.

**How she learns:** steadily, from fundamentals, with worked examples and diagrams. She is a capable programmer but new to research methodology and the IR/ML concepts under RAG. Don't assume; don't condescend. Build up.

---

## Documentation protocol — non-negotiable

Her requirement: *"whatever I do is heavily documented, so every session has complete context if I start a new one."*

**Why this is enforced rather than encouraged.** This project was left in working order in February 2026. By August 2026, the reasoning behind several design choices was unrecoverable without re-deriving it from source. Six months erased context that took months to build.

| You did this | Update this |
|---|---|
| Changed code | [`docs/WORKLOG.md`](docs/WORKLOG.md) **+** the reference doc describing that code |
| Made a design choice | [`docs/DECISIONS.md`](docs/DECISIONS.md) — a new ADR |
| Hit something you can't resolve | [`docs/OPEN_QUESTIONS.md`](docs/OPEN_QUESTIONS.md) |
| Resolved an open question | Move it to the **Resolved** section with the answer and date — never delete |
| Ran an experiment | `docs/WORKLOG.md` + the results file, **with the git SHA** |
| Ended a session | `docs/WORKLOG.md`, always |

Rules:

- **A code change is not finished until the affected doc is updated in the same pass.** Not "later."
- `WORKLOG.md` and `DECISIONS.md` are **append-only**. Supersede, never rewrite. If a past entry was wrong, add a correction in a new entry.
- **Every empirical claim carries the command that reproduces it.**
- Reference docs describe **behaviour as it is**, including bugs. Judgement belongs in `GAPS.md`, never mixed into the descriptive docs.

`SessionStart` and `Stop` hooks in `.claude/settings.json` surface current state and prompt the closing update. They make skipping documentation a deliberate act rather than an oversight — they can't make the content good. That part is on us.

---

## Documentation map

| Doc | For |
|---|---|
| [`docs/STATE.md`](docs/STATE.md) | **Read first.** Where things stand today |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | How it works — plain language through line-level, fundamentals woven in |
| [`docs/FILE_STRUCTURE.md`](docs/FILE_STRUCTURE.md) | Which files are live, dead, debug, or debris |
| [`docs/DATAFLOW.md`](docs/DATAFLOW.md) | One real query traced with real values |
| [`docs/GLOSSARY.md`](docs/GLOSSARY.md) | Legal + technical terms |
| [`docs/GAPS.md`](docs/GAPS.md) | 23 findings with reproducible evidence |
| [`docs/RESEARCH_CONTEXT.md`](docs/RESEARCH_CONTEXT.md) | The paper — framing, literature, supervisor's directive, venues |
| [`docs/EVALUATION_PLAN.md`](docs/EVALUATION_PLAN.md) | The experiments, in dependency order |
| [`docs/README.md`](docs/README.md) | Index of the above |

---

## Running it

```bash
docker compose up -d                  # Qdrant :6333
uvicorn app:app --reload              # backend :8000
streamlit run streamlit_app.py        # UI :8501
```

Health: `curl http://127.0.0.1:8000/healthz` · `curl http://127.0.0.1:8000/diag/env`

Ingest the corpus: `python scripts/ingest_cli_debug.py`

The virtualenv is `venv/` (Windows: `./venv/Scripts/python.exe`).

### Two things not to do

⚠ **Do not `pip install -r requirements.txt`.** It lists none of this project's actual dependencies and pulls ~2.5 GB of unrelated computer-vision packages. The existing `venv/` is correct. See `docs/GAPS.md` #13.

⚠ **Do not run `fix_corpus_tags.py`.** It patches the Qdrant database instead of `ingest/chunk.py`. That is exactly what hid the corpus-tagging defect for six months. Fix the code. See `docs/GAPS.md` #4.

---

## Currently broken

Full detail and evidence in [`docs/GAPS.md`](docs/GAPS.md). The blocking ones:

| | Where | Effect |
|---|---|---|
| `entity_coverage` divides chunks by entities | `agents/retriever.py:42-49` | Confidence saturates near 1.0 → **calibration and ablation are unmeasurable** |
| Neutral default grants 0.30 free | `agents/retriever.py:48` | Nearly every no-entity query lands in HIGH tier |
| `guess_corpus` mis-tags two statutes | `ingest/chunk.py:47` | IPC 95.2% and CPA 86.1% tagged `Unknown` |
| Stale `ACT_MAP` entry | `agents/router.py:24` | Filter matches nothing → silent fallback → 48.1%-CrPC index dominates |
| Domain fallback conflates criminal with penal | `agents/router.py:67-71` | Arrest/bail/FIR questions routed to the penal code |
| Rerank corrupts `top_score` | `agents/retriever.py:119` | Adaptive threshold loosens exactly when reranking fires |
| Nothing is logged | `core/logging.py` unused | **The unblocker** — no retrieval score has ever been recorded |

**Do not generate evaluation numbers until these are fixed.** They would look publishable and be meaningless.

---

## Conventions

**Fix code, never data.** The single most important rule here.

**One variable at a time.** Changing the router and the confidence formula together makes the delta uninterpretable.

**Never mix pre-fix and post-fix numbers.** Every result carries the git SHA that produced it.

**Descriptive docs stay descriptive.** `ARCHITECTURE.md` and `DATAFLOW.md` describe behaviour including its bugs. Criticism goes in `GAPS.md`.

**Code style:** match the surrounding file. The codebase uses plain `print()` for tracing — that is a known gap (`GAPS.md` #11), so prefer structured logging in new code once `core/logging.py` is wired up.

**Testing:** `tests/test_router.py` currently raises on its first case. Write real pytest tests before changing behaviour, not after.

---

## Architecture in one screen

```
POST /query
  → IntakeAgent    (LLM)   raw query      → CaseContext
  → RouterAgent    (regex) CaseContext    → QueryPlan
  → RetrievalAgent (Qdrant) QueryPlan     → RetrievalResult + confidence
  → AnswerAgent    (LLM)   RetrievalResult → answer + citations
  → ReporterAgent  (fpdf2) answer         → PDF
```

Each stage's output type is the next stage's input type. `clients/` is the only code touching OpenAI or Qdrant — which makes it the natural place for instrumentation.

| Fact | Value |
|---|---|
| Corpus | 4 PDFs, **1,011 chunks** |
| Composition | `BNSS` 48.1% · `Unknown` 29.5% · `BNS` 20.7% · phantom tags 1.8% |
| Embedding | `text-embedding-3-small`, 1536-d, cosine |
| Typical scores | **0.35–0.55** — not 0.8+. Every threshold is tuned to this |
| Tiers | HIGH ≥ 0.55 · MEDIUM ≥ 0.38 · LOW < 0.38 |
| Retrieval | `limit=15`, threshold `max(top − 0.15, 0.35)`, ≥3 forced through |
| Absent from corpus | Constitution, Evidence Act, case law, NI Act, Contract Act, Limitation Act |

---

## Current priority

Per [`docs/EVALUATION_PLAN.md`](docs/EVALUATION_PLAN.md):

**P0** settle the `gpt-5.2` / `temperature=0` question (2 min) → **P1** regenerate `requirements.txt` → **P2** structured logging (*the unblocker*) → **P3** real tests → **P4** routing cluster + clean re-ingest → **P5** confidence cluster.

**E1** — the annotated 50–100 query set — has no prerequisites and should run in parallel from day one.

Target venue: **ACL Rolling Review, 12 October 2026.** The August deadlines have passed or are unreachable, consistent with Prof. Joshi's instruction to prioritise evaluation quality over early deadlines.
