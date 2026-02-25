<p align="center">
  <h1 align="center">⚖️ Legal MVP</h1>
  <p align="center"><strong>Agentic RAG System for Indian Legal Q&A</strong></p>
  <p align="center">FastAPI · Qdrant · OpenAI · Streamlit · Multi-Agent Architecture</p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python" alt="Python"/>
  <img src="https://img.shields.io/badge/FastAPI-0.100+-green?logo=fastapi" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/Qdrant-Vector_DB-purple" alt="Qdrant"/>
  <img src="https://img.shields.io/badge/OpenAI-GPT--4o--mini-black?logo=openai" alt="OpenAI"/>
  <img src="https://img.shields.io/badge/Streamlit-UI-red?logo=streamlit" alt="Streamlit"/>
</p>

> A production-minded, multi-agent **Retrieval-Augmented Generation** system for Indian law. Upload legal documents → Ingest into vector store → Ask questions in natural language → Receive **grounded answers with inline citations**. Includes a full **Paralegal Mode** with case intake, intelligent routing, and automated report generation.

---

## Table of Contents

- [System Overview](#system-overview)
- [Architecture](#architecture)
  - [High-Level Architecture](#high-level-architecture)
  - [Dual Operating Modes](#dual-operating-modes)
- [Agent Deep Dive](#agent-deep-dive)
  - [Router Agent](#-router-agent)
  - [Retriever Agent](#-retriever-agent)
  - [Answer Agent](#-answer-agent)
  - [Intake Agent](#-intake-agent--paralegal-mode)
  - [Reporter Agent](#-reporter-agent--paralegal-mode)
- [Supporting Modules](#supporting-modules)
  - [Decision Engine](#decision-engine)
  - [MMR Diversifier](#mmr-diversifier)
  - [Evidence Packer](#evidence-packer)
  - [JSON Validator](#json-validator)
- [Ingestion Pipeline](#ingestion-pipeline)
- [Data Flow & Sequence Diagrams](#data-flow--sequence-diagrams)
- [Directory Layout](#directory-layout)
- [Prerequisites](#prerequisites)
- [Quickstart](#quickstart)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Streamlit UI](#streamlit-ui)
- [Evaluation Protocol](#evaluation-protocol)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)
- [License](#license)
- [Acknowledgements](#acknowledgements)

---

## System Overview

Legal MVP is built around a **five-agent architecture** that orchestrates the entire lifecycle of legal question-answering — from case intake to cited report generation. The system operates in two modes:

| Mode | Agents Involved | Use Case |
|------|----------------|----------|
| **Standard Q&A** | Router → Retriever → Answer | Direct legal questions with cited responses |
| **Paralegal Mode** | Intake → Router → Retriever → Answer → Reporter | Full case workflow: intake, research, analysis, and report |

**Key capabilities:**

- **Grounded answers** — Every claim backed by numbered `[n]` citations with source document, page, and snippet
- **Agentic routing** — Intelligent classification of queries to the right legal corpus and retrieval strategy
- **Paralegal automation** — Structured case intake, intelligent evidence gathering, and professional report generation
- **Indian law focus** — Covers BNS, BNSS, BSA, CPA, CrPC, Constitution, and judicial precedents
- **Production-ready** — FastAPI backend, Docker-based vector DB, Windows-compatible, robust error handling

---

## Architecture

### High-Level Architecture

```mermaid
flowchart TD
    subgraph UI["🧑 Interface Layer"]
        USER["👤 User"]
        STUI["🖥️ Streamlit UI<br/><i>streamlit_app.py</i>"]
        CURL["⌨️ cURL / HTTP Client"]
    end

    subgraph API["🌐 API Gateway"]
        FA["⚡ FastAPI Server<br/><i>app.py</i>"]
    end

    subgraph Agents["🤖 Agent Layer — agents/"]
        direction TB
        INTAKE["📝 Intake Agent<br/><i>agents/intake.py</i>"]
        ROUTER["🧭 Router Agent<br/><i>agents/router.py</i>"]
        RETRIEVER["🎯 Retriever Agent<br/><i>agents/retriever.py</i>"]
        ANSWER["💬 Answer Agent<br/><i>agents/answer.py</i>"]
        REPORTER["📊 Reporter Agent<br/><i>agents/reporter.py</i>"]
    end

    subgraph Retrieval["🔍 Retrieval Engine — retrieve/"]
        DEC["🧠 Decision Engine<br/><i>retrieve/decision.py</i>"]
        SEARCH["🔎 Vector Search<br/><i>retrieve/search.py</i>"]
        MMR["🔀 MMR Diversifier<br/><i>retrieve/mmr.py</i>"]
        PACK["📋 Evidence Packer<br/><i>retrieve/pack.py</i>"]
    end

    subgraph AnswerGen["✍️ Answer Generation — answer/"]
        PROMPT["📜 Prompt Builder<br/><i>answer/prompt.py</i>"]
        LLM["🤖 LLM Synthesizer<br/><i>answer/llm.py</i>"]
        VALID["✅ JSON Validator<br/><i>answer/validate.py</i>"]
    end

    subgraph Ingest["📥 Ingestion Pipeline — ingest/"]
        EXT["🔍 Extractor<br/><i>ingest/extract.py</i>"]
        CHK["✂️ Chunker<br/><i>ingest/chunk.py</i>"]
        IDX["📦 Indexer<br/><i>ingest/index.py</i>"]
    end

    subgraph Infra["🗄️ Infrastructure"]
        QD[("🔷 Qdrant<br/>1536-d Cosine<br/>Docker :6333")]
        OAI["🤖 OpenAI API<br/>Embeddings + Chat"]
    end

    subgraph Core["⚙️ Core — core/ + clients/"]
        CFG["📝 Config<br/><i>core/config.py</i>"]
        LOG["📊 Logger<br/><i>core/logging.py</i>"]
        OC["OpenAI Client<br/><i>clients/openai_client.py</i>"]
        QC["Qdrant Client<br/><i>clients/qdrant_client.py</i>"]
    end

    USER --> STUI & CURL
    STUI & CURL --> FA

    FA -->|"POST /query"| ROUTER
    FA -->|"Paralegal Mode"| INTAKE
    FA -->|"POST /ingest"| EXT

    INTAKE -->|"structured case"| ROUTER
    ROUTER -->|"classified query"| RETRIEVER
    RETRIEVER --> DEC --> SEARCH --> MMR --> PACK
    RETRIEVER -->|"evidence"| ANSWER
    ANSWER --> PROMPT --> LLM --> VALID
    ANSWER -->|"cited answer"| REPORTER
    REPORTER -->|"final report"| FA

    EXT --> CHK --> IDX

    SEARCH <--> QD
    IDX --> QD
    LLM <--> OAI
    IDX <--> OAI

    Core -.-> Agents
    Core -.-> Retrieval
    Core -.-> AnswerGen
    Core -.-> Ingest

    style UI fill:#e8f4f8,stroke:#2196F3
    style API fill:#fff3e0,stroke:#FF9800
    style Agents fill:#fce4ec,stroke:#E91E63
    style Retrieval fill:#e8f5e9,stroke:#4CAF50
    style AnswerGen fill:#f3e5f5,stroke:#9C27B0
    style Ingest fill:#e0f2f1,stroke:#009688
    style Infra fill:#ede7f6,stroke:#673AB7
    style Core fill:#f5f5f5,stroke:#9E9E9E
```

---

### Dual Operating Modes

The system operates in two distinct modes, each using a different subset of agents:

```mermaid
flowchart LR
    subgraph Mode1["⚡ Mode 1: Standard Q&A"]
        direction LR
        Q1["❓ Query"] --> R1["🧭 Router"] --> RET1["🎯 Retriever"] --> A1["💬 Answer"]
        A1 --> OUT1["📨 JSON Response<br/>{query, answer, citations}"]
    end

    subgraph Mode2["📋 Mode 2: Paralegal Mode"]
        direction LR
        C2["📝 Case Details"] --> I2["📝 Intake"] --> R2["🧭 Router"]
        R2 --> RET2["🎯 Retriever"] --> A2["💬 Answer"]
        A2 --> REP2["📊 Reporter"]
        REP2 --> OUT2["📄 Case Report<br/>+ Dashboard"]
    end

    style Mode1 fill:#e8f5e9,stroke:#4CAF50
    style Mode2 fill:#fff3e0,stroke:#FF9800
```

| Feature | Standard Q&A | Paralegal Mode |
|---------|-------------|----------------|
| **Entry point** | Direct question | Structured case intake |
| **Agents used** | 3 (Router → Retriever → Answer) | 5 (all agents) |
| **Output** | JSON with answer + citations | Full case report + dashboard |
| **Best for** | Quick legal queries | Comprehensive case analysis |
| **Interaction** | Single-turn | Multi-turn with structured input |

---

## Agent Deep Dive

The five agents in `agents/` form the backbone of the system. Each agent is a specialized module with a distinct role in the legal Q&A pipeline.

### 🧭 Router Agent

**File:** `agents/router.py`

The Router Agent is the **orchestrator** and entry point for all queries. It classifies the incoming query, determines which legal corpus to target, applies section-specific boosting rules, and routes the request to the Retriever Agent with the appropriate configuration.

```mermaid
flowchart TD
    Q["Incoming Query"] --> CLASSIFY{"Classify<br/>Query Type"}

    CLASSIFY -->|"Statutory Question"| CORPUS["Identify Target Corpus"]
    CLASSIFY -->|"Case Law Question"| JUDG["Route to Judgments"]
    CLASSIFY -->|"Cross-cutting"| MULTI["Multi-corpus Search"]

    CORPUS --> BOOST{"Section Boosting<br/>Rules"}
    JUDG --> BOOST
    MULTI --> BOOST

    BOOST -->|"§82 → add §83"| REWRITE["Query Rewriting"]
    BOOST -->|"§125 → maintenance"| REWRITE
    BOOST -->|"§21 → CPA filter"| REWRITE
    BOOST -->|"No match"| DIRECT["Pass Through"]

    REWRITE --> RET["🎯 Retriever Agent"]
    DIRECT --> RET

    style CLASSIFY fill:#fff9c4,stroke:#F9A825
    style BOOST fill:#e1f5fe,stroke:#0288D1
```

**Responsibilities:**

- **Query classification** — Determines if the query is statutory, case-law, procedural, or cross-cutting
- **Corpus routing** — Maps query keywords to specific legal corpora (BNS/BNSS/BSA, CPA, CrPC, Constitution, Judgments)
- **Section boosting** — Injects related sections for companion provisions (e.g., §82 proclamation → also boost §83 attachment)
- **Query rewriting** — Prepends boosted terms to improve semantic retrieval

**Boosting rules:**

| Detected Pattern | Injected Boost | Reason |
|-----------------|----------------|--------|
| §82 (proclamation) | §83 (attachment of property) | Companion provisions always read together |
| §125 | "maintenance" context | Enriches semantic search for family law |
| §21 (misleading ads) | CPA corpus filter | Routes to Consumer Protection Act |
| Forms/Annexures | De-prioritize FORM pages | Prefer substantive statute body text |

**Query rewrite example:**

```
Input:  "What is the procedure under Section 83 CrPC?"
Output: "Section 83 CrPC attachment property || What is the procedure under Section 83 CrPC?"
```

---

### 🎯 Retriever Agent

**File:** `agents/retriever.py`

The Retriever Agent manages the entire evidence-gathering pipeline. It coordinates four sub-modules — Decision Engine, Vector Search, MMR Diversification, and Evidence Packing — to produce a curated, diverse, and numbered evidence block.

```mermaid
flowchart TD
    IN["Boosted Query<br/>+ Corpus Filters<br/><i>from Router Agent</i>"] --> EMBED

    subgraph RetrieverAgent["🎯 Retriever Agent Pipeline"]
        EMBED["🔢 Embed Query<br/><i>text-embedding-3-small</i><br/>→ 1536-d vector"]

        SEARCH["🔎 Vector Search<br/><i>retrieve/search.py</i><br/>Qdrant cosine · k=24"]

        MMR_S["🔀 MMR Diversify<br/><i>retrieve/mmr.py</i><br/>λ·relevance − (1−λ)·redundancy<br/>→ top 6–8 chunks"]

        DEDUP["🧹 Deduplication<br/>Remove near-identical<br/>snippets from same page"]

        PACK_S["📋 Evidence Packer<br/><i>retrieve/pack.py</i><br/>Numbered [1]..[k]<br/>~400 chars per snippet"]

        EMBED --> SEARCH --> MMR_S --> DEDUP --> PACK_S
    end

    PACK_S --> OUT["Evidence Block<br/>ready for Answer Agent"]

    QD[("🔷 Qdrant")] <-->|"similarity<br/>search"| SEARCH

    style RetrieverAgent fill:#e8f5e9,stroke:#4CAF50
```

**Stage-by-stage breakdown:**

| Stage | Module | Input | Output | Details |
|-------|--------|-------|--------|---------|
| **1. Embed** | `clients/openai_client.py` | Boosted query string | 1536-d vector | `text-embedding-3-small` model |
| **2. Search** | `retrieve/search.py` | Query vector + corpus filter | 24 candidate chunks | Qdrant cosine similarity |
| **3. MMR** | `retrieve/mmr.py` | 24 candidates | 6–8 diverse chunks | Maximal Marginal Relevance |
| **4. Dedupe** | `retrieve/mmr.py` | 6–8 chunks | Deduplicated set | Removes near-identical snippets |
| **5. Pack** | `retrieve/pack.py` | Diverse chunks | Numbered evidence block | `[1]` source, page, snippet format |

---

### 💬 Answer Agent

**File:** `agents/answer.py`

The Answer Agent synthesizes grounded legal answers from the evidence block. It constructs a strict prompt, calls the LLM with JSON-mode enforcement, and validates the output through a repair-capable JSON validator.

```mermaid
flowchart TD
    IN["Evidence Block [1]..[k]<br/>+ Original Query"] --> PROMPT

    subgraph AnswerAgent["💬 Answer Agent Pipeline"]
        PROMPT["📜 Prompt Builder<br/><i>answer/prompt.py</i><br/>━━━━━━━━━━━━━━<br/>System: legal assistant rules<br/>User: evidence + question"]

        LLM["🤖 LLM Call<br/><i>answer/llm.py</i><br/>━━━━━━━━━━━━━━<br/>gpt-4o-mini<br/>temperature=0<br/>max_tokens=500<br/>response_format=json"]

        VAL["✅ JSON Validator<br/><i>answer/validate.py</i><br/>━━━━━━━━━━━━━━<br/>Parse → Validate Schema<br/>→ Auto-repair (1 try)"]

        PROMPT --> LLM --> VAL
    end

    VAL --> OUT["Structured Response<br/>{query, answer, citations[]}"]

    style AnswerAgent fill:#f3e5f5,stroke:#9C27B0
```

**Prompt design:**

```
┌─────────────────────────────────────────┐
│  SYSTEM PROMPT                          │
│  • You are a legal research assistant   │
│  • Answer ONLY from provided evidence   │
│  • Use [n] inline citations             │
│  • Admit when evidence is insufficient  │
│  • Output strict JSON format:           │
│    {query, answer, citations[]}         │
└─────────────────────────────────────────┘
                    +
┌─────────────────────────────────────────┐
│  USER PROMPT                            │
│  Evidence:                              │
│  [1] Source: file.pdf | Page: 20        │
│  "The District Commission may order..." │
│  [2] Source: file.pdf | Page: 7         │
│  "Consumer rights include..."           │
│                                         │
│  Question: {user_query}                 │
└─────────────────────────────────────────┘
```

**Output schema:**

```json
{
  "query": "What actions can the District Commission take?",
  "answer": "The District Commission may direct the seller to remove the defect [1], replace the goods [1], or return the price paid [2].",
  "citations": [
    {"source": "a2019-35.pdf", "page": 20, "snippet": "...relevant excerpt..."},
    {"source": "a2019-35.pdf", "page": 7,  "snippet": "...relevant excerpt..."}
  ]
}
```

**LLM Configuration:**

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Model | `gpt-4o-mini` | Fast, cost-effective, strong at structured output |
| Temperature | `0` | Deterministic, factual responses |
| Max tokens | `500` | Prevents verbose outputs; keeps answers concise |
| Response format | `{"type": "json_object"}` | Enforces valid JSON at the API level |

---

### 📝 Intake Agent — Paralegal Mode

**File:** `agents/intake.py`

The Intake Agent is the entry point for **Paralegal Mode**. It conducts a structured case intake — gathering key details about the legal matter, parties involved, relevant facts, and desired outcomes — then formats this information into a structured case object that the Router Agent can process.

```mermaid
flowchart TD
    CLIENT["👤 Client / User"] -->|"Case details"| INTAKE

    subgraph IntakeAgent["📝 Intake Agent"]
        INTAKE["Parse & Structure<br/>Case Information"]

        EXTRACT_FACTS["Extract Key Facts<br/>━━━━━━━━━━━━━━<br/>• Parties involved<br/>• Nature of dispute<br/>• Relevant dates<br/>• Jurisdiction"]

        CLASSIFY_CASE["Classify Case Type<br/>━━━━━━━━━━━━━━<br/>• Criminal vs Civil<br/>• Statutory area<br/>• Urgency level"]

        FORMULATE["Formulate Legal<br/>Questions<br/>━━━━━━━━━━━━━━<br/>• Break case into<br/>  researchable queries<br/>• Prioritize issues"]

        INTAKE --> EXTRACT_FACTS --> CLASSIFY_CASE --> FORMULATE
    end

    FORMULATE --> ROUTER["🧭 Router Agent"]

    style IntakeAgent fill:#fff3e0,stroke:#FF9800
```

**Responsibilities:**

- **Case information parsing** — Extracts structured data from free-form case descriptions
- **Fact extraction** — Identifies parties, dispute nature, dates, and jurisdictional details
- **Case classification** — Determines the legal domain (criminal, civil, consumer, constitutional) and urgency
- **Query formulation** — Breaks the case down into discrete, researchable legal questions for the Retriever Agent

---

### 📊 Reporter Agent — Paralegal Mode

**File:** `agents/reporter.py`

The Reporter Agent is the **final stage** in Paralegal Mode. It takes the cited answers produced by the Answer Agent and compiles them into a comprehensive, professional legal report or dashboard view.

```mermaid
flowchart TD
    IN["Cited Answers<br/>from Answer Agent"] --> REPORTER

    subgraph ReporterAgent["📊 Reporter Agent"]
        REPORTER["Compile Results"]

        STRUCTURE["Structure Report<br/>━━━━━━━━━━━━━━<br/>• Case summary<br/>• Legal analysis<br/>• Applicable provisions<br/>• Citations & references"]

        FORMAT["Format Output<br/>━━━━━━━━━━━━━━<br/>• HTML report<br/>• Dashboard view<br/>• Downloadable format"]

        DASHBOARD["Generate Dashboard<br/>━━━━━━━━━━━━━━<br/>• Case strength indicators<br/>• Key provisions listed<br/>• Action items"]

        REPORTER --> STRUCTURE --> FORMAT --> DASHBOARD
    end

    DASHBOARD --> OUT["📄 Final Report<br/>+ 📊 Dashboard"]

    style ReporterAgent fill:#e8eaf6,stroke:#3F51B5
```

**Responsibilities:**

- **Result compilation** — Aggregates answers and citations from multiple legal queries into a unified view
- **Report structuring** — Organizes findings into case summary, legal analysis, applicable provisions, and references
- **Output formatting** — Generates HTML reports (via Jinja2 templates in `report/`) and dashboard views
- **Action items** — Highlights key legal provisions, potential arguments, and recommended next steps

---

## Supporting Modules

These modules in `retrieve/` and `answer/` provide the low-level functionality that the agents orchestrate.

### Decision Engine

**File:** `retrieve/decision.py`

Rule-based corpus filter and section booster — no LLM calls required.

```mermaid
flowchart LR
    Q["Query"] --> KW["Keyword Detection"]
    KW -->|"BNS, BNSS, BSA,<br/>Constitution"| CR["Criminal &<br/>Constitutional"]
    KW -->|"CPA, Consumer<br/>Protection"| CP["Consumer<br/>Protection"]
    KW -->|"CrPC, Criminal<br/>Procedure"| CPC["Criminal<br/>Procedure"]
    KW -->|"No match"| ALL["All Corpora"]
```

### MMR Diversifier

**File:** `retrieve/mmr.py`

Applies **Maximal Marginal Relevance** to balance relevance with diversity:

```
Score(d) = λ × Sim(d, query) − (1 − λ) × max[Sim(d, already_selected)]
```

Takes 24 candidates → outputs 6–8 diverse, non-redundant chunks.

### Evidence Packer

**File:** `retrieve/pack.py`

Formats chunks into numbered evidence blocks: `[1] Source: file.pdf | Page: 20 | "snippet..."` — each capped at ~400 characters.

### JSON Validator

**File:** `answer/validate.py`

```mermaid
flowchart LR
    IN["LLM Output"] --> P{"Valid JSON?"}
    P -->|"✅"| S{"Has query +<br/>answer +<br/>citations?"}
    P -->|"❌"| R["Auto-repair"]
    R --> P2{"Repaired?"}
    P2 -->|"✅"| S
    P2 -->|"❌"| ERR["Error"]
    S -->|"✅"| OK["✅ Valid"]
    S -->|"❌"| ERR
```

---

## Ingestion Pipeline

The ingestion pipeline (`ingest/`) transforms raw legal documents into searchable vectors:

```mermaid
flowchart LR
    subgraph Input["📄 Documents"]
        PDF["PDF"] & DOCX["DOCX"] & TXT["TXT"]
    end

    subgraph Extract["🔍 Extract"]
        E["Byte-based reading<br/>OCR fallback<br/>(Tesseract guarded)"]
    end

    subgraph Chunk["✂️ Chunk"]
        C["350–500 tokens<br/>1–2 sentence overlap<br/>Metadata attached"]
    end

    subgraph Index["📦 Index"]
        I["Batch embed<br/>(text-embedding-3-small)<br/>Qdrant upsert"]
    end

    PDF & DOCX & TXT --> E --> C --> I --> QD[("🔷 Qdrant")]
```

**Chunk metadata payload:**

| Field | Type | Description |
|-------|------|-------------|
| `doc_name` | string | Source filename |
| `page` | int | Page number in source |
| `chunk_id` | UUID | Unique chunk identifier |
| `chunk_index` | int | Sequential index within document |
| `corpus` | string | Legal corpus (BNS, CPA, CrPC, etc.) |
| `lang_detected` | string | Detected language |
| `text` | string | Chunk content |

---

## Data Flow & Sequence Diagrams

### Standard Q&A Mode — Full Sequence

```mermaid
sequenceDiagram
    actor User
    participant API as FastAPI
    participant Router as 🧭 Router<br/>Agent
    participant Retriever as 🎯 Retriever<br/>Agent
    participant QD as 🔷 Qdrant
    participant Answer as 💬 Answer<br/>Agent
    participant OAI as 🤖 OpenAI

    User->>API: POST /query {"query": "..."}

    API->>Router: Route query
    Note over Router: Classify query type<br/>Select corpus filter<br/>Apply section boosters<br/>Rewrite query

    Router->>Retriever: boosted_query + filters

    Retriever->>OAI: Embed query
    OAI-->>Retriever: q_vec (1536-d)

    Retriever->>QD: Search(q_vec, k=24, filters)
    QD-->>Retriever: 24 candidate chunks

    Note over Retriever: MMR diversification<br/>Deduplication<br/>Pack evidence [1]..[k]

    Retriever->>Answer: Evidence block + original query

    Answer->>OAI: System prompt + evidence + query
    Note over OAI: gpt-4o-mini<br/>temp=0, JSON mode
    OAI-->>Answer: Raw JSON

    Note over Answer: Validate JSON<br/>Auto-repair if needed

    Answer-->>API: {query, answer, citations[]}
    API-->>User: JSON response
```

### Paralegal Mode — Full Sequence

```mermaid
sequenceDiagram
    actor User
    participant API as FastAPI
    participant Intake as 📝 Intake<br/>Agent
    participant Router as 🧭 Router<br/>Agent
    participant Retriever as 🎯 Retriever<br/>Agent
    participant QD as 🔷 Qdrant
    participant Answer as 💬 Answer<br/>Agent
    participant Reporter as 📊 Reporter<br/>Agent
    participant OAI as 🤖 OpenAI

    User->>API: Submit case details
    API->>Intake: Raw case information

    Note over Intake: Extract key facts<br/>Classify case type<br/>Formulate legal questions

    Intake->>Router: Structured case + questions[]

    loop For each legal question
        Router->>Retriever: boosted_query + filters
        Retriever->>OAI: Embed query
        OAI-->>Retriever: q_vec
        Retriever->>QD: Search(q_vec, k=24)
        QD-->>Retriever: Candidates
        Note over Retriever: MMR → Pack evidence
        Retriever->>Answer: Evidence block
        Answer->>OAI: Prompt + evidence
        OAI-->>Answer: Cited answer
        Answer-->>Router: {answer, citations}
    end

    Router->>Reporter: All answers + case context

    Note over Reporter: Compile report<br/>Structure analysis<br/>Generate dashboard

    Reporter-->>API: 📄 Case Report + Dashboard
    API-->>User: Final report
```

---

## Directory Layout

```
legal-mvp/
│
├── app.py                        # ⚡ FastAPI application (routes: /ingest, /query, /healthz, /diag)
├── streamlit_app.py              # 🖥️ Streamlit demo UI (upload + query + history)
├── app_backup.py                 # Backup of main application
│
├── agents/                       # 🤖 AGENT LAYER — Core agentic architecture
│   ├── __init__.py               #   Agent registry & exports
│   ├── router.py                 #   🧭 Router Agent: query classification, corpus routing, boosting
│   ├── retriever.py              #   🎯 Retriever Agent: search orchestration, MMR, evidence packing
│   ├── answer.py                 #   💬 Answer Agent: LLM synthesis, JSON validation
│   ├── intake.py                 #   📝 Intake Agent: Paralegal mode case intake & structuring
│   └── reporter.py               #   📊 Reporter Agent: Paralegal mode report & dashboard generation
│
├── core/                         # ⚙️ Core Services
│   ├── config.py                 #   Environment variables, model names, feature flags
│   └── logging.py                #   Tolerant logging with req_id safety
│
├── clients/                      # 🔌 External Service Clients
│   ├── openai_client.py          #   Embeddings (text-embedding-3-small) + Chat (gpt-4o-mini)
│   └── qdrant_client.py          #   Collection CRUD, upsert, similarity search
│
├── ingest/                       # 📥 Ingestion Pipeline
│   ├── extract.py                #   PDF/DOCX/TXT byte-based extraction + OCR guard
│   ├── chunk.py                  #   Token-based chunking (350–500) with overlap & metadata
│   └── index.py                  #   Batch embedding + Qdrant upsert
│
├── retrieve/                     # 🔎 Retrieval Sub-modules
│   ├── decision.py               #   Decision Engine: corpus filter + section boosting rules
│   ├── search.py                 #   Qdrant cosine similarity search (k=24)
│   ├── mmr.py                    #   Maximal Marginal Relevance diversification + deduplication
│   └── pack.py                   #   Evidence Packer: numbered snippet formatting [1]..[k]
│
├── answer/                       # ✍️ Answer Generation Sub-modules
│   ├── prompt.py                 #   System + user prompt templates (strict JSON enforcement)
│   ├── llm.py                    #   LLM call wrapper (gpt-4o-mini, temp=0, JSON mode)
│   └── validate.py               #   JSON parser with auto-repair capability
│
├── report/                       # 📊 Report Generation
│   ├── render.py                 #   Jinja2-based HTML report renderer
│   └── templates/
│       └── answer.html.j2        #   HTML answer report template
│
├── scripts/                      # 🛠️ Utility Scripts (smoke tests, CLI tools)
├── tests/                        # 🧪 Test Suite
│
├── docker-compose.yml            # 🐳 Qdrant container @ port 6333
├── requirements.txt              # 📦 Python dependencies
├── check_pdfs.py                 # PDF diagnostic utility
├── debug_qdrant.py               # Qdrant debug/inspection tool
├── full_codebase.py              # Codebase consolidation script
├── smoke_ingest.sh               # Ingestion smoke test
├── test_ingest.py                # Ingestion test script
└── .gitignore
```

---

## Prerequisites

- **Python 3.10+** (virtualenv recommended)
- **Docker** & **Docker Compose** (for Qdrant)
- **OpenAI API key** (for embeddings + generation)
- *(Optional)* **Tesseract** for OCR on scanned PDFs — Windows: `choco install tesseract` (add to PATH)

---

## Quickstart

```bash
# 1. Create virtual environment & install dependencies
python -m venv venv
source venv/bin/activate          # Windows: .\venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env → set OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# 3. Start Qdrant vector database
docker compose up -d

# 4. Run FastAPI server
uvicorn app:app --host 127.0.0.1 --port 8000 --log-level info

# 5. (Optional) Launch Streamlit UI
streamlit run streamlit_app.py
```

**Verify setup:**

| Service | URL | Expected |
|---------|-----|----------|
| API Health | http://127.0.0.1:8000/healthz | `{"ok": true}` |
| API Diagnostics | http://127.0.0.1:8000/diag/env | `{"openai_key_set": true}` |
| Streamlit UI | http://localhost:8501 | Web interface |

---

## Configuration

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=sk-...
EMBED_MODEL=text-embedding-3-small
GEN_MODEL=gpt-4o-mini
QDRANT_URL=http://localhost:6333
TOP_K=8
USE_TRANSLATION=false
LANGS_OCR=eng+hin+tam+tel
```

> The app loads `.env` at startup (top of `app.py`) so all keys are available before clients initialize.

---

## API Reference

### `POST /ingest` — Document Ingestion

Upload one or more legal documents for processing and indexing.

**Request:** `multipart/form-data` with `files` field (PDF, DOCX, TXT)

```json
// Response
{
  "files_received": 3,
  "chunks_indexed": 128,
  "errors": []
}
```

### `POST /query` — Legal Q&A

Ask a question; receive a grounded JSON answer with inline citations.

```json
// Request
{"query": "What actions can the District Commission take for a defective product?"}

// Response
{
  "query": "What actions can the District Commission take for a defective product?",
  "answer": "The District Commission may direct the seller to remove the defect [1], replace the goods [1], or return the price paid [2].",
  "citations": [
    {"source": "a2019-35.pdf", "page": 20, "snippet": "..."},
    {"source": "a2019-35.pdf", "page": 7,  "snippet": "..."}
  ]
}
```

> Append `?format=html` for a pre-rendered HTML report.

### `GET /healthz` → `{"ok": true}`

### `GET /diag/env` → `{"openai_key_set": true}`

---

## Streamlit UI

The Streamlit interface (`streamlit_app.py`) provides a modern, mobile-friendly demo experience:

- **Sidebar:** Backend URL, answer style (Detailed/Summary), raw JSON toggle, document upload & ingest, clear history
- **Main area:** Query text area, answer cards with inline `[n]` superscripts, collapsible citation expander, HTML report download, conversation history

---

## Evaluation Protocol

**Recommended setup:** 30–50 queries across corpora (CPA, CrPC, BNS, etc.) with 20% "trick" questions

| Metric | Description | Target |
|--------|-------------|--------|
| **Correctness** | % factually correct answers | ≥ 85% |
| **Groundedness** | Every claim has supporting citation | 100% |
| **Citation accuracy** | Citations truly support their claims | ≥ 90% |
| **Recall@k** | Gold snippet in top-k results | ≥ 80% |
| **MRR** | Mean reciprocal rank of first relevant chunk | ≥ 0.7 |
| **Latency p50** | Median response time | ≤ 3s |
| **Latency p95** | 95th percentile response time | ≤ 5s |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| **401 OpenAI / invalid key** | Ensure `.env` has `OPENAI_API_KEY=sk-…`; verify via `GET /diag/env` |
| **Logger KeyError: req_id** | Handled by tolerant formatter — see `core/logging.py` |
| **Git Bash `curl (26)`** (Windows) | Use `curl.exe` (PowerShell) or Streamlit uploader |
| **Mis-grounded forms/annexures** | Add section boosters in Decision Engine; de-rank "FORM No." pages |
| **UI timeouts** | Increase Streamlit timeout (120–180s); reduce prompt/context size |

---

## Roadmap

- [ ] **Corpus expansion** — BNS/BNSS/BSA (new criminal codes), IPC §§141/415/503/320, HMA, Limitation Act
- [ ] **Judgment metadata** — Extract parties, bench, year, citation fields into vector payload
- [ ] **RAG eval harness** — Automated correctness & groundedness scoring pipeline
- [ ] **Auth & quotas** — Per-tenant API keys, rate limiting
- [ ] **Full containerization** — Dockerfile for FastAPI + Streamlit (compose with Qdrant)
- [ ] **Caching layer** — Redis-based embedding and result cache for repeated queries
- [ ] **Multi-language support** — Hindi, Tamil, Telugu legal documents with translation layer
- [ ] **Paralegal Mode enhancements** — Multi-turn conversation, case timeline builder, precedent comparison

---

## License

This repository is provided for educational and research use.

---

## Acknowledgements

- **[Qdrant](https://qdrant.tech/)** — High-performance vector search engine
- **[FastAPI](https://fastapi.tiangolo.com/)** + **Uvicorn** — Modern async Python web framework
- **[Streamlit](https://streamlit.io/)** — Rapid prototyping UI framework
- **[OpenAI](https://openai.com/)** — Embeddings (`text-embedding-3-small`) and chat completions (`gpt-4o-mini`)

---

<p align="center"><i>Upload docs → Ingest → Ask → Get grounded answers with citations.</i></p>
<p align="center"><b>Legal MVP — simple, explainable, and fast legal AI.</b></p>
