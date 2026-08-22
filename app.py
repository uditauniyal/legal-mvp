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
from core.run_logger import get_run_logger
from core import config
from core.verifier import CorpusIndex, audit_answer
from ingest.registry import DOCUMENT_REGISTRY

# Which Acts are actually searchable. Anything the answer cites outside
# this set could not have been retrieved -- the model produced it from
# training data. Built from the registry so it cannot drift from ingest.
CORPUS_INDEX = CorpusIndex(
    acts={info.statute_code for info in DOCUMENT_REGISTRY.values()},
    sections=[],
)

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
    """Report configuration health.

    Previously checked OPENAI_API_KEY, which no longer exists -- all traffic
    goes through OpenRouter. It reported False on a perfectly working setup.
    """
    problems = config.check()
    return {
        "ok": not problems,
        "problems": problems,
        "config": config.describe(),
    }

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
                # chunk_page assigns a DETERMINISTIC chunk_id of the form
                # "<doc>:<page>:<index>". Overwriting it with uuid.uuid4() is
                # what caused 618 duplicate chunks in the index, because every
                # ingest produced fresh ids that upsert could not match.
                all_chunks.extend(chunk_page(name, page, text))

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

from agents.reporter import ReporterAgent
from agents.intake import IntakeAgent

# Initialize Agents
intake_agent = IntakeAgent()
router_agent = RouterAgent()
retrieval_agent = RetrievalAgent()
answer_agent = AnswerAgent()
reporter_agent = ReporterAgent()

@app.post("/query")
async def query(body: dict, format: str = Query(default="json")):
    q = body.get("query", "").strip()
    if not q:
        return JSONResponse({"error": "empty query"}, status_code=400)

    # One record per query. Every stage below adds to it; it is written once at
    # the end. This is Prof. Joshi's item 2 and the prerequisite for every
    # number in the paper -- see docs/EVALUATION_PLAN.md.
    rec = get_run_logger(config.describe()).new_record(
        query_id=body.get("query_id", "adhoc"),
        query_raw=q,
    )

    # 1. Intake (Analysis & Triage)
    case_context = intake_agent.analyze(q)
    rec.set("intake",
            scenario=case_context.scenario,
            persona=case_context.user_persona,
            urgency=case_context.urgency,
            complexity=case_context.complexity,
            financial_status=case_context.financial_status,
            domain=case_context.predicted_legal_domain,
            issues=case_context.legal_issues,
            missing_facts=case_context.missing_facts,
            llm_ok=case_context.llm_ok,
            fallback_used=case_context.fallback_used,
            llm_error=case_context.llm_error)

    # 2. Router (Corpus Selection)
    plan = router_agent.route(case_context)
    rec.set("router",
            target_corpus=plan.target_corpus,
            decision_path=plan.decision_path,
            intent=plan.intent,
            entities=plan.entities,
            boost_terms=plan.boost_terms,
            rewritten_query=plan.rewritten_query)

    # 3. Retrieve (now returns RetrievalResult with confidence scoring)
    retrieval = retrieval_agent.retrieve(plan)
    rec.set("retrieval",
            filter_applied=retrieval.filter_applied,
            filter_fallback_fired=retrieval.filter_fallback_fired,
            n_retrieved=retrieval.total_retrieved,
            n_after_filter=retrieval.total_chunks,
            scores_raw=retrieval.scores_raw,
            max_score=retrieval.max_score,
            embed_provider=retrieval.embed_provider,
            chunks=[{"doc": c.payload.get("doc_name"),
                     "page": c.payload.get("page"),
                     "corpus": c.payload.get("corpus"),
                     "score": round(float(c.score), 6),
                     "text_head": (c.payload.get("text") or "")[:160]}
                    for c in retrieval.chunks])
    rec.set("confidence",
            top_k_mean=retrieval.top_k_mean,
            score_gap=retrieval.score_gap,
            entity_coverage=retrieval.entity_coverage,
            entity_coverage_default_used=retrieval.entity_coverage_default_used,
            composite=retrieval.confidence,
            refused=retrieval.refused)

    # 4. Answer (includes refusal gate)
    style = body.get("style", "Detailed")
    data = answer_agent.answer(q, retrieval, style=style)
    rec.set("answer",
            refused=data.get("refused"),
            prompt_variant=data.get("prompt_variant"),
            llm_ok=data.get("llm_ok"),
            llm_error=data.get("llm_error"),
            provider_name=data.get("gen_provider"),
            model=data.get("gen_model"),
            prompt_tokens=data.get("prompt_tokens"),
            completion_tokens=data.get("completion_tokens"),
            answer_text=data.get("answer"),
            citations=data.get("citations"))

    # 5. Report (Paralegal Mode PDF)
    # Include Paralegal Context ALWAYS (so Dashboard works even if PDF fails)
    data["paralegal_context"] = {
        "scenario": case_context.scenario,
        "issues": case_context.legal_issues,
        "persona": case_context.user_persona,
        "complexity": case_context.complexity,
        "urgency": case_context.urgency,
        "financial_status": case_context.financial_status,
        "missing_facts": case_context.missing_facts
    }

    # Only generate PDF if the system did NOT refuse
    if not data.get("refused", False):
        report_filename = f"report_{uuid.uuid4().hex[:8]}.pdf"
        report_path = Path("static") / report_filename
        report_path.parent.mkdir(exist_ok=True)
        
        try:
            reporter_agent.generate_report(q, plan, data, filename=str(report_path))
            data["report_url"] = f"/static/{report_filename}"
        except Exception as e:
            print(f"Report Generation Failed: {e}")
            data["report_error"] = str(e)

    # 4.5 Verify: are the provisions the answer cites actually present in the
    # passages it was given? Deterministic -- no LLM, no cost, same numbers
    # every run. Runs on EVERY query, so the metrics accumulate automatically
    # rather than only during evaluation.
    if not data.get("refused"):
        retrieved_text = "\n".join(
            (c.get("snippet") or "") for c in (data.get("citations") or [])
        )
        audit = audit_answer(
            answer_text=data.get("answer") or "",
            retrieved_text=retrieved_text,
            corpus=CORPUS_INDEX,
            panel_text=retrieved_text,
        )
        rec.set(
            "verifier",
            cited=[str(p) for p in audit.cited],
            grounded=[str(p) for p in audit.grounded],
            ungrounded=[str(p) for p in audit.ungrounded],
            out_of_corpus=[str(p) for p in audit.out_of_corpus],
            vintage_errors=audit.vintage_errors,
            **audit.summary(),
        )
        data["citation_audit"] = audit.summary()

    # Write the record. finish() is idempotent, so the html branch below
    # cannot double-write it.
    rec.set("answer", report_url=data.get("report_url"))
    rec.finish()
    data["req_id"] = rec.data["req_id"]

    # 6. Render
    if format == "html":
        try:
            html = render_html(data)
            return HTMLResponse(content=html, media_type="text/html")
        except Exception as e:
            return JSONResponse({"error": f"HTML Render failed: {e}", "data": data}, status_code=500)

    return JSONResponse(data)

# Serve static files for reports
try:
    from fastapi.staticfiles import StaticFiles
    app.mount("/static", StaticFiles(directory="static"), name="static")
except RuntimeError:
    pass # Already mounted or directory issue handled explicitly

