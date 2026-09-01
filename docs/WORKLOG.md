# Work Log

Dated session journal. **Newest first. Append-only** — never edit or delete a past entry; if something turns out wrong, add a correction in a later entry.

**Every session ends with an entry here.** See [`../CLAUDE.md`](../CLAUDE.md) for the protocol.

### Entry template

```markdown
## YYYY-MM-DD — Title

**Goal:** what this session set out to do
**Commit range:** `abc1234..def5678` (or "no code changes")

### Done
- …

### Found
- …

### Decided
- … → recorded as ADR-0NN in DECISIONS.md

### Open
- … → added to OPEN_QUESTIONS.md as QNN

### Next
- …
```

---

## 2026-08-23 — Ingest rebuilt, routing fixed, three query sets built

**Goal:** fix ingest, re-ingest cleanly, build the evaluation query set.
**Commit range:** uncommitted working tree.

### The index was in a worse state than the code suggested

Started Qdrant and inspected the live index before running anything:

| | Before | After rebuild |
|---|---|---|
| points | 1,813 | **1,933** |
| duplicate text | **618 (34.1%)** | **0** |
| `Unknown` tags | IPC 95%, CPA 86% | **0** |
| chunks with a section number | field absent | **1,528 (79%)** |
| CrPC share | **53.2%** | **39.1%** |
| IPC reachable | ❌ tagged `BNS` | ✅ **31.8%** |

**Duplicate cause:** `app.py` overwrote each chunk's deterministic id with `uuid.uuid4()`. A fresh random id every ingest means `upsert` has nothing to match, so it inserted copies instead of replacing. Ids are now `uuid5(namespace, "<doc>:<page>:<index>")` — same input, same id, forever.

**Tag cause confirmed live:** the index carried `BNSS` / `BNS` / `ConsumerProtection`, which are `fix_corpus_tags.py`'s values, not anything the pipeline produces. `GAPS.md` #4 verified against real data.

### Ingest changes

- **`ingest/registry.py`** (new) — explicit filename → statute lookup with in-force dates. Unregistered files now raise instead of silently tagging `Unknown`.
- **`ingest/chunk.py`** — splits on section boundaries instead of counting to 450 tokens. Section 41 now arrives as one 534-token provision instead of fragments.
- **Contents-page filtering.** 20.7% of CrPC chunks were table-of-contents listings. A listing reads *"Section 36. Powers of superior officers of police."* in 15 tokens of pure topic words while the real provision sits in 400 tokens of prose — the listing can out-score the law it points to. Detected via the em-dash Indian statutes use to separate title from body: **0% of contents entries have it, 45% of real provisions do.** Contents chunks 88 → 13.

### Got it wrong once, caught it

First filtering attempt worked **per page** and discarded page 69 entirely — which contains **Section 126 (maintenance procedure, 380 tokens of real law)** — because four short cross-page fragments dragged the page median down. Switched to per-**section** filtering. Both Section 126 and Section 41 preserved.

### Router fix

`ACT_MAP` mapped `"ipc" → "BNS"` — a workaround from when the IPC was unreachable, which became a bug the moment it became reachable. Measured live before the fix: *"punishment for murder under Section 302 IPC"* retrieved **BNS** text at **confidence 0.737 (HIGH)**.

Also `"consumer protection" → "Unknown"`, a tag no chunk has carried since the rebuild — zero results, silent filter drop, fallback across a CrPC-dominated index. That is the drift reported to Prof. Joshi.

Now maps to real corpora only: `IPC→IPC`, `BNS→BNS`, `CRPC→CRPC`, `CPA→CPA`.

### First live run of the logging pipeline

C3 had never executed on a real query. It has now:

```
Q: "Police are arresting my brother without a warrant right now."
retrieved: CrPC 1973 — Section 41 "When police may arrest without warrant"   (Feb: BNS, child trafficking)
decision_path: no_match      <- Router applied NO filter; it got this right by accident
entity_coverage_default_used: TRUE
composite: 0.682 = 0.2381 + 0.1440 + 0.3000   <- 44% of the score was the free default
```

Stripping the free 0.30 gives **0.382 — MEDIUM, not HIGH.** `GAPS.md` #2 measured on live data.

**Citation audit of that same answer:** 13 provisions cited, 3 grounded. Seven cite the **BNSS**, which is not in the index at all. The model emitted old and new numbering side by side — cross-vintage citation, caught on the first real query.

**Separates two things previously tangled: fixing retrieval did NOT fix grounding.** Retrieval was correct here and 76.9% of citations were still ungrounded.

### Cost, measured not estimated

`3,801 in + 2,400 out = $0.0059 (~₹0.50) per query`. 110 queries ≈ ₹55.

### Three query sets built

| Set | n | Gold | Purpose |
|---|---|---|---|
| `eval/queryset.jsonl` | 58 | 30 verified, 28 provisional | Hand-written, mixed |
| `eval/generated_queryset.jsonl` | 600 | **certain by construction** | Calibrates the retrieval machinery |
| `eval/layman_queryset.jsonl` | 93 | 66 uncontroversial, 27 to review | **The actual claim** — lived situations |

**The gold trick:** build the query FROM the section, and the section is the answer by construction — no legal review needed. That unblocks scale without waiting on a lawyer.

**Only 1 of 58 hand-written queries contained a usable event date.** Since only a date can decide IPC vs BNS, and real queries almost never supply one, the correct answer is frequently undeterminable from the question alone. That is a finding, and it is why the *search both and say it depends* decision was right. The layman set carries four date conditions per situation to measure it.

**BNS excluded from topic phrasings** — its PDF has no marginal notes, so title extraction returns the first clause of the provision. Numbered variants only there.

### Also fixed
- `/diag/env` was checking the removed `OPENAI_API_KEY` and reported `false` on a working setup.
- 5 `print()` statements containing `→` / `—` crash on a Windows console (cp1252). `router.py:59` would have crashed on **any** multi-corpus query.

### Open
- `IPC 304B` (dowry death) missing from the index — extraction or heading format. Not yet diagnosed.
- IPC↔BNS mapping (`data/ipc_bns_map_candidates.csv`, 511 rows) is **unverified**. Similarity-derived and demonstrably wrong on theft and robbery. **That is itself evidence**: if similarity cannot map the codes when handed both texts directly, it cannot separate them at retrieval time.
- Plugins installed but unused today. `pyright-lsp` would have caught two broken-string-literal bugs; heredoc editing bypasses it.

### Next
Run the full evaluation across all three sets, then Phase E remaining fixes (confidence arithmetic, rerank ordering).

---

## 2026-08-22 — Infrastructure build (Stages A–C, partial)

**Goal:** build the capture + tooling + foundation layers agreed in the plan, before any system work.
**Commit range:** uncommitted working tree.

### Done

**Stage A — capture**
- `cleanupPeriodDays` 30 → 3650. Claude Code was deleting session transcripts after 30 days; it no longer does. Protects past sessions retroactively.
- `.claude/hooks/session_log.py` + `UserPromptSubmit` and `PostToolUse(Bash)` hooks → `docs/SESSION_LOG.md`. Raw append-only trail of every prompt and command. Assistant responses deliberately excluded (they live in transcripts and would bloat the file ~10×).
- `.claude/hooks/guardrail.py` as `PreToolUse`. Hard-blocks `fix_corpus_tags.py` and `pip install -r requirements.txt` — the two ⚠ warnings in `CLAUDE.md` are now enforcement rather than advice. Verified: blocks both, allows `pytest` and single-package `pip install`.
- All five hooks pipe-tested in both directions.

**Stage B — tooling**
- arXiv MCP installed into an **isolated** venv at `.tools/arxiv-mcp/`, registered project-scope via `claude mcp add`. Shows as pending approval until the next `claude` start.

**Stage C — foundation**
- `requirements.txt` regenerated: 19 real dependencies. Removed the CV stack (torch, torchvision, ultralytics, opencv-python, pycocotools, thop) and five LangChain packages — none are imported anywhere. Added `requirements.lock.txt` (151 pins) for exact reproduction. `pip check` clean; `import app` works.
- `core/run_logger.py` — one JSONL record per query. Nine stage buckets, unknown stage names raise. Carries the four silent-failure flags (`intake.fallback_used`, `router.decision_path`, `retrieval.filter_fallback_fired`, `confidence.entity_coverage_default_used`), plus `scores_raw` pre-filter so the confidence ablation can be recomputed offline without re-querying. Self-tested.

### Broke and fixed

Installed `arxiv-mcp-server` into the **project** venv, which upgraded `starlette` 0.38.6 → 1.6.0 and broke `fastapi 0.115.0`. Caught by `pip check`. Uninstalled the server and its deps, restored `starlette==0.38.6` / `uvicorn==0.30.6`, confirmed `import app` works. Reinstalled the server into `.tools/arxiv-mcp/` instead.

**Rule now recorded:** never install tooling into the project venv. `.tools/` and `runs/` added to `.gitignore`.

### Out of sequence

`core/citations.py` was written **before** this infrastructure, contrary to the agreed plan. Kept — it is tested (12/12 on reference formats) and works on real data — but logged here as built out of order. It belongs to Stage D.

First real measurement from it, on the recorded arrest query:
```
answer cites:       BNSS 35, 47, 48, 58 · Constitution Art 22(1)
retrieved contains: BNS 193, 203, 190, 176, 2, 136
overlap:            ZERO      panel_prose_jaccard = 0.0
```

Known bug in it: proximity-based statute attribution produced `BNSS Article 22` — the BNSS has no Articles. Needs a kind/statute compatibility rule.

### Blocked

**C2 · OpenRouter migration** — `.env` has no `OPENROUTER_API_KEY`. Everything else in Stage C can proceed without it.

### Next

Wire the logger into `agents/retriever.py`; instrument `clients/` together with the OpenRouter migration once the key is available; pytest suite; `scripts/run_eval.py`; then Stage D as one block.

---

## 2026-08-17 — Full review and documentation pass

**Goal:** return to the project after ~6 months, re-establish understanding of the architecture, and assess readiness for the evaluation work Prof. Joshi directed on 6 Aug.
**Commit range:** no code changes. Documentation, config, and memory only.

### Done

- Full read of every source file on the live path (`app.py`, `agents/*`, `ingest/*`, `clients/*`, `report/*`, `streamlit_app.py`).
- Created the `docs/` set: `STATE`, `ARCHITECTURE`, `FILE_STRUCTURE`, `DATAFLOW`, `GLOSSARY`, `GAPS`, `RESEARCH_CONTEXT`, `EVALUATION_PLAN`, plus the three living documents.
- Established the documentation protocol in `CLAUDE.md`.
- Wrote project memory so future Claude Code sessions start with the full background.
- Ran three measurements that did not previously exist (below).

**Automation added** (`.claude/settings.json` + `.claude/hooks/`):

| Hook | Script | Behaviour |
|---|---|---|
| `SessionStart` | `session_start.py` | Injects the latest `WORKLOG.md` entry heading + its "Next" block, and all open questions from `OPEN_QUESTIONS.md`. `CLAUDE.md` carries static context; this carries the *changing* state, which is the part that goes stale. |
| `Stop` | `check_docs.py` | **Silent unless the docs are actually behind.** Compares the mtime of the live source tree (`agents/`, `ingest/`, `clients/`, `core/`, `report/`, `app.py`, `streamlit_app.py`, `requirements.txt`) against `docs/WORKLOG.md`; fires only when code is newer. |

The Stop hook is conditional on purpose: `Stop` fires every turn, and a reminder on every turn gets ignored — which is worse than no reminder. Both hooks fail open (any exception → silent) so a broken hook can never block a session. Both tested in both directions before wiring.

*Limitation, stated honestly:* hooks make skipping documentation a deliberate act rather than an oversight. They cannot make the content good.

### Found

**Measurement 1 — corpus tagging.** Ran the live ingest path over `tests/data/*.pdf`:

| Document | Chunks | Tags |
|---|---|---|
| BNS 2023 | 209 | `BNS` 100% ✅ |
| CrPC 1973 | 482 | `BNSS` 100% ✅ |
| IPC 1860 | 248 | **`Unknown` 95.2%** ❌ |
| CPA 2019 | 72 | **`Unknown` 86.1%** ❌ |

Cause: `guess_corpus` matches on `doc_name + text[:200]`, but the filename is `repealedfileopen.pdf` and **a statute never names itself by acronym** — the IPC's text says "this Code", never "IPC".

**Measurement 2 — index composition.** 1,011 chunks total: `BNSS` 48.1%, `Unknown` 29.5%, `BNS` 20.7%, `Judgments` 0.8%, `BSA` 0.7%, `Constitution` 0.3%. Three of those corpora have **no source document** — they are substring-matching artefacts.

**Measurement 3 — citation support.** Compared each answer's "Relevant Legal Provisions" table against what retrieval actually returned, across the 7 straightforward recorded queries: **6 of 7 cite statutory authority that was never retrieved**, including Acts absent from the corpus entirely (NI Act, Contract Act). Citation precision ≈ 1/7.

**Three blocking defects** (full detail in `GAPS.md`):

1. `entity_coverage` divides a chunk count by an entity count → exceeds 1.0 → saturates the clamp. The composite behaves as a binary entity-match detector rather than a three-signal score. **Blocks calibration and ablation.**
2. `guess_corpus` mis-tags two of four statutes; `fix_corpus_tags.py` patched the *database* but never the *code*, so re-ingestion silently reverts.
3. The CrPC drift: `ACT_MAP` still maps `"consumer protection" → "Unknown"`, which post-patch matches nothing → `retriever.py:93` silently drops the filter → unfiltered search over an index that is 48.1% CrPC.

**Correction to an earlier hypothesis.** The 5 Aug email to Prof. Joshi attributed the drift to the Router "only matching keywords like ipc and crpc." That is not the mechanism. The keyword *does* match; it maps to a corpus that no longer exists, and the silent fallback plus corpus imbalance produce the drift. Worth telling him — it's a sharper diagnosis and it's his item 4 largely solved.

**Also found:** the domain fallback conflates "criminal" with "penal", routing arrest/bail/FIR questions to the BNS instead of the CrPC; the refusal gate is structurally unreachable on a populated index (0 refusals in 23 runs); reranking corrupts `top_score` so the adaptive threshold loosens exactly when reranking fires; `requirements.txt` lists no runtime dependency of this project; the only test raises `AttributeError` on its first case; `core/logging.py` exists and is imported by nothing.

**Publication risk.** `Legal_MVP_Architecture_Document (2).pdf` §8.2 reports numbers the formula cannot produce (43.3% requires a positive entity term, contradicting the stated "not found"). §8.1 reconciles exactly, but 0.30 of its 0.706 was the neutral default, not a measurement. §9's corpus table contradicts what the code actually assigns. **Do not carry §8 into the paper.**

**Status of the 23 recorded runs.** They predate commit `ce1bded` — no `confidence` key in any captured JSON, and 15/15 citations everywhere, meaning zero adaptive filtering. They evaluate a system that no longer exists. Usable as a labelled pre-fix baseline only.

### Decided

- Understand first, fix second — no source changes until the architecture docs have been read and `GAPS.md` challenged → **ADR-011**
- Three separate living documents rather than one journal → **ADR-010**

### Open

- Q1 · Does `gpt-5.2` reject `temperature=0`? If so, Intake and Answer have been failing into silent fallbacks and every run under this config is void. **One command settles it.**
- Q2 · Keep the 23 runs as a labelled baseline, or discard and re-run?
- Q3 · Ingest case law, or scope the eval set to statutes only?
- Q4 · How to fix the entity-coverage neutral default — renormalise, penalise, or make it an explicit state?
- Q5 · Confirm the "Insights from Negative Results" deadline; confirm CODS 2026.

### Next

Per `EVALUATION_PLAN.md`, in order: **P0** settle Q1 (2 min) → **P1** regenerate `requirements.txt` → **P2** structured logging (*the unblocker*) → **P3** real tests → **P4** routing cluster + clean re-ingest → **P5** confidence cluster. **E1** (annotated query set) runs in parallel from day one — it has no prerequisites.

August venue deadlines have passed or are unreachable. Target **ARR, 12 October**, consistent with Prof. Joshi's "quality over earliest deadlines."

---

## Earlier history

Reconstructed from git; no contemporaneous log was kept.

| Date | Commit | What happened |
|---|---|---|
| 2026-02-25 | `ce1bded` | Composite confidence scoring + confidence-aware disclaimers. **The current confidence system.** The 23 recorded runs predate this. |
| 2026-02-09 | `dd4c59d` | README update |
| 2026-01-22 | `1ccbecb` | Paralegal Mode — Intake agent, Reporter agent, dashboard |
| 2026-01-19 | `0e44d28` | Agentic RAG architecture — Router, Retrieval, Answer agents. **`retrieve/` and `answer/` orphaned here.** |
| 2025-10-07/14 | `8b38718`… | Repo cleanup, README |
| 2025-09-16 | `f166967` | `.gitignore`, secrets kept untracked |
| 2025-09-08 | `d8b0ba6` | Ingest fix, UUID bug fix, Streamlit scaffold |
| 2025-09-06 | `0d87a24` | Ingestion + extraction fixes |
| 2025-08-26 | `c1c9bcb` | Initial commit |

Undated, inferred from artefacts: all stored vectors were once zeros (`fix_embeddings.py` exists to repair it) — **any evaluation predating that fix is void**; and `fix_corpus_tags.py` was run at some point to patch corpus labels in the database.

---

## 2026-08-23 (session 2) — Phase E complete, three query sets built

### What changed

Phase E as agreed, plus two defects found while verifying it. No scope changes.

| | Fix | Evidence it was real |
|---|---|---|
| E1 | Layman date gold labels | 23 of 24 `bns_era` rows carried IPC gold. A system citing CURRENT law scored wrong; citing REPEALED law scored right. The experiment ran backwards. |
| E2 | `panel_prose_jaccard` matching rule | Returned **0.0 on perfect grounding** for its entire life. Compared `Provision.key` exactly, and statutory text never names its own statute, so the panel side was always `?:section:302` against the prose side's `IPC:section:302`. |
| E3 | `entity_coverage` bounds | Counted CHUNKS, divided by ENTITIES. Reached 5.0 for a value weighted at 0.30 in a composite capped at 1.0 — the cap absorbed the error and the score looked plausible. |
| E4 | `top_score` after reranking | Read `res[0].score` after step 5 reorders by entity match, not score. A promoted hit at 0.31 against a real best of 0.58 dropped the adaptive threshold by 0.27 and stopped the filter filtering. |
| E5 | "vintage error" → corpus-vintage mismatch | The `RECODIFICATION` map was legally correct all along; only the label was wrong. Now split by direction (`cited_successor` / `cited_predecessor`) because they have different causes. |
| E6 | Contents filter + footnote parsing | 14 table-of-contents entries survived on dashes borrowed from the NEXT sub-heading (`B.–AID`). Separately, 13 amendment footnotes parsed as sections, and **all 13 collided with a real section number** — a query for IPC 8 could return a 1950 Adaptation Order note instead of the definition of gender. |
| E7 | Refusal gate | An out-of-corpus NI Act query returned HIGH confidence **0.73**. |
| E8 | Router domain fallback | `if "Criminal": target_corpus = "BNS"` made the IPC unreachable for any query not naming it. Found while verifying E7. |

### The measurement that decided E7

15 probe queries against the rebuilt index:

| | max similarity |
|---|---|
| in corpus, lowest — *"my landlord is not returning my deposit"* (CPA **is** indexed) | **0.278** |
| out of corpus, highest — *"grounds for divorce under the Hindu Marriage Act"* | **0.519** |
| nonsense, highest — *"how do I bake a chocolate cake"* | 0.208 |

The out-of-corpus query scores **higher than five of six legitimate ones**. The distributions are inverted, not merely overlapping, so **no similarity threshold can implement a corpus-boundary check**. Any cutoff rejecting the Hindu Marriage Act query rejects most real work.

This is a negative result worth reporting, not a tuning problem. The gate was therefore built on **named-statute detection**, which is deterministic: if the user says "Negotiable Instruments Act" and we never indexed it, that is certain. Its stated limitation is that layman queries name nothing — which is what the Router and the Phase H Date Resolver are for.

The score floor that remains (`NONSENSE_FLOOR = 0.25`) catches non-legal input only and is documented as a garbage filter, never as a corpus check.

### Index rebuilt

1933 → **1899 points**. IPC 615→595, CrPC 756→742. Zero duplicate ids. `$0.0058`.

### Query sets

| Set | Rows | What it tests |
|---|---|---|
| `layman_queryset.jsonl` | 120 | the access-to-justice claim. 30 situations × 4 date conditions. 8 CPA rows are controls (unchanged by the recodification); 5 rows are honestly unanswerable (BNSS not ingested). |
| `paired_queryset.jsonl` | **99 (new)** | **the thesis.** 33 verified IPC↔BNS provision pairs × 3 phrasings. Same offence, same wording, only the numbering scheme differs. |
| `generated_queryset.jsonl` | 200 | instrument calibration; gold certain by construction. |

`data/recodification_map.json` is new — 33 IPC→BNS entries whose targets were located in this index and whose bare-Act text was read to confirm the subject matches, plus 10 CrPC→BNSS entries marked `unverified_not_in_corpus`.

### Tests

52 → **89 passing.** Nine tests that pinned the old defects were rewritten to assert the corrected behaviour, each recording the value it used to assert. Every metric expectation is now worked out by hand in its docstring — a metric test whose expectation came from running the code proves only that the code is deterministic.

### Next

Phase G: run all three sets, produce the E1–E6 tables.

### Still open

- **BNSS and BSA are not ingested.** 5 layman rows and all 10 CrPC→BNSS map entries are unreachable by construction. Stated in Limitations, not hidden.
- `score_gap` rewards uniform irrelevance — flat, uniformly bad scores earn the full 0.15 for "consistency". Pinned in a test rather than fixed, because it is one of the three signals under ablation in E6.
- 68 of 120 layman rows are `needs_review` and should not be counted until someone with legal training has checked them.

---

## 2026-08-23 (session 2, continued) — Phase G run: 419 queries, first clean numbers

Runs `eval_2026-08-23_{0215,0231,0256}_5184e78`. Full tables in [`docs/results/PHASE_G.md`](results/PHASE_G.md).

Reproduce: `python scripts/analyze_eval.py --runs runs/eval_2026-08-23_0215_5184e78 runs/eval_2026-08-23_0231_5184e78 runs/eval_2026-08-23_0256_5184e78` and `python scripts/ablate_filter.py`.

### The result the main table was hiding

The joined evaluation reported a **perfect** corpus confusion matrix on the paired set — 33/33 IPC, 33/33 BNS, zero off-diagonal. Taken at face value that refutes the paper's hypothesis.

It is not a result. The Router reads the Act name and applies a hard Qdrant filter (`ipc_numbered → filter=IPC`, `bns_numbered → filter=BNS`), so an IPC-numbered query **cannot** return a BNS chunk. The diagonal was guaranteed before any vector was compared.

`scripts/ablate_filter.py` removes the filter:

| query names | → IPC | → BNS | correct | chance |
|---|---|---|---|---|
| IPC (repealed) | 32 | 1 | **97.0%** | 31.3% |
| BNS (in force) | **16** | 17 | **51.5%** | 22.3% |

Top-1 only: a query naming the Bharatiya Nyaya Sanhita gets an IPC chunk first **19/33**. Cross-statute retrieval failure is real and **directional — toward the repealed code**.

### Other findings

| | |
|---|---|
| layman set | gold retrieved **7.5%**, gold cited **85.0%**, ungrounded **0.838** — answers come from the model's own knowledge, not the corpus |
| ideal conditions | generated set retrieves the named section only **68.0%** of the time — a ceiling on everything else |
| neutral phrasing | **93.9%** retrieve the repealed IPC provision vs 36.4% the current BNS one |
| date | retrieval flat across all four conditions; `gold cited` falls 96.4% → **60.9%** in `bns_era` |
| confidence | `entity_coverage` AUROC **0.492** = chance; composite **0.610** is *worse* than raw max similarity **0.663**; only **27/419** answers fully grounded |
| refusal | **0/419**, exactly as the named-statute gate design predicts |
| routing | `act_map_single` 65.9% vs `no_match` 49.0% overall; 85.7% vs 28.9% on the layman set alone |

### Explicitly not claimed

Messiness runs backwards (confounded with topic — messiness-1 rows are the CPA scenarios whose gold is a definitions section). CPA controls sit at 0.0% for the same reason. Nothing about BNS-era procedure, since the BNSS is not ingested.

### Infrastructure defects found while running

- The clean-tree guard was unsatisfiable: the server writes `runs/` during a run, and the session hook appends to `docs/SESSION_LOG.md` on every command. `runs/` is now gitignored and `SESSION_LOG.md` exempted.
- `git()` calls `.stdout.strip()`, eating the leading space of the first porcelain line, so the fixed `line[3:]` offset sliced into that one path (`ocs/SESSION_LOG.md`). Blocked four runs while every direct test of the parser passed — the tests did not go through `git()`.
- `already_done()` read `queries.jsonl` (written by the server) instead of `eval_summary.jsonl` (written by the runner), so `--resume` never skipped anything.
- `--queryset` and `--resume` both crashed on relative paths.
- Killed-and-resumed runs append duplicates: 320 rows for 200 queries. The analyzer now deduplicates by `query_id` and reports how many it dropped. **Left unfixed in the runner** — recorded in `docs/OPEN_QUESTIONS.md`.

### Next

Re-gold the CPA controls; vary messiness within topic; run the filter ablation on the layman set. Then Phase H.

---

## 2026-08-23 (session 2, continued) — Phase H: the intervention, built and measured

Full tables in [`docs/results/PHASE_H.md`](results/PHASE_H.md). Reproduce with
`python scripts/compare_runs.py --baseline runs/eval_2026-08-23_0353_302e1f8 --intervention runs/eval_2026-08-23_0410_302e1f8_both`.

### Built

| | Component | Tests |
|---|---|---|
| H1 | `core/dates.py` — resolve the event date to IPC_ERA / BNS_ERA / BOTH_ERAS / UNKNOWN | 35 |
| H2 | `core/statute_mapper.py` — translate the citation to the code that governs | 18 |
| H3 | `baseline / date / mapper / both` flag; `QueryPlan.target_corpora` for multi-corpus filters | — |
| H4 | `eval/paired_dated_queryset.jsonl` — 99 queries where the code named and the date disagree | — |

Suite 89 → 142.

### Result 1 — retrieval is fixed

| | baseline | + intervention |
|---|---|---|
| correct corpus dominates (both conflict types) | **0.0%** | **100.0%** |
| wrong-era provision retrieved (`conflict_ipc_named`) | **81.8%** | **0.0%** |
| `agree_control`, every measure | unmoved | unmoved |

The control not moving is what makes this a fix rather than a flipped preference.

### Result 2 — routing was not the whole problem

With routing perfect, section-level retrieval is **78.8%** when the target is an IPC section and **36.4%** when it is a BNS section — same 33 offences, same wording. The BNS is 22.3% of the index and its PDF carries no marginal notes, so chunks start with the first clause rather than the subject. That is a corpus and chunking problem, not a routing one, and it is testable by re-chunking that one PDF.

### Result 3 — the answer barely follows the retrieval

Whether the answer states the law changed: 39.4% → 63.6% and 51.5% → 66.7%, control flat at 3.0%. Both point the right way, **but the intervals overlap** (39.4% [24.7, 56.3] vs 63.6% [46.6, 77.8]) and this is not established at n=33.

The gap between Result 1 and Result 3 is the finding: the largest possible retrieval improvement moved the answer by ~20 points. This is Phase G's ungrounded-rate result shown causally — the inputs changed and the outputs barely followed.

### A metric retired mid-analysis

`gold_cited` and `wrong_era_cited` are **unusable on this query set**. `core/citations.py` attributes a statute by proximity in the answer text, and these answers legitimately mention both codes, so an answer citing BNS 190 was recorded as `IPC Section 190` because "Indian Penal Code" appeared earlier. `wrong_era_cited = 100%` therefore cannot separate "wrongly relied on repealed law" from "correctly explained the law changed" — opposite behaviours, identical measurement.

Caught by reading one answer before reporting the number. Recorded in `docs/OPEN_QUESTIONS.md`.

### Next

Bind citations to their supporting chunk so attribution stops depending on proximity; re-run the comparison on the layman set; investigate BNS chunking.

---

## 2026-09-01 — Wave 0 (discovery). Two of my earlier claims were wrong.

Branch `metrics/sept-01`. Baseline 142 tests passing. Cost this wave: **₹0.06** (621 embedding calls, no generation).

Artifacts: `experiments/SCHEMA.md`, `experiments/stages.jsonl` (621 rows, all three retrieval stages with authoritative `section_number`), `experiments/check00_preflight.py`, `check01_determinism.py`, `check02_reproduce.py`, `check03_stage_effect.py`.

### CORRECTION 1 — the "counting bug" was not a bug

On 26 August I claimed `scripts/analyze_eval.py` mis-identified retrieved passages by parsing the first 160 characters of text instead of reading `section_number`, and that this had "halved a published figure: layman retrieval reported as 7.5% is actually 15.0%."

**Measured against authoritative `section_number` on 4,906 Stage-C chunks:**

```
recovered correctly : 4,906  (100.0%)
found nothing       :     0
found the wrong one :     0
```

The text-parsing rule has a **0.0% error rate**. The 1,020 chunks (17.2%) carrying no `section_number` are preamble, split continuations, or demoted footnotes — they are not sections, so scoring them as "not the gold section" was always correct.

**The 7.5% / 15.0% discrepancy was a STAGE confusion, not a bug — mine.**

| Stage | Layman gold retrieved |
|---|---|
| `raw_15` — what Qdrant returned | **15.0%** [9.7, 22.5] |
| `reranked_15` | 15.0% [9.7, 22.5] |
| `filtered_n` — what reached the model | **7.5%** [4.0, 13.6] |

I compared `raw_15` (my 26-Aug probe searched unfiltered) against the README's `filtered_n`. Both figures were always correct at their own stage. **`docs/PLAN.md` section 4.1, "'retrieved' has three meanings", is the rule that caught this.** It was written by Udita.

Consequence: Wave 1 Subagent 2 had no bug to fix and has been repurposed (below).

### CORRECTION 2 — `section_number` was never in the logs

`SCHEMA.md` records the real chunk schema: `['corpus', 'doc', 'page', 'score', 'text_head']`. No `section_number`. It exists in the Qdrant payload but was never copied into the run log. Recovery by `(doc, page)` fails — 376 of 495 keys (76.0%) hold more than one section.

Resolved by Option A: a retrieval-only re-run capturing all three stages plus the payload field. ₹0.06.

### Pre-flight checks (all passed)

| Check | Result |
|---|---|
| Index identity | 1,899 points; composition CRPC 742 / IPC 595 / BNS 424 / CPA 138 exact; **1,200 of 1,200** logged chunks re-found in Qdrant by text |
| Reproducibility | **589/621 (94.8%)** identical chunk list *and* order; 22 same set different order; **7 (1.1%)** genuinely different (HNSW is approximate); max score deviation 0.0063 |
| Determinism | Keyed on `(query_id, intervention)`: 228 same-condition repeats, **206 (90.4%) byte-identical**; `n_citations` differed **0** times; refusal flipped **0** times; confidence differed on 22 by at most **0.0005** — three orders of magnitude below the 0.55/0.38 tier boundaries |

**The pipeline is effectively deterministic.** Claimable with evidence. The 99 of 222 "duplicate" `query_id`s that disagreed were baseline-vs-both — two conditions, not repeats.

### NEW FINDING — the adaptive filter is what costs laypeople their answers

Gold section retrieved, strict, by stage:

| Query set | N | `raw_15` | `filtered_n` | filter cost |
|---|---|---|---|---|
| generated | 198 | 69.2% | 67.7% | −1.5 pt |
| paired | 99 | 73.7% | 70.7% | −3.0 pt |
| paired_dated | 197 | 49.2% | 45.2% | −4.0 pt |
| **layman** | **120** | **15.0%** | **7.5%** | **−7.5 pt, i.e. HALF** |

The adaptive filter — `threshold = max(top_score − 0.15, 0.35)` — removes half of all successful layman retrievals while costing the other sets 2–4%. Hypothesis to test in Wave 2: the 0.35 absolute floor is binding on layman queries because their top scores sit near 0.40, whereas technical queries top out well above it.

This is a new, unreported mechanism and it is measured on data already paid for.

### Schema facts worth keeping

- `pair_id` exists on **every** query set — the `situation_id` the plan asked for needs no reconstruction. paired 33×3, paired_dated 33×3, layman 30×4, generated 80×2.5.
- Gold present on **518 of 518** rows across the four current sets.
- `answer.prompt_variant` is `"HIGH"` on all 859 rows — the tier bug, confirmed in schema.
- `answer.prompt_tokens` / `completion_tokens` **are** logged, so per-query cost is recoverable although `cost_usd` never was.
- `date.*` and `mapper.*` buckets exist and are populated — Phase H logging worked.
- Summaries hold 850 rows for 521 unique `query_id`; **deduplication belongs inside `load_logs()`**, not in each caller.

### Next

Task B — build `experiments/metrics_lib.py` with known-answer tests. Wave 1 Subagent 2 repurposed to `exp08_filter.py`, the adaptive-filter investigation (analysis only; the deployed 0.35 floor is **not** to be changed).

---

## 2026-09-01 — Wave 1: three parallel tasks, one reframing of the paper

Branch `metrics/sept-01`. Three subagents ran concurrently under the PLAN.md
concurrency rules (one owner per file, no subagent runs git, everyone imports
`experiments/metrics_lib.py`). Zero API calls; cost to the OpenRouter key ₹0.

### S1 — tier logging bug (agents/answer.py)

`prompt_variant` was initialised to "HIGH" and never reassigned in the LOW or
MEDIUM branches. The disclaimer itself was always applied correctly; only the
recorded field was wrong.

Measured, not assumed: **369/859 = 42.96%** of records carried the wrong tier,
95% Wilson [39.69, 46.29]. Logged {HIGH: 859}; true {HIGH: 490, MEDIUM: 354,
LOW: 15}. The recomputation replays the branch rather than estimating it,
because `app.py:229` writes `composite = retrieval.confidence` — the logged
float is the same value the `if` tested.

Reproduce: see `results/EXPLAIN.md`, block "Tier logging bug".

Fix extracts a pure `tier_for_confidence()`; the disclaimer-selecting branch is
byte-for-byte unchanged. +31 tests.

**No published number is affected.** `prompt_variant` is written by
`app.py:241` and read by nothing in `experiments/` or `scripts/`. What it
blocked — the Phase G tier analysis — is now recoverable retrospectively on the
existing 859 rows at zero API cost.

**Incidental finding, not investigated:** the REFUSED path has never fired in
859 records. Lowest tier observed is LOW at 15 rows (1.75%). A refusal
mechanism that never refuses is a paper-relevant fact. Path left intact.

### S2 — adaptive filter analysis (experiments/exp08_filter.py)

Not a bug fix. Analysis of `threshold = max(top_score - 0.15, 0.35)`.
The deployed 0.35 floor was NOT changed anywhere in the system.

Paired check agreed exactly: layman `filtered_n` recall reconstructed = 0.075000,
from Wave 0 stored Stage C chunk list = 0.075000; agreement under 1e-12 on every
set, and 0 length mismatches in 621 rows.

**Binding arm — a clean 100/0 split both ways.** All 9 layman cuts were bound by
the 0.35 floor; 0 of the 14 non-layman cuts were. Mechanism: layman `top_score`
mean 0.335, so the relative arm computes 0.185, the floor at 0.35 dominates, and
cut gold chunks averaged 0.288.

**Counterfactual sweep** (recall / mean chunks reaching the model):

| set | n | 0.35 deployed | 0.30 | 0.25 | 0.20 | none | raw_15 ceiling |
|---|---|---|---|---|---|---|---|
| generated | 198 | 0.677 / 11.2 | 0.677 | 0.677 | 0.677 | 0.677 | 0.692 |
| paired | 99 | 0.707 / 10.3 | 0.707 | 0.707 | 0.707 | 0.707 | 0.737 |
| paired_dated | 197 | 0.452 / 10.1 | 0.452 | 0.452 | 0.452 | 0.452 | 0.492 |
| layman | 120 | 0.075 / 5.1 | 0.117 / 9.0 | 0.117 / 13.4 | 0.150 / 15.0 | 0.150 / 15.0 | 0.150 |

On three of four sets the floor is a total no-op — removing it moves recall by
0.000. Their 1.5/3.0/4.1 pp losses come from the relative arm, which this sweep
holds fixed.

**The reframing.** The filter halves layman recall 15.0% to 7.5%. But for 102 of
120 layman queries the gold section was never in the retrieved 15 at all.
Abolishing the filter entirely still leaves 85% of public-style questions
unanswerable. **The paper should anchor its primary claim at `raw_15`** — the
stage where no filter exists and where the floor is provably irrelevant to the
other three sets — and report the filter loss as a secondary mechanistic
finding. This also pre-empts the reviewer objection that the failure is a
tuning artefact: `raw_15` is measured before any tuning knob applies.

Determinism: NOT demonstrated by S2 (a command timed out). Demonstrated by the
main agent afterwards — two full runs, output byte-identical.

Rule breach to record: S2 issued a command containing `git status`, against the
no-git rule. It timed out before completing and `git status` is read-only, so no
repository state was altered.

### S3 — citation statute-binding bug (core/citations.py)

`_statute_near()` bound a statute to a section number by taking the nearest
statute name in a character window on either side. Since answers legitimately
name both IPC and BNS, the parser broke precisely on the queries this paper
studies.

Citation unit chosen: the reference regex match extended over content-free
tokens (whitespace, list punctuation, the words of/the/under, a 4-digit year).
Everything else terminates it. Two refinements forced by real counterexamples: a
trailing statute is decisive and a leading one only a fallback (Indian citation
form puts the Act after the number); and an Act is discarded when a list
separator divides it from the reference and another reference begins right
after — which is what separates "Section 357C CrPC / Section 397 BNSS" from
"CrPC Section 154(3) / BNSS Section 175(3)".

UNKNOWN reuses `statute=None`. All six call sites checked; a truthy sentinel
would have walked past four of them.

**Blast radius**, 859 answers / 6,687 citation units. The old parser reproduces
the logged `verifier.cited` 857/857 = 100.0%, so "before" is genuinely the
parser that produced the recorded numbers.

    answers naming BOTH IPC and BNS (at risk)   497/859  = 57.9% [54.5, 61.1]
    units UNCHANGED                            5555/6687 = 83.1% [82.2, 84.0]
    units confident statute -> UNKNOWN         1060/6687 = 15.9% [15.0, 16.7]
    units statute A -> statute B                 72/6687 =  1.1% [0.9, 1.4]
    units UNKNOWN -> confident statute            0/6687 =  0.0% [0.0, 0.1]
    answers with >=1 changed unit                447/859  = 52.0% [48.7, 55.4]

Concentrated on the at-risk population, intervals non-overlapping:
to-UNKNOWN 20.8% [19.5, 22.1] at risk vs 9.7% [8.7, 10.8] not at risk.

**70 of 72 flips (97.2% [90.4, 99.2]) are recodification pairs** — CrPC to BNSS 46,
BNS to IPC 10, BNSS to CrPC 8, IEA to BSA 2, IPC to BNS 2. The parsing error
landed on the treatment variable. That is a validity problem, not a precision
problem.

+23 tests. No pre-existing test failed; nothing was pinning the old behaviour.

### Suite

175 (Wave 0) + 31 (S1) + 23 (S3) = **229 passing**, `pytest tests/ -q`.

Note: bare `pytest -q` from the repo root has never worked. It aborts during
collection on root-level `test_ingest.py`, a manual script that opens three PDFs
from the Downloads folder at import time. Pre-existing and unrelated.
**The suite must be run as `pytest tests/ -q`.** Earlier WORKLOG entries quoting
a bare `pytest` command were describing the wrong invocation; the counts
themselves were from `tests/` and stand.

### Correction

`docs/PLAN.md` repurposed Subagent 2 brief said the filter cost paired_dated 8%.
Measured: 4.1 percentage points. That figure was introduced by me when rewriting
the brief and was never in this WORKLOG, which said 2-4% (consistent with the
measured 1.5-4.1 pp). Corrected in place in PLAN.md.

### Next

The GATE: three smoke-test numbers, per PLAN.md section 5. Do not start Wave 2
before reading them.

---

## 2026-09-01 — GATE: the spine holds, and two of my own defects were caught

Branch `metrics/sept-01`, after Wave 1. Three numbers per `docs/PLAN.md` §5.
Full explanation blocks (three, eight headings each) in `results/smoke_test.md`.
Cost: about ₹0.01, the ablation re-run only. Everything else computed from logs.

### Verdict

| Gate condition | Required | Measured |
|---|---|---|
| 97.0 / 51.5 survive the fixes | yes | **reproduced exactly** — 32/1 and 16/17 |
| positives under `retrieved@k` | 200+ | **327** |
| positives still stuck at 27 | would mean the label is miswired | no — 27 is `grounded` only, by design |

Per the plan's decision table: **spine holds, Wave 2 may run.**

### 1 — the headline is unchanged

`scripts/ablate_filter.py` re-run against the live collection (1,899 points,
green). Output captured this time at `results/ablation_rerun_2026-09-01.txt`;
the original run printed to stdout only and was never saved, so 97.0/51.5
existed in `docs/` and nowhere as data.

Dominant corpus among the top 15, corpus filter OFF, n=33 per row:

| Query names | to IPC | to BNS | correct | chance |
|---|---|---|---|---|
| Indian Penal Code (repealed) | 32 | 1 | **97.0%** [84.7, 99.5] | 31.3% |
| Bharatiya Nyaya Sanhita (in force) | **16** | 17 | **51.5%** [35.2, 67.5] | 22.3% |

Top-1 only: IPC 30/3 = 90.9% [76.4, 96.9]; BNS 19/14 = 42.4% [27.2, 59.2].
**Identical to `docs/results/PHASE_G.md` in every cell**, after three bug fixes
and a new metric library.

A DIFFERENT question, recorded so the two are never conflated: gold-section
recall through the deployed pipeline with the corpus filter ON, paired set,
`retrieved@15`, n=33 per cell.

| Stage | IPC-named | BNS-named |
|---|---|---|
| `raw_15` | 29/33 = 87.9% [72.7, 95.2] | 11/33 = 33.3% [19.8, 50.4] |
| `reranked_15` | 29/33 = 87.9% | 11/33 = 33.3% |
| `filtered_n` | 26/33 = 78.8% [62.2, 89.3] | 11/33 = 33.3% |

The asymmetry survives with the corpus filter ON, so it is not an artefact of
switching a filter off to expose it. The adaptive filter costs the IPC row 9.1
points and the BNS row nothing — it removes correct retrievals only where
retrieval was already working.

**Two filters exist and must not be confused.** The *corpus filter* restricts
the Qdrant search to one statute before retrieval. The *adaptive score filter*
`max(top_score - 0.15, 0.35)` drops low scorers afterwards. `ablate_filter.py`
disables the FIRST; `stages.jsonl` replays it as recorded, which is why the
three-stage table cannot reproduce 97.0/51.5 and must not be asked to.

### 2 — positives under each definition, n=617 labelled rows

| Definition | Stage | Positives | Rate |
|---|---|---|---|
| `retrieved@15` | `raw_15` | **327** | 53.0% [49.1, 56.9] |
| `retrieved@15` | `reranked_15` | 327 | 53.0% [49.1, 56.9] |
| `retrieved@15` | `filtered_n` | 304 | 49.3% [45.3, 53.2] |
| `cited` | pre-fix parser (logged) | 533 | 86.4% [83.5, 88.9] |
| `cited` | post-fix parser (re-parsed) | 538 | 87.2% [84.3, 89.6] |
| `grounded` | — | 27 | 4.4% [3.0, 6.3] |

Reranking moves nothing (327 to 327), as expected: it reorders the same 15
passages, and a presence metric cannot see a reordering. Rank-order metrics
must therefore be reported separately in Wave 2.

**The S3 citation fix barely moves this: 533 to 538, five rows.** It changes
15.9% of citation units and flips 72, but `cited` asks only whether the gold
number appears somewhere, and most changes turn a confident statute into
UNKNOWN, which still matches on number alone. The fix will show up in
statute-sensitive metrics, not this one. Do not oversell it.

### 3 — composite vs raw max score, paired bootstrap, n=617

| Definition | Positives | composite | max_score | paired diff | p | Supported claim |
|---|---|---|---|---|---|---|
| `grounded` | 27 | 0.531 [0.449, 0.608] | 0.589 [0.489, 0.686] | -0.058 [-0.169, +0.056] | 0.3154 | **no better than** |
| `retrieved@15` | 327 | 0.663 [0.617, 0.710] | **0.784** [0.747, 0.819] | **-0.121** [-0.162, -0.080] | <0.0001 | **worse** |
| `cited` post-fix | 538 | 0.571 [0.500, 0.643] | 0.675 [0.602, 0.744] | -0.103 [-0.159, -0.046] | 0.0004 | **worse** |

The README word "worse" IS supported — and more strongly than the README claims
— but only under the definitions with the positives to support it. Under
`grounded` (27 positives) the honest statement is "no better than".

Recommended claim for the paper: **a single raw cosine similarity discriminates
better than the engineered three-signal composite, on 617 queries, at
p < 0.0001** — reported under `retrieved@15` as primary, with all three
definitions shown and the power limitation of `grounded` stated.

`max_score` reaching 0.784 matters: this is a design finding about the
composite, not a "nothing works here" result.

**Which definition produced the README pair 0.610 / 0.663 is not recorded**, and
none of the three rows reproduces it. Same class of omission as the unlabelled
stage figures. Treat those README numbers as superseded, not reconcilable.
Flagged for Wave 4.

### Two defects in my own Wave 0 code, both caught here

**(a) `same_section` raised ValueError on real data.** `normalise_section`
handles Sections; Constitution *Articles* and CPC *Orders*/*Rules* fell through
to a fallback returning no `:` separator, which `same_section` then split on.
28 distinct such strings in the logs, `CONSTITUTION Article 226` 29 times.
Fixed so the kind word is kept: `CONSTITUTION:ARTICLE226`, which correctly does
NOT equal Section 226 — and the Constitution is not in this corpus, so
collapsing the kind would have manufactured matches among precisely the
out-of-corpus citations the paper counts.

**(b) The fix for (a) silently zeroed every retrieval metric.**
`ranked_sections()` returns canonical strings and `same_section()` normalises
them again, so the function is routinely called on its own output.
`normalise_section` was never idempotent; the old fallback was a no-op there by
accident. The corrected fallback stripped the statute prefix a second time and
turned `BNS:190` into `BNS::190`. Result: 0/617 under `retrieved@k`. Nothing
crashed. Every number looked like a real finding.

This is exactly the failure the gate exists to catch, and it is exactly the
failure mode that cost this project six months in February. Fixed by making
`normalise_section` idempotent and pinning it with
`test_idempotent_on_its_own_output`.

Suite 229 to 237 (`pytest tests/ -q`).

### Next

Wave 2 — five metric families in parallel. Per the plan, Wave 2 must not start
until these three numbers have been read.

---

## 2026-09-01 — Wave 2: five metric families in parallel

Branch `metrics/sept-01`. Five subagents concurrent, one owner per file, none ran
git, all imported `experiments/metrics_lib.py`. Zero API calls, cost to the
OpenRouter key ₹0. All six result CSVs share the exact long-format schema;
1,312 result rows total. Suite 237 passing throughout.

Outputs: `retrieval_metrics.csv` (623), `routing_confusion.csv` (109),
`calibration.csv` (172), `ablation.csv` (133), `robustness.csv` (125), plus
Wave 1 `filter_analysis.csv` (150). Explanation blocks merged into
`results/EXPLAIN.md`, eight headings each.

### THE FINDING OF THE WAVE — the deployed confidence formula has a sign error

S4 paired check. The formula recorded in CLAUDE.md and in the Wave 2 brief,
`0.55*top_k_mean + 0.15*score_gap + 0.30*entity_coverage`, reproduces NONE of
the 617 logged composites (max deviation 0.148, all 617 rows off by >1e-3).

The deployed formula at `agents/retriever.py:137-142` normalises and INVERTS
the gap:

    gap_penalty = min(score_gap / 0.3, 1.0)
    composite   = 0.55*top_k_mean + 0.15*(1.0 - gap_penalty) + 0.30*entity_coverage

With the inversion, reconstruction agrees to 9.0e-05 on every row — the 4-dp
rounding floor. Verified by two routes sharing no code, both asserting.
**The logged scores are correct; the written description was wrong.**

Consequence, `retrieved@k` at `raw_15`, n=617, 327 positives:

| Signal | AUROC | paired diff vs composite | p |
|---|---|---|---|
| `max_score` | 0.784 | +0.121 | <0.0001 |
| `top_k_mean` | 0.757 | +0.094 | <0.0001 |
| `score_gap` raw, uninverted | 0.730 | +0.067 | 0.018 |
| **`composite` deployed** | **0.663** | — | — |
| `entity_coverage` | 0.581 | -0.083 | <0.0001 |
| **`gap_term` as deployed** | **0.270** | -0.393 | <0.0001 |

An AUROC of 0.270 is anti-predictive: below 0.5 means the signal points the
wrong way. The gap is worth 0.730 raw and 0.270 inverted. Confirmed by a
secondary sweep with the gap NOT inverted: 0.55/0.45/0.00 gives 0.785, which
beats `max_score`. **The signal is valuable and wired backwards.**

Leave-one-out, renormalised: dropping `gap_term` IMPROVES the composite by
+0.0415 (p<0.0001); dropping `entity_coverage` changes nothing (-0.005, p=0.82);
dropping `top_k_mean` collapses it to 0.486.

Weight sweep, 231 weightings: argmax is **1.00 / 0.00 / 0.00 under all three
correctness definitions**, and the peak is sharp (1 of 231 within 0.005).
Held out on a 60/40 stratified split the gain survives at +0.0918 on
`retrieved@k` (test AUROC 0.744 vs deployed 0.652).

NOTHING DEPLOYED WAS CHANGED. 55/15/30 and the 0.55/0.38 tiers stand. This is
analysis. The weights were fixed in Feb 2026 before any score was logged, and
that remains a methodological strength.

Correction to our own docs: `entity_coverage` is NOT broken as GAPS.md
describes. In these logs it takes only {0.0, 0.5, 1.0}, never exceeds 1.0, and
no free 0.30 default appears. Its AUROC is 0.581, not the 0.492 repeatedly
quoted. It is not defective — it is a three-level flag that is CONSTANT for
43.4% of queries, and exactly 0.500 on all 120 layman rows because no layman
query names a section.

`entity_coverage` scores 0.386 on recodification queries — BELOW CHANCE —
because the query names the repealed IPC section while the corpus holds the
successor BNS text. A legal fact surfacing as a measurement artefact.

### S5 — the claims that FAIL. Read this before writing anything.

**1. The recodification gap dies under two of three correctness definitions.**
It holds under `retrieved@15` at every stage and under every restriction:
+0.545 [0.303, 0.758] clustered. Under `cited` it is -0.030 [-0.121, 0.061] and
under `grounded` -0.030 [-0.091, 0.000] — both contain zero and the sign flips.

Cause, measured: the IPC arm cites the gold section 90.9% of the time and the
BNS arm 93.9%. The answer generator cites correct sections REGARDLESS of what
was retrieved. **The failure is a retrieval failure, and the answer text hides
it.** This must be stated as a scope condition, not buried.

**2. The layman rate at `filtered_n` dies under clustering.** Naive interval
[0.033, 0.125] excludes zero; clustered [0.000, 0.167] does not. The 9 hits sit
in only 3 of 30 situations. This is the one threshold crossing in the wave.

**3. "Composite worse than max_score" survives only under `retrieved@15`.**
Under `cited` it holds unrestricted but dies under all three real restrictions;
under `grounded` it never holds and once flips to +0.219.

Design effects (naive variance vs clustered): layman 1.93, max_score AUROC 1.37,
composite AUROC 1.26, AUROC diff 1.10. Clustering does NOT always widen here —
`paired_recodification` 0.64 and `paired_dated_conflict` 0.79, because
contrastive variants are BUILT to disagree, so within-cluster correlation is
negative. S5 flagged its own first implementation for inverting this ratio and
caught it against theory before it reached the CSV.

S5 left CHECK 2 deliberately FAILING: 8 AUROC values narrowed under clustering,
4 explained by measured negative within-situation correlation, **4 unresolved**
(`cited`/`grounded` restricted subsets, ratios 1.043-1.121). Resampler bug and
Monte Carlo noise ruled out across 5 seeds. Not ruled out: AUROC is a rank
statistic and the mean-based design-effect argument may not transfer.
**Do not rely on clustered AUROC intervals for those two restricted subsets.**
`restriction=none` is unaffected.

### S3 — calibration

Coverage at 10% risk, i.e. what share of questions could be answered while
keeping errors at or below 10%:

| | retrieved@15 | cited | grounded |
|---|---|---|---|
| composite | **0.0000** | 0.6483 | **0.0000** |
| max_score | 0.0486 | 0.8768 | 0.0000 |

The zeros are MEASURED, not missing. For composite under `retrieved@15` no
threshold anywhere on the curve reaches 10% risk; the curve minimum is 0.2685
at 59.2% coverage. **There is no confidence setting at which this system can
answer any share of questions and be wrong one time in ten.**

ECE (Expected Calibration Error, lower better), clustered CIs:
composite 0.2410 [0.1983, 0.2737] vs max_score 0.1270 [0.0991, 0.1724] under
`retrieved@15`. Brier 0.2326 vs 0.2113. AURC 0.398 vs 0.271. Raw similarity
beats the engineered blend on every axis measured.

**The composite reliability curve is NON-MONOTONE.** Accuracy by bin:
0.35, 0.16, 0.15, 0.28, 0.95, 1.00, 0.79, 0.51, 0.56, 0.55. It peaks at
composite ~0.62 and falls back to the base rate at the top. `max_score` is
monotone throughout. A single ECE number hides this completely.

Platt scaling on the test half only: composite/`grounded` ECE 0.550 -> 0.037
looks spectacular and is DEGENERATE — the fitted probabilities span 0.037-0.049,
a near-constant equal to the base rate, AUROC 0.524. Reported as a failure, not
a success. Platt is monotone so it cannot repair the non-monotonicity either;
on the deployed configuration it moves ECE only 0.220 -> 0.201.

### S2 — routing

Base-rate control VERIFIED, not refuted. Index shares read from Qdrant
read-only (CrPC 742, IPC 595, BNS 424, CPA 138 of 1,899). Recorded 70.4% /
39.1% / 1.8x; recomputed 70.23% / 39.07% / **1.7974x**.

**But the recorded figure was a `filtered_n` number quoted with no stage.** At
`raw_15` the same queries give 1.49x. Both exceed chance; the magnitudes differ
by a third. Every future quotation must carry its stage.

**NEW: the adaptive score filter is a bias amplifier.** raw_15 -> filtered_n:
CrPC 1.49x -> 1.80x, IPC 0.59x -> 0.48x, BNS 0.58x -> **0.34x**. A step whose
purpose is removing noise is preferentially deleting substantive criminal law.
Nobody was looking for this.

4x4 layman routing confusion at `raw_15`, "went to" = dominant corpus among
retrieved chunks, 0 ties:

| gold / got | IPC | BNS | CrPC | CPA | n | accuracy |
|---|---|---|---|---|---|---|
| IPC | 3 | 2 | 17 | 1 | 23 | 13.0% |
| BNS | 3 | 1 | 18 | 1 | 23 | **4.3%** |
| CrPC | 0 | 0 | 5 | 0 | 5 | 100% |
| CPA | 0 | 0 | 0 | 8 | 8 | 100% |

35 of 46 substantive-law queries land in the procedure code. **BNS — the
criminal code currently in force — is the worst-routed book in the system.**

The paired 2x2 on `paired_recodification` returns 33/33 and 33/33 at every
stage. Not a result: the corpus filter fired IPC on all 33 IPC-named and BNS on
all 33 BNS-named queries, so the diagonal was guaranteed before an embedding was
compared. Usable only as the contrast to the filter-off condition, where BNS
falls 100% -> 51.5%. Labelled `filter_as_recorded` throughout.

**61 of 120 layman queries are structurally unanswerable**: 56 state no date
(either code could be correct, no single right column) and 5 require the BNSS,
which is not in the index. Belongs in Limitations as a corpus-coverage claim.

All 4 CPA misroutes are ONE situation (`pair_id=L024`, builder took 18 lakh,
gold is criminal cheating). One clustered mistake counting four times.

S2 paired check agreed to one chunk in 608. Traced: query L0089, replay and
original differ in the FIFTH decimal of a cosine score (0.259167 vs 0.259176),
flipping the third slot of the >=3-forced-through rule between a CPA chunk at
0.2489 and a CrPC chunk at 0.2491. Reported, not smoothed.

### S1 — retrieval metrics

Recall@15, `retrieved@k`, Wilson intervals:

| set | n | raw_15 | filtered_n |
|---|---|---|---|
| generated | 198 | 0.692 [0.624, 0.752] | 0.677 |
| paired | 99 | 0.737 [0.643, 0.814] | 0.707 |
| paired_dated | 197 | 0.492 [0.423, 0.562] | 0.452 |
| layman | 120 | 0.150 [0.097, 0.225] | 0.075 [0.040, 0.136] |
| ALL | 617 | 0.530 [0.491, 0.569] | 0.493 |

Paired check reproduced both gate anchors (9/120 and 327/617) through a route
that does not import `metrics_lib` at all — its own parser, its own Wilson
algebra. 2,306 comparisons agree.

**DEFECT in `metrics_lib`: `ranked_sections()` compresses rank.** It drops
chunks with no `section_number`, so a gold chunk retrieved at position 5 is
reported at rank 3. Only 118 of 617 `raw_15` lists have a section number on all
15 chunks, so this is the common case. Identical at k=15 — which is why every
anchor held — but `layman` Recall@5 is 0.100 compressed vs 0.050 positional, a
factor of two. Neither convention is wrong; BOTH are in the CSV under distinct
metric names with the convention named in every row's `notes`.
S2, S3 and S4 all used k=15 or no k, so Wave 2 is unaffected.

**Gold is not always a single section: 525 single, 88 double, 4 triple.** The
pre-registered "single binary gold" assumption is false for 92 rows. It matters:
`paired_recodification` Recall@15 is 0.737 binary (found at least one) vs 0.616
fraction-of-gold (found all). Finding one side of an IPC-BNS pair is not finding
both. Both reported.

**Do not quote `paired_dated_conflict` = 0.492.** Those 197 rows are 99 baseline
plus 98 of the SAME queries under `intervention=both`. The pooled figure
averages **0.293 baseline and 0.694 intervention** — a large intervention effect
hiding inside a single number. Split rows are in the CSV.

**Reranking moves gold UP, not down**: pooled MRR 0.418 -> 0.467. We had assumed
reranking only scrambled score order. NOT CLAIMED — cluster intervals overlap;
flagged as needing a paired test.

Correction to the brief: with gold as a SECTION and retrieval returning CHUNKS,
P@k = R@k/k holds on 99.2-100% of the 525 single-gold rows and breaks on 4 where
the gold section spans two retrieved chunks. The nDCG identity was confirmed
exactly — 14 distinct reciprocal-rank values map one-to-one, zero violations.

### Corrections to the wave brief, from S5

- The 3 legacy `criminal_*` rows (Q001-Q003) are NOT excluded; they sit inside
  the 617 and share one `pair_id` (`P_murder`) spanning two query sets.
- Only 1 of the 4 unlabelled rows is a SMOKE row. G0107, G0190 and D0094 are
  real queries that lost their gold join.
- The dated set is 33 x 3 x 2 = 197 rows, not 30 x 4. "30 x 4" describes the
  LAYMAN set.
- `filter_applied is None` on **208** rows, not 210.

### Known limitation, disclosed rather than fixed

`load_logs()` deduplicates on `(query_id, intervention)` keeping the LAST
occurrence. In three cases the last occurrence has no gold label while an
earlier one did, so the labelled row is discarded: `('G0107','baseline')`,
`('G0190','baseline')`, `('D0094','both')`. **n is 617 where it could be 620** —
0.5%, and S4 verified it moves no conclusion.

Deliberately NOT fixed now. Changing the loader would shift every number in six
CSVs by a fraction of a percent and invalidate five carefully written
explanation blocks that all quote n=617. The cost of that churn exceeds the
value of 3 rows. Disclosed here with exact identifiers, and to be revisited at
Wave 4 as a single decision rather than mid-wave.

### Resolved, so nobody re-litigates it

The `cited` positive count has THREE legitimate values on the same 617 rows:
- **533** — `correctness_label(..., "cited")`, reading the LOGGED
  `verifier.cited`, produced by the PRE-fix citation parser. S3 and S4 both
  report this.
- **538** — the answers RE-PARSED with the Wave 1 S3 post-fix parser. The GATE
  reports this, labelled.
- **587** — lenient matching, where a subsection matches its parent section.
Three routes, three correct answers to three different questions. Any figure
quoted must name its route.

### Not measured, with reasons

- Significance test that the CrPC over-representation ratio DIFFERS between
  `raw_15` and `filtered_n`. The correct instrument is a paired bootstrap on a
  share difference; `metrics_lib` exposes only the AUROC version. S2 stopped
  rather than reimplement a metric. The two intervals are reported separately
  and no difference claim is made.
- CIs on AURC and coverage-at-risk, and CIs on Platt pre/post — need a nested
  bootstrap, roughly 10x runtime.
- Calibration at `reranked_15` and `filtered_n`; per-query-set calibration CIs.
- Layman under `exclude_entity_default_used` — all 120 layman rows use the
  neutral default, so the restriction empties the set.
- `raw_15` has no second source for S2's paired check: the original logs stored
  only post-filter survivors. Stated as NOT CHECKABLE.

### Next

Wave 3 — two experiments. `statute_consistency` (the fourth confidence signal,
specified and never built) and BM25 plus hybrid retrieval. `rank_bm25` is NOT
installed and must not be installed without a decision, since a previous install
into this venv upgraded starlette and broke fastapi.

---

## 2026-09-01 — Wave 3: BM25 inverts the failure, and a gold-reachability ceiling

Branch `metrics/sept-01`. Two subagents concurrent, one owner per file, neither
ran git, both imported `experiments/metrics_lib.py`. Eight result CSVs now share
the exact long-format schema: **2,727 rows**. Suite 237 passing.

Cost: **13,375 embedding tokens, $0.000268, about 2 paise.** Zero generation
calls. Embeddings cached outside the repo, so re-runs are free.

### Environment change, approved by Udita and verified

`rank_bm25` 0.2.2 installed with `pip install rank_bm25 --no-deps`. The
`--no-deps` flag prevents pip from upgrading or touching any other package, so
it cannot repeat the earlier starlette/fastapi breakage. Verified by diffing
`pip freeze` before and after: **154 -> 155 packages, exactly one line added**
(`rank-bm25==0.2.2`). fastapi 0.115.0 and starlette 0.38.6 unmoved, `import app`
succeeds, 237 tests pass.

### S2 — BM25 AND HYBRID. The sharpest reviewer objection, answered.

The objection: *an exact-word search would separate IPC 420 from BNS 318
trivially, so the failure is an artefact of choosing a dense retriever.*

66 numbered paired queries, corpus filter DISABLED, dominant corpus among top 15:

| Query names | dense | bm25 | hybrid RRF | chance |
|---|---|---|---|---|
| **IPC** | **97.0%** [84.7, 99.5] | **0.0%** [0.0, 10.4] | 45.5% [29.8, 62.0] | 31.3% |
| **BNS** | 51.5% [35.2, 67.5] | **97.0%** [84.7, 99.5] | 78.8% [62.2, 89.3] | 22.3% |

Top-1: IPC dense 90.9% / bm25 45.5% / hybrid 87.9%. BNS dense 42.4% /
bm25 84.8% / hybrid 66.7%.

**BM25 does not fix the failure. It INVERTS it.** BNS-named accuracy moves off
51.5% — UP by 45.5 points to 97.0%, intervals non-overlapping — while IPC-named
collapses 97.0% -> 0.0%, below chance, all 33 landing in the CrPC. The two
retrievers fail on opposite halves of the same 66 queries.

**MECHANISM, MEASURED NOT INFERRED.** `sanhita` occurs in 30 chunks, all BNS,
idf 4.12 — the 2023 BNS names itself in its operative text. `penal` occurs in
82 CrPC chunks against 23 IPC, idf 2.79 — the 1860 IPC never names itself, so
"Indian Penal Code" is lexically a *CrPC* phrase, appearing there only as
cross-references.

**The IPC cannot be found by its own name in this corpus.** That is a property
of statutory drafting and statute age, not of any retriever, and it is the
paper's real contribution.

**Fusion made it worse.** Reciprocal Rank Fusion (Cormack, Clarke and Buttcher,
SIGIR 2009, k=60) scores 62.1% pooled against dense 74.2%, and Recall@15 0.531
against dense 0.558. Averaging two complementary failure modes produces a system
that fails at both. No reweighting of these two signals fixes both halves —
independent support for an explicit statute-and-date resolution layer, i.e. for
the Phase H mapper.

Recall@15 per set (binary, compressed convention), n=518 unique queries:

| set | n | dense | bm25 | hybrid |
|---|---|---|---|---|
| generated | 200 | 0.645 | 0.635 | 0.650 |
| paired_recodification | 99 | **0.737** | 0.576 | 0.717 |
| paired_dated_conflict | 99 | **0.697** | 0.434 | 0.616 |
| layman | 120 | **0.150** | 0.025 | 0.108 |
| ALL | 518 | **0.558** [0.515, 0.600] | 0.444 | 0.531 |

Pooled MRR@15: dense 0.4245, bm25 0.2967, hybrid 0.4059. nDCG@15: 0.4564 /
0.3319 / 0.4362.

Tokenisation rule (the crux — a tokeniser that strips numerals destroys the only
signal BM25 has here): lowercase, normalise unicode dashes and quotes, scan
`\d+[a-z]{0,2}(?:\([0-9a-z]+\))*|[a-z]+`, then expand each numeric to its
statutory ancestors. `318(4)` -> `318(4), 318`; `304b` -> `304b, 304`;
`498a(1)(b)` -> `498a(1)(b), 498a(1), 498a, 498`. Expansion is required because
headings are bare (`Section 318.`) while queries cite subsections; applied
identically to documents and queries so matching stays symmetric. The bare
subsection digit is deliberately NOT emitted — near-zero idf, no recall gained,
noise in length normalisation. Index: 1,899 documents, 6,355 distinct tokens,
mean 156.3 tokens per chunk.

### NEW AND IMPORTANT — the gold-reachability ceiling

**22 of the 33 BNS-named gold labels name subsections (`BNS 318(4)`) that the
index records only as bare sections (`318`).** Under strict `same_section` those
are unreachable by ANY retriever.

| Set | Ceiling |
|---|---|
| **BNS-named** | **11/33 = 0.333** |
| paired_recodification | 75/99 |
| paired_dated_conflict | 73/99 |
| layman | 96/120 |
| **pooled** | **444/518 = 0.857** |

Gold-section recall on BNS-named: dense 11/33 and hybrid 11/33 — **both
saturate the ceiling exactly**; bm25 10/33. On the reachable subset, dense
retrieval is perfect.

**CORRECTION TO A NUMBER I PUBLISHED AT THE GATE.** I reported BNS-named gold
recall of 11/33 = 33.3% and presented it as a retrieval failure. **It is the
ceiling, not a failure.** Any recall figure on that subset must be quoted
against 0.333, not 1.0.

The two headline figures are UNAFFECTED: 97.0% and 51.5% measure which BOOK was
retrieved, not which section, so subsection granularity does not touch them.

Reported, not repaired — patching gold labels is forbidden on this project.
Pinned as invariant C6 in `check07`.

Honest caveat S2 raised itself: BM25's IPC 0.0% is a TAIL effect. On query P0001
it puts the correct IPC section at rank 1, but ranks 6-15 flood with CrPC
cross-references, so dominant-corpus scores it zero. Dominant-corpus is a coarse
instrument and must be quoted alongside top-1, where BM25 gets IPC 45.5%.

`paired_dated_conflict` is 99 queries here, not 197 rows: per `app.py` the
date/mapper intervention acts ONLY by rewriting `plan.target_corpora`, so with
the corpus filter disabled it is a no-op for retrieval.

**17 paired checks, all passing.** A second BM25 written from the Okapi formula
in plain Python reproduces 32/33 and 0/33 exactly. A second tokeniser built by
character scan rather than regex agrees on 52 real chunks. The dense arm
reproduces `ablate_filter.py`'s published 32/33, 17/33, 30/33, 14/33
query-for-query. RRF verified against a hand-computed toy worked out on paper
before the code was written; single-list RRF is the identity on all 66 real
dense lists.

Clustered CI collapsed on pooled-66 BM25 — [0.455, 0.500] against naive
[0.368, 0.603], design effect **0.19** — because BM25 scores exactly one of
every pair right, so every cluster contributes an identical 1/2. Expected, per
Wave 2's note on contrastive variants.

RRF margins can be minute: on P0002 the correct chunk won by 0.0000084.

### S1 — statute_consistency, the fourth confidence signal

Built as specified in `docs/TARGET_ARCHITECTURE.md` and never previously
implemented: the fraction of retrieved chunks whose `statute_code` lies in the
set implied by the query plus its date.

`retrieved@k` at `raw_15`, primary variant:

| Scope | n | AUROC | clustered CI | vs composite | vs max_score |
|---|---|---|---|---|---|
| **ALL** | 617 | **0.685** | [0.659, 0.709] | +0.021 p=0.50 | **-0.099** p=0.0002 |
| **paired_dated_conflict** | 197 | **0.830** | [0.797, 0.867] | **+0.359** p<1e-4 | **+0.174** p=0.0008 |
| layman | 120 | 0.566 | [0.474, 0.675] | -0.005 p=0.98 | +0.014 p=0.87 |
| generated | 198 | 0.500 | constant | -0.373 p<1e-4 | -0.380 p<1e-4 |
| paired_recodification | 99 | 0.500 | constant | +0.147 p=0.038 | -0.235 p=0.0002 |

`reranked_15` is identical to `raw_15` by construction — a fraction over a SET
ignores order. `filtered_n` pooled 0.658; dated 0.806.

Four-row ablation picture at `raw_15`, `retrieved@k`, n=617:
max_score 0.784 > top_k_mean 0.757 > **statute_consistency 0.685** >
composite 0.663 > entity_coverage 0.581 > deployed gap_term 0.270.
The five pre-existing rows reproduce `ablation.csv` to 0.00e+00.

**VERDICT: pooled, it does NOT beat the generic signals.** It ties the composite
(p=0.50) and loses to `max_score` (p=0.0002).

**Conditionally, it is the only signal that works.** On the 197 dated-conflict
queries the deployed composite is BELOW CHANCE at 0.471 and statute_consistency
reaches 0.830.

**And S1 diagnosed why it looks weaker than it is.** On 343 of 617 rows the
Qdrant corpus filter was derived from the SAME query-plus-date inputs, so the
signal cannot fail by construction — it is measuring the output of a mechanism
built from its own inputs. Variants restricted to deployed information alone are
CONSTANT at 1.0, AUROC 0.5, no information. The signal earns its keep only where
the filter follows the NAMED code while the DATE disagrees, which is exactly the
dated-conflict set.

**A confidence signal placed downstream of a filter built from the same inputs
is a tautology.** That is an architectural finding, and it belongs in the paper.

Worked example D0001: composite 0.7895 (logged HIGH), entity_coverage 1.0, all
15 retrieved chunks IPC, gold `BNS 190` never retrieved, and
statute_consistency **0.000**. One row that shows the whole argument.

ECE 0.319 pooled against composite 0.241 and max_score 0.127 — flagged in-file
as a category reading, since this is a consistency FRACTION, not a probability.

Oracle variant reaches only 0.704, a mere +0.019 over the deployable version, so
the gap is not an implementation shortfall.

### entity_coverage recomputed from the payload, and GAPS.md corrected

| | logged substring match | payload `section_number` |
|---|---|---|
| mean | 0.5778 | 0.5494 |
| AUROC pooled | 0.5806 | **0.6050** (paired +0.0245) |
| AUROC generated | 0.8799 | **0.9854** (paired **+0.1055**) |

18 of 617 rows change, all downward.

**Wave 2's correction is fully confirmed by an independent route.** Values take
only {0, 0.5, 1.0}; maximum is 1.0; there is no free 0.30 default (the neutral
constant is 0.5, contributing 0.5 x 0.30 = 0.15); pooled AUROC 0.580565; 43.27%
sit at the constant; 120 of 120 layman rows are exactly 0.500; recodification
0.385669. **`docs/GAPS.md` #1 and #2 describe PRE-FIX code and must be marked as
superseded.**

### The normaliser artefact rate — and why the scary number is not the story

3,302 rewrites; 100 sampled without replacement, `default_rng(20260901)`:

| Class | k/100 | 95% Wilson |
|---|---|---|
| genuine section heading | 36 | [0.273, 0.458] |
| contents/index row | 47 | [0.375, 0.567] |
| footnote, digits not a section at all | 17 | [0.109, 0.255] |
| **artefact, strict** | **64** | **[0.542, 0.727]** |

**But only 1 of those 64 survives into Qdrant.** `is_contents_entry()` and
`footnote_verdict()` catch 63. **Both numbers must be reported** — quoting 64%
alone badly overstates the harm.

**SURPRISE: the entity_coverage false matches are not normaliser artefacts at
all.** All 17 are statutory CROSS-REFERENCES. Example:
`Section 454. Appeal against orders under section 452 or section 453` matches a
query for s.452. The briefed hypothesis — page numbers and list items — is
WRONG. The cause is 160-year-old drafting convention.

### Paired checks

`check06` PASSED. Mean statute_consistency at `filtered_n` computed from the raw
`runs/*/queries.jsonl` `retrieval.chunks[*].corpus` field matches the
`stages.jsonl` replay to **0.000000 on every query set**. At chunk level, 6
differing chunks in 5,879 slots (0.102%, 5 rows), every `req_id` printed —
consistent with Wave 2's one-in-608 cosine-tie note, and the means are unchanged
because the differing chunks fall inside the same admissible set. The 3,302
population was re-derived by two further regex routes. exp04 AUROCs reproduce
exactly, pooled and per set.

`check06` failed twice before passing, both faults S1's own: a dedupe ordering
that differed from `load_logs()`, and a notes parser that let layman values
masquerade as pooled ones. Documented in its section 6. One reconstruction
mismatch remains, a single stale pre-`ENTITY_NEUTRAL` log row
(`req_id=40bd347de051`), named in the CSV. Nothing was tuned after seeing an
AUROC, so no train/test refit was required.

### Next

Wave 4 — assemble. Concatenate all eight CSVs into `results/RESULTS.md`, verify
every referenced path exists, confirm `results/EXPLAIN.md` carries one complete
block per output file, and list separately: every number that CHANGED from what
`README.md` publishes, every failed assertion, and everything that could not be
computed.

Carry into Wave 4 as explicit agenda items:
- the gold-reachability ceiling, and the correction to the gate's 33.3% figure
- `docs/GAPS.md` #1 and #2 describe pre-fix code and are superseded
- the three `cited` values (533 logged / 538 re-parsed / 587 lenient)
- the 3 dropped labelled rows, n=617 vs 620, disclosed not fixed
- `ranked_sections()` rank compression, which inflates every k<15 figure

---

## 2026-09-01 — Wave 4: assemble. The plan is complete.

Branch `metrics/sept-01`. Serial, no subagents, per `docs/PLAN.md` section 5.
Zero API calls, ₹0.

`results/RESULTS.md` — 3,386 lines, generated by
`experiments/assemble_results.py` from all eight result CSVs. **2,727 result
rows.**

Design decision worth recording: **nothing in RESULTS.md is retyped.** Every
headline table is built by FILTERING the CSVs on metric/definition/stage, so no
figure in the document can drift from the data that produced it. Full tables
follow each headline inside a collapsed block. Transcription was the one
remaining route by which a wrong number could enter, and it is now closed.

The three closing lists require judgement, so they are maintained by hand in
`results/_RESULTS_appendix.md` and appended verbatim. If that file is absent the
script writes "NOT WRITTEN" rather than generating them from memory — the plan
forbids writing them from memory and the code now enforces it.

### Verification ran BEFORE writing, and found real problems

Every referenced path exists. `results/EXPLAIN.md` was checked for one block per
output file with all eight headings.

**Three blocks appeared incomplete and none of them was.** All content was
present; three heading LEVELS were wrong:

- `# Robustness and clustering` was written at h1 instead of h2, so the whole
  block was being absorbed into the ablation block above it.
- `# statute_consistency` was at h1, and its eight headings at h2 instead of h3,
  so it appeared as eight separate top-level blocks.
- `Retrieval metrics` has a NINTH heading, "Paired check" — an extra, not a gap.

10 heading levels normalised. That is a formatting repair on content that
already existed, not writing from memory. After it: **12 blocks, every one
carrying its eight headings.** The `GATE smoke test` entry is a pointer; the
real three blocks with 24 headings live in `results/smoke_test.md`.

Final verification run: **0 problems.**

### The appendix — four lists

**A. Numbers that CHANGED from README.md** — 11 entries with old value, new
value and cause. Two are RETRACTIONS of claims I made:

- **A1** the "counting bug" never existed. Text-parsing recovered the section
  4,906 of 4,906 times, 0.0% error. Both 7.5% (`filtered_n`) and 15.0%
  (`raw_15`) were always correct; I had compared an unfiltered probe against a
  filtered figure.
- **A7** BNS-named gold recall of 33.3%, which I published at the GATE as a
  retrieval failure, **is the reachability ceiling**. 22 of 33 BNS gold labels
  name subsections the index stores only as bare sections. Dense and hybrid both
  score 11/33 — saturating it exactly.

Also recorded: **A2** the confidence formula in CLAUDE.md was wrong (the
deployed code inverts the gap term) — a documentation error, not a code defect;
**A3** `GAPS.md` #1 and #2 describe pre-fix code; **A4** the README AUROC pair
0.610/0.663 records no definition and no stage and is superseded, not
reconcilable; **A8** `paired_dated_conflict` 0.492 averages two different
systems and must never be quoted.

**Numbers that did NOT change, which is itself the result:** 97.0% [84.7, 99.5]
and 51.5% [35.2, 67.5], reproduced cell-for-cell after three bug fixes, a new
metric library and a fresh run against the live index.

**B. Assertions that FAILED** — 10 entries. Two were defects in this project's
own measurement code, both caught by the gate, and both would have produced
believable wrong numbers:

- **B2** `same_section` raised on Constitution Articles and CPC Orders/Rules.
- **B3** the fix for B2 made `normalise_section` non-idempotent and silently
  zeroed every retrieval metric — 0 of 617, nothing crashed, every number looked
  plausible.

**B5** is left DELIBERATELY FAILING and documented: four clustered AUROC
intervals narrower than naive, unexplained after ruling out resampler bugs and
Monte Carlo noise across five seeds. Those two restricted subsets are marked
unusable rather than explained away.

**C. Could not be computed** — 13 entries with reasons, including the 3 dropped
labelled rows (n=617 vs 620), the absent BNSS, the 56 layman queries with no
single admissible answer, and the missing legal-expert validation.

**D. Caveats that must travel with any quoted figure** — 8 entries, including
the `k<15` rank compression, the three legitimate `cited` values (533 logged /
538 re-parsed / 587 lenient), multi-section gold, and the fact that the
recodification gap is a RETRIEVAL claim that does not survive at citation level.

### Status at the end of the plan

| | |
|---|---|
| Waves complete | 0, 1, 2, 3, 4, plus the gate |
| Result rows | 2,727 across 8 CSVs, one shared schema |
| `results/EXPLAIN.md` | 12 blocks, eight headings each |
| `results/RESULTS.md` | 3,386 lines, fully regenerable |
| Tests | 237 passing (`pytest tests/ -q`) |
| Total API spend today | about ₹0.09 |
| Environment | `rank_bm25` added with `--no-deps`; fastapi and starlette unmoved |

### Next — not code

The plan is finished. What remains is judgement, and it is Udita's:

1. **Ask Prof. Joshi for a law student to validate ~30 queries and their gold
   labels.** Every credible paper in this field has expert validation; almost no
   Indian system paper does. It is the cheapest remaining differentiator and it
   costs one email.
2. **Decide the framing.** Wave 3 argues for: *neither dense nor lexical
   retrieval routes reliably across a recodification boundary, and fusing them
   does not help, because the two failures have different causes — semantic
   near-identity one way, asymmetric statutory self-naming the other. The task
   needs an explicit statute-and-date resolution layer.*
3. **Decide whether to fix the gold subsection labels.** The ceiling is a real
   constraint on every recall figure. Fixing it means re-deriving gold, which is
   data work and must be done deliberately, not quietly.
