# Legal MVP — Glossary

Terms used across this documentation set, in two tables: **legal** and **technical**. Each entry says where it shows up in this codebase.

---

## Legal terms

### The statutory landscape

India replaced its three core criminal laws in 2023–24. Both the old and new versions matter here, because the corpus contains some of each.

| Old law (pre-2024) | New law (from 1 July 2024) | Covers |
|---|---|---|
| Indian Penal Code, 1860 (**IPC**) | Bharatiya Nyaya Sanhita, 2023 (**BNS**) | What counts as a crime, and the punishment |
| Code of Criminal Procedure, 1973 (**CrPC**) | Bharatiya Nagarik Suraksha Sanhita, 2023 (**BNSS**) | How the process works — arrest, bail, trial, appeal |
| Indian Evidence Act, 1872 (**IEA**) | Bharatiya Sakshya Adhiniyam, 2023 (**BSA**) | What can be proved in court, and how |

**The distinction that matters most in this system: penal vs procedural.**

- **Penal law** (IPC / BNS) defines *offences*. "Theft is…", "the punishment for murder shall be…"
- **Procedural law** (CrPC / BNSS) defines *process*. "A police officer may arrest without a warrant when…", "bail shall be granted if…"

Questions like *"can police arrest without a warrant?"*, *"where do I file an FIR?"*, or *"how do I get bail?"* are **procedural**. It is a common and consequential error to route them to the penal code — see [`DATAFLOW.md`](DATAFLOW.md) for exactly that happening.

| Term | Meaning | Where it appears here |
|---|---|---|
| **IPC** | Indian Penal Code, 1860. Repealed, but still governs offences committed before July 2024. | `tests/data/repealedfileopen.pdf`; `ACT_MAP` maps `"ipc" → "BNS"` |
| **BNS** | Bharatiya Nyaya Sanhita, 2023. The current penal code. | `tests/data/Bharatiya_Nyaya_Sanhita_2023.pdf`; a corpus tag |
| **CrPC** | Code of Criminal Procedure, 1973. | `tests/data/the_code_of_criminal_procedure,_1973.pdf` — tagged `BNSS` in this index |
| **BNSS** | Bharatiya Nagarik Suraksha Sanhita, 2023. Current procedural code. | A corpus tag. ⚠ No BNSS document is actually ingested; the `BNSS` tag holds CrPC 1973 |
| **BSA / IEA** | Evidence law, new and old. | A corpus tag with 7 spuriously-labelled chunks; no evidence-law document is ingested |
| **CPA** | Consumer Protection Act, 2019. Defective goods, deficient services, consumer commissions. | `tests/data/a2019-35.pdf` |
| **Constitution** | Constitution of India. Fundamental rights (Art. 14, 19, 21, 22), writs (Art. 32, 226). | A corpus tag with 3 spurious chunks; **no constitutional document is ingested** |

### Procedural vocabulary

| Term | Meaning | Relevance |
|---|---|---|
| **FIR** | First Information Report — the police record that starts a criminal investigation. | A paralegal-override trigger (`agents/intake.py`) |
| **Cognizable offence** | Police may arrest without a warrant and investigate without a magistrate's order. | Determines whether "police can act right now" is true |
| **Non-cognizable** | Police need a magistrate's permission to investigate. | Often the answer to "why won't they file my FIR?" |
| **Bailable / non-bailable** | Whether bail is a right or at the court's discretion. | A paralegal-override trigger |
| **Anticipatory bail** | Pre-arrest bail (CrPC §438 / BNSS §482). | The one query in the recorded test set that routed correctly |
| **Quashing** | Asking a High Court to cancel an FIR or proceeding (CrPC §482 / BNSS §528). | A paralegal-override trigger |
| **Writ petition** | Direct approach to a High Court (Art. 226) or Supreme Court (Art. 32) to enforce rights. | A paralegal-override trigger |
| **Cause of action** | The set of facts that entitles you to sue. | What Intake's `legal_issues` field tries to name |
| **Limitation period** | The deadline after which a claim can no longer be brought. | Appears in test queries; the Limitation Act is **not** in the corpus |
| **District / State / National Commission** | The three-tier consumer dispute forums under the CPA 2019. | Subject of several test queries |

---

## Technical terms

### Retrieval and embeddings

| Term | Meaning | Where |
|---|---|---|
| **Embedding** | A list of numbers representing text's meaning as a position in space. Here, 1536 numbers from `text-embedding-3-small`. Texts with similar meaning land near each other. | `clients/openai_client.py:6`; [`ARCHITECTURE.md` §2.2](ARCHITECTURE.md#22--what-an-embedding-actually-is) |
| **Dimension** | How many numbers per embedding. 1536 for `-small`, 3072 for `-large`. Hard-coded at `ensure_collection(dim=1536)` — changing models means rebuilding the collection. | `clients/qdrant_client.py:10` |
| **Cosine similarity** | The cosine of the angle between two vectors. 1.0 = same direction, 0 = unrelated, −1 = opposite. Length-independent, so a short question and a long passage compare fairly. | Configured as `Distance.COSINE`; [`ARCHITECTURE.md` §2.3](ARCHITECTURE.md#23--cosine-similarity-worked-by-hand) |
| **Score** | The cosine value on a search result (`hit.score`). In this corpus, useful hits sit at **0.35–0.55**, not the 0.8+ seen in general-domain RAG. Absolute values mean little; relative differences carry the signal. | `agents/retriever.py` |
| **Chunk** | A slice of a document small enough to embed meaningfully and cite precisely. Here ~450 tokens with one sentence of overlap. | `ingest/chunk.py:6` |
| **Token** | Roughly ¾ of an English word. This codebase approximates it as whitespace-separated word count. | `ingest/chunk.py:13` |
| **Overlap** | Repeating the tail of one chunk at the head of the next, so provisions straddling a boundary appear intact somewhere. | `overlap_sentences=1` |
| **Corpus** | A label grouping chunks by source law (`BNS`, `BNSS`, `BSA`, `Constitution`, `Judgments`, `Unknown`). Assigned at ingest, filtered on at query time. | `ingest/chunk.py:47`; `agents/router.py` |
| **Payload** | Metadata stored beside a vector — `doc_name`, `page`, `text`, `corpus`. Carries citations and enables filtering. | `ingest/index.py:24` |
| **Payload filter** | Restricting a search to a payload subset *before* similarity is computed. The single most consequential lever in this system: a wrong filter makes the right answer unreachable. | `agents/retriever.py:76-80` |
| **top-k** | How many results to return. `limit=15` here. | `agents/retriever.py:71` |
| **Reranking** | Reordering results after retrieval by some second criterion. Here: chunks containing an extracted entity are moved to the front, **independent of score**. | `agents/retriever.py:105-114` |
| **MMR** | Maximal Marginal Relevance — a reranking method trading relevance against diversity to avoid near-duplicate results. ⚠ Documented in `README.md` but **not implemented**; `retrieve/mmr.py` does not exist. | — |
| **Vector database** | A store that finds nearest neighbours in embedding space efficiently. Here: Qdrant. | `docker-compose.yml`; `qdrant_storage/` |
| **Collection** | Qdrant's unit of storage, like a table. One here: `legal_mvp`. | `clients/qdrant_client.py:5` |
| **Upsert** | Insert-or-update by id. Used at ingest so re-running doesn't duplicate. | `ingest/index.py:33` |

### Generation

| Term | Meaning | Where |
|---|---|---|
| **RAG** | Retrieval-Augmented Generation. Retrieve documents, then ask the model to answer using them, rather than from memory alone. | The whole system |
| **Grounding** | Every claim traceable to retrieved text. RAG's central promise. ⚠ **Requested via prompt, not enforced by any mechanism** — see [`DATAFLOW.md`](DATAFLOW.md) Step 8 | `agents/answer.py` |
| **Parametric knowledge** | What a model knows from training, as opposed to what it was given in the prompt. When retrieval fails, this is what fills the gap — fluently, and without announcing itself. | — |
| **Hallucination** | Fluent, confident, wrong output. In legal RAG specifically: citing provisions that were not retrieved, or do not exist. | The core phenomenon this project studies |
| **System prompt** | Standing instructions given to the model before the user's message. Here, tier-dependent. | `agents/answer.py:5-56` |
| **Temperature** | Randomness in generation. `0` = most deterministic. ⚠ Some newer model families reject any value other than the default — see [`OPEN_QUESTIONS.md`](OPEN_QUESTIONS.md) | `agents/answer.py:119` |
| **Refusal gate** | Declining to answer rather than guessing. Here it fires **only when zero chunks survive filtering** — not on low confidence. | `agents/answer.py:83` |

### Evaluation and research

These matter for the paper more than for the code.

| Term | Meaning | Why it matters here |
|---|---|---|
| **Calibration** | Whether stated confidence matches actual accuracy. A well-calibrated system that says "70%" is right about 70% of the time. | Prof. Joshi's item #3. Requires confidence to vary meaningfully — see [`GAPS.md`](GAPS.md) |
| **Reliability diagram** | Plot of predicted confidence (x) against observed accuracy (y). Perfect calibration is the diagonal. | The main calibration figure |
| **ECE** | Expected Calibration Error — average gap between confidence and accuracy across bins. One number summarising a reliability diagram. | Likely a headline metric |
| **Ablation** | Removing one component to measure its contribution. Here: drop each of the three confidence signals in turn. | Prof. Joshi's item #5 |
| **Baseline** | A simpler alternative you must beat, or at least measure against. E.g. dense retrieval with no routing, or the previous mean-of-15 confidence. | Prof. Joshi's item #5 |
| **Ground truth** | The known-correct answer, labelled in advance. Here: which statutory sections *should* have been retrieved. | Prof. Joshi's item #1 — cannot be inferred after the fact, must be annotated first |
| **Precision / Recall @ k** | Of the top-k retrieved, what fraction were relevant (precision); of all relevant chunks, what fraction were retrieved (recall). | Core retrieval metrics |
| **MRR** | Mean Reciprocal Rank — 1/(rank of the first correct result), averaged. Rewards putting the right answer near the top. | Standard retrieval metric |
| **Hybrid retrieval** | Combining dense (embedding) search with sparse (keyword/BM25) search. Catches exact section numbers that embeddings blur. | Prof. Joshi's item #4 |
| **Failure analysis** | Systematically categorising *how* a system fails, not just how often. | The likely core contribution of this paper |

---

## Project-specific vocabulary

Terms that mean something particular in this codebase.

| Term | Meaning here |
|---|---|
| **Agent** | A Python class with one method and one responsibility. **Not** an autonomous LLM agent — there is no tool use, no looping, no self-direction. Five agents run in a fixed line. |
| **`CaseContext`** | Intake's output. Triage metadata about the user's situation. Only `predicted_legal_domain` and `legal_issues` affect behaviour; the rest is displayed. |
| **`QueryPlan`** | Router's output. Which corpus, which entities, and the rewritten query for embedding. |
| **`RetrievalResult`** | Retriever's output. Chunks plus the confidence breakdown. |
| **Entity** | A statutory reference extracted by regex — `"Section 41"`, `"Article 226"`. Used for reranking and for confidence signal 3. |
| **Boost terms** | Text prepended to the query before embedding, to drag it toward statutory vocabulary. Affects the embedding only, not what the model is shown. |
| **Paralegal override** | A regex pass that forces `user_persona = "Paralegal"` when the query contains technical terms, overriding the LLM's classification. |
| **Paralegal Mode** | The Intake + Reporter additions — case triage plus a PDF advisory. |
| **Confidence tier** | HIGH (≥0.55) / MEDIUM (≥0.38) / LOW (<0.38). Selects which disclaimer is prepended to the system prompt. |
| **Adaptive threshold** | `max(top_score − 0.15, 0.35)`. Keeps chunks near the best one, with an absolute floor. |
| **Corpus tag** | The `corpus` payload value. Assigned by `guess_corpus()`, filtered on by the Router. These two must agree on vocabulary or filtering silently fails. |
