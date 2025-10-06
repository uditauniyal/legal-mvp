# Legal MVP — Retrieval-Augmented Legal Q&A (FastAPI · Qdrant · OpenAI · Streamlit)

> A production-minded, monolithic **RAG backend** for Indian law with a clean **FastAPI** service, **Qdrant** vector store, and a minimal **Streamlit** UI.
> Upload PDFs/DOCX/TXT → Ingest → Ask questions → Get **grounded** answers with **citations**.

---

## ✨ Highlights

* **End-to-end RAG**: OCR + chunking → embeddings → vector search → LLM synthesis (JSON-only)
* **Grounded answers**: Every claim is supported with numbered **[n]** markers and **citations** (doc, page, snippet)
* **Monolith simplicity**: One FastAPI app; Qdrant via Docker; OpenAI API for embeddings & generation
* **Decision Agent**: Simple rules to **filter by corpus** (e.g., BNS/BNSS/BSA/Constitution/Judgments vs CPA/CrPC) and add **section boosters**
* **Streamlit UI**: Modern, mobile-friendly demo app with upload/ingest, settings, answer cards, expander for citations, raw JSON toggle
* **Windows-friendly**: Byte-based ingest (no `/tmp`), OCR guarded, robust logging/diagnostics

---

## 🧭 Table of Contents

* [Architecture](#-architecture)
* [Directory Layout](#-directory-layout)
* [Prerequisites](#-prerequisites)
* [Quickstart](#-quickstart)
* [Configuration](#-configuration)
* [Run Services](#-run-services)
* [API Reference](#-api-reference)
* [Streamlit UI](#-streamlit-ui)
* [Ingestion Tips](#-ingestion-tips)
* [Decision Agent](#-decision-agent)
* [Evaluation (Accuracy & Latency)](#-evaluation-accuracy--latency)
* [Troubleshooting](#-troubleshooting)
* [Roadmap](#-roadmap)
* [License](#-license)

---

## 🏗 Architecture

```mermaid
flowchart TD
  U[User] -->|query JSON| API[FastAPI /query]
  subgraph Monolith
    API --> DEC[Decision Agent\n(corpus filter + section booster)]
    DEC --> EMB[Embedding Agent\n(text-embedding-3-small)]
    EMB -->|q_vec| RET[Retriever\nQdrant search k=24]
    RET --> MMR[MMR + Dedupe]
    MMR --> PACK[Evidence Packer\n[1]..[k] snippets]
    PACK --> LLM[Answer Synthesizer\ngpt-4o-mini (JSON-only)]
    LLM --> VAL[JSON Validator\n(repair once if needed)]
  end
  subgraph Vector DB
    QD[Qdrant (1536-d cosine)]
  end
  RET <-->|vectors| QD
  subgraph Ingestion
    UPLOAD[(PDF/DOCX/TXT)]
    UPLOAD --> EX[Extract+OCR (bytes)]
    EX --> CH[Chunker\n350–500 tokens + overlap]
    CH --> IE[Indexer\nOpenAI embed + Qdrant upsert]
    IE --> QD
  end
  VAL -->|{query, answer, citations[]}| U
```

**Key points**

* **Ingestion**: PDF/DOCX/TXT → **bytes-based extract** (OCR if needed) → **chunk** → **embed** → **upsert**
* **Query**: Decision Agent applies **corpus filter** / **section booster** → retrieve (k=24) → MMR to top 6–8 → LLM → **strict JSON**

---

## 📁 Directory Layout

```
legal-mvp/
├─ app.py                      # FastAPI app (ingest/query/health/diag)
├─ core/
│  ├─ config.py                # env vars, models, flags
│  └─ logging.py               # tolerant logging (req_id safe)
├─ clients/
│  ├─ openai_client.py         # embeddings + chat JSON wrapper
│  └─ qdrant_client.py         # collection create/upsert/search helpers
├─ ingest/
│  ├─ extract.py               # PDF/DOCX/TXT extract (bytes), OCR guarded
│  ├─ chunk.py                 # 350–500 token chunks, overlap, metadata
│  └─ index.py                 # batch embed + Qdrant upsert
├─ retrieve/
│  ├─ decision.py              # corpus filter + section booster + cues
│  ├─ search.py                # Qdrant similarity (cosine)
│  ├─ mmr.py                   # MMR diversify + dedupe
│  └─ pack.py                  # numbered snippets [1]..[k]
├─ answer/
│  ├─ prompt.py                # strict system + templated user prompt
│  ├─ llm.py                   # gpt-4o-mini, temperature=0, JSON format
│  └─ validate.py              # parse/repair into valid JSON
├─ report/
│  ├─ render.py                # optional HTML report (Jinja2)
│  └─ templates/answer.html.j2
├─ streamlit_app.py            # modern demo UI (upload + query)
├─ tests/, scripts/            # smoke_ingest.sh, smoke_query.sh etc.
├─ docker-compose.yml          # Qdrant @ 6333
├─ requirements.txt
└─ .env.example
```

---

## ✅ Prerequisites

* **Python 3.10+** (virtualenv recommended)
* **Docker** & **Docker Compose** (for Qdrant)
* **OpenAI API key** (for embeddings + generation)
* (Optional) **Tesseract** for OCR on scanned PDFs

  * Windows: `choco install tesseract` (add to PATH)

---

## ⚡ Quickstart

```bash
# 1) Create venv & install deps
python -m venv venv
source venv/bin/activate          # Windows: .\venv\Scripts\activate
pip install -r requirements.txt

# 2) Configure environment
cp .env.example .env
# edit .env and set:
# OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# 3) Start Qdrant
docker compose up -d

# 4) Run FastAPI
uvicorn app:app --host 127.0.0.1 --port 8000 --log-level info

# 5) (Optional) Run Streamlit UI in another terminal
streamlit run streamlit_app.py
```

Visit:

* API Health: [http://127.0.0.1:8000/healthz](http://127.0.0.1:8000/healthz)
* Streamlit UI: [http://localhost:8501](http://localhost:8501)

---

## 🔧 Configuration

`.env` (typical)

```
OPENAI_API_KEY=sk-...
EMBED_MODEL=text-embedding-3-small
GEN_MODEL=gpt-4o-mini
QDRANT_URL=http://localhost:6333
TOP_K=8
USE_TRANSLATION=false
LANGS_OCR=eng+hin+tam+tel
```

> **Load order**: The app loads `.env` **at startup** (top of `app.py`) so keys are available before any clients initialize.

---

## ▶ Run Services

**Qdrant**

```bash
docker compose up -d
```

**FastAPI (no reload flapping)**

```bash
uvicorn app:app --host 127.0.0.1 --port 8000 --log-level info
```

**Streamlit**

```bash
streamlit run streamlit_app.py
```

---

## 🔌 API Reference

### `POST /ingest`

Upload one or more documents (`PDF`, `DOCX`, `TXT`) and index them.

**Request (multipart/form-data)**

```
files: <file>
files: <file>
...
```

**Response (JSON)**

```json
{
  "files_received": 3,
  "chunks_indexed": 128,
  "errors": []
}
```

> **Windows tip**: If `curl` on Git Bash fails with `(26)`, use PowerShell’s `curl.exe` or the Streamlit uploader.

---

### `POST /query`

Ask a question; get **strict JSON** with answer + citations.

**Request**

```json
{"query":"What actions can the District Commission take for a defective product?"}
```

**Response**

```json
{
  "query": "...",
  "answer": "… include inline markers like [1][2] …",
  "citations": [
    {"source":"a2019-35.pdf", "page":20, "snippet":"…"},
    {"source":"a2019-35.pdf", "page":7,  "snippet":"…"}
  ]
}
```

> Add `?format=html` to receive a pre-rendered HTML report (downloadable via the UI).

---

### `GET /healthz`

Health probe → `{"ok": true}`

### `GET /diag/env` (optional helper)

Diagnostic (returns whether OpenAI key is set)
→ `{"openai_key_set": true}`

---

## 🖥 Streamlit UI

* **Sidebar**

  * Backend URL, **Answer style** (Detailed/Summary)
  * **Show raw JSON** toggle
  * **Upload & Ingest** (PDF/DOCX/TXT)
  * Clear history

* **Main**

  * Big emoji heading
  * Text area for question
  * Answer card with soft shadow; inline **[n]** superscripts
  * **Citations** in collapsible expander
  * Optional **Download HTML report**
  * Recent **History** cards

> Mobile-friendly layout, professional blue/grey/white palette.

---

## 📥 Ingestion Tips

* **OCR** is guarded: if Tesseract not found, text-PDFs still ingest; scanned pages are skipped (no 500s).
* Prefer **clean statute PDFs** over scanned; use 300 DPI if OCRing.
* Chunk target **350–500 tokens** with 1–2 sentence overlap; include metadata:
  `doc_name, page, chunk_id (uuid), chunk_index, corpus, lang_detected, text`

---

## 🧠 Decision Agent

A tiny rules layer that boosts retrieval quality without extra model calls.

* **Corpus filter**: Map keywords to corpora (`BNS/BNSS/BSA/Constitution/Judgments` or `CPA/CrPC`)
* **Section booster**: If a query mentions **§82 proclamation**, also boost **§83 attachment**; **§125** → **maintenance**; **§21 misleading ads** → CPA filters
* **Query rewrite**: Prepend boosters to the semantic query before embedding

  ```
  "Section 83 CrPC || " + original_query
  ```
* **De-prioritize forms/annexures** (optional): down-rank pages starting with “FORM No.” unless no statute body was retrieved

---

## 📊 Evaluation (Accuracy & Latency)

**Suggested protocol**

* 30–50 queries across your corpora (CPA, CrPC, etc.); 20% “trick” queries
* Gold answers + gold snippets (doc/page/lines)
* Metrics:

  * **Correctness** (% correct) & **Groundedness** (every claim cited)
  * **Citation accuracy** (citations truly support claims)
  * **Recall@k** & **MRR** (gold appears in top-k)
  * **Latency** p50/p95; token in/out (cost proxy)

**Quick tuning**

* Retrieve **k=24 → MMR → keep 6–8**
* Cap each snippet to **~400 chars**
* `temperature=0`, `max_tokens=500`, enforce `response_format={"type":"json_object"}`
* Cache embeddings for repeated queries
* Aim **≤3s p50 / ≤5s p95**

---

## 🛠 Troubleshooting

* **401 OpenAI / invalid key**

  * Ensure `.env` contains `OPENAI_API_KEY=sk-…`
  * Load `.env` **at the top of `app.py`** with `load_dotenv(..., override=True)`
  * Confirm via `GET /diag/env → {"openai_key_set": true}`

* **Logger KeyError: req_id**

  * Use tolerant formatter (adds `req_id="-"` when absent). See `core/logging.py`.

* **Git Bash `curl (26)`** (Windows path issues)

  * Use `curl.exe` (PowerShell) or Streamlit uploader; or `scripts/ingest_cli.py`

* **“Attachment after proclamation” mis-grounded to §421 (forms)**

  * Add **Section 83** booster; down-rank “FORM No.” pages; confirm statute body for §82–83 was OCR’d.

* **Time-outs from UI**

  * Increase Streamlit timeout (e.g., 120–180s) for heavy scans; shrink prompt/context server-side.

---

## 🗺 Roadmap

* **Corpus expansion**: BNS/BNSS/BSA (new codes), IPC §§141/415/503/320, HMA, Limitation Act
* **Judgment metadata**: parties, bench, year, citation fields in payload
* **RAG eval harness**: automatic correctness & groundedness scoring
* **Auth & quotas**: per-tenant API keys, rate limiting
* **Containerize app**: Dockerfile for FastAPI + Streamlit (compose with Qdrant)

---

## 📜 License

This repository is provided for educational/research use.
(Choose an appropriate license: MIT/Apache-2.0/BSD-3-Clause and add it to `LICENSE`.)

---

## 🙏 Acknowledgements

* **Qdrant** for vector search
* **FastAPI** + **Uvicorn** for a clean, fast Python web stack
* **Streamlit** for rapid demo UI
* **OpenAI** for embeddings and JSON-friendly chat completions

---

### One-liner to remember

> **Upload docs → Ingest → Ask → Get grounded answers with citations.**
> Legal MVP keeps things **simple, explainable, and fast**—perfect for demos, research, and the first production mile.
