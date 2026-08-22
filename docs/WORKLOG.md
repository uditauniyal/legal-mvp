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
