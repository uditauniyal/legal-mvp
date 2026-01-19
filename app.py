# Load .env early so OPENAI_API_KEY is available everywhere
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root (where app.py lives)
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=True)

from fastapi import FastAPI, UploadFile, File, Query
from fastapi.responses import JSONResponse, HTMLResponse
from typing import List
import hashlib
import traceback
import uuid
from pathlib import Path

from core.logging import new_req_id
from clients.qdrant_client import qdrant, ensure_collection
from clients.openai_client import embed_texts
from core.schemas import AnswerJSON
from ingest.extract import extract_text_pdf_bytes, extract_text_docx_bytes, extract_text_txt_bytes
from ingest.chunk import chunk_page
from ingest.index import index_chunks
from agents.router import RouterAgent
from agents.retriever import RetrievalAgent
from agents.answer import AnswerAgent

from report.render import render_html

app = FastAPI(title="Legal MVP")

# Unique build id — proves reload when code changes
with open(__file__, "rb") as f:
    BUILD_ID = hashlib.sha1(f.read()).hexdigest()[:8]

@app.on_event("startup")
def startup():
    ensure_collection(qdrant())

@app.get("/healthz")
def healthz():
    return {"ok": True, "build": BUILD_ID}

@app.get("/diag/env")
def diag_env():
    """Check if OPENAI_API_KEY is loaded correctly"""
    import os
    return {"openai_key_set": bool(os.getenv("OPENAI_API_KEY"))}

@app.post("/ingest")
async def ingest_files(files: List[UploadFile] = File(...)):
    all_chunks, errors = [], []

    for f in files:
        name = Path(f.filename).name
        try:
            data = await f.read()
            ext = name.lower().split(".")[-1]

            if ext == "pdf":
                pages = extract_text_pdf_bytes(data)
            elif ext == "docx":
                pages = extract_text_docx_bytes(data)
            elif ext == "txt":
                pages = extract_text_txt_bytes(data)
            else:
                raise ValueError(f"Unsupported file type: {ext}")

            for (page, text) in pages:
                chunk = chunk_page(name, page, text)
                for c in chunk:
                    c["chunk_id"] = str(uuid.uuid4())
                all_chunks.extend(chunk)

        except Exception:
            errors.append({"file": name, "traceback": traceback.format_exc()})

    if all_chunks:
        try:
            index_chunks(all_chunks)
        except Exception:
            errors.append({"stage": "qdrant_upsert", "traceback": traceback.format_exc()})

    return JSONResponse({
        "files_received": len(files),
        "chunks_indexed": len(all_chunks),
        "errors": errors
    }, status_code=200 if all_chunks or errors else 400)

# Initialize Agents
router_agent = RouterAgent()
retrieval_agent = RetrievalAgent()
answer_agent = AnswerAgent()

@app.post("/query")
async def query(body: dict, format: str = Query(default="json")):
    q = body.get("query", "").strip()
    if not q:
        return JSONResponse({"error": "empty query"}, status_code=400)

    # 1. Plan
    plan = router_agent.route(q)
    
    # 2. Retrieve
    context = retrieval_agent.retrieve(plan)
    
    # 3. Answer
    # Detect style from body if provided, else default
    style = body.get("style", "Detailed")
    data = answer_agent.answer(q, context, style=style)

    # 4. Render
    if format == "html":
        # We need to adapt the data structure for render_html if necessary
        # render_html expects 'answer' and 'citations' keys, which AnswerAgent returns.
        try:
            html = render_html(data)
            return HTMLResponse(content=html, media_type="text/html")
        except Exception as e:
            # Fallback if render fails
            return JSONResponse({"error": f"HTML Render failed: {e}", "data": data}, status_code=500)

    return JSONResponse(data)
