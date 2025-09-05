from fastapi import FastAPI, UploadFile, File, Query
from fastapi.responses import JSONResponse, HTMLResponse
from typing import List
from pathlib import Path
import hashlib
import traceback
import uuid

from core.logging import new_req_id
from clients.qdrant_client import qdrant, ensure_collection
from clients.openai_client import embed_texts
from core.schemas import AnswerJSON
from ingest.extract import extract_text_pdf_bytes, extract_text_docx_bytes, extract_text_txt_bytes
from ingest.chunk import chunk_page
from ingest.index import index_chunks
from retrieve.decision import decision_agent, rewrite_query
from retrieve.search import search
from retrieve.pack import build_snippets
from answer.prompt import build_messages
from answer.llm import get_json_answer
from answer.validate import parse_or_repair
from report.render import render_html
from core.config import TOP_K

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
                # Assign safe UUIDs for point IDs
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

@app.post("/query")
async def query(body: dict, format: str = Query(default="json")):
    q = body.get("query", "").strip()
    if not q:
        return JSONResponse({"error": "empty query"}, status_code=400)

    d = decision_agent(q)
    q2 = rewrite_query(q, d["boosts"])
    q_vec = embed_texts([q2])[0]
    points = search(q_vec, top_k=3 * TOP_K, payload_filter=d["filter"])

    # Dedupe
    seen_ids = set()
    unique_points = []
    for p in points:
        if p.id not in seen_ids:
            seen_ids.add(p.id)
            unique_points.append(p)

    snippets = build_snippets(unique_points[:TOP_K])

    messages = build_messages(q, snippets)
    raw = get_json_answer(messages)
    data = parse_or_repair(raw)

    try:
        AnswerJSON(**data)
    except Exception as e:
        return JSONResponse(
            {"error": f"JSON validation failed: {e}", "raw_response": raw},
            status_code=500
        )

    if format == "html":
        html = render_html(data)
        return HTMLResponse(content=html, media_type="text/html")

    return JSONResponse(data)
