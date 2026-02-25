
# streamlit_app.py
# Modern Streamlit UI for Legal MVP (FastAPI + Qdrant RAG) + Document Upload & Ingestion

import json
import re
import time
import mimetypes
from datetime import datetime
from typing import Dict, Any, List

import requests
import streamlit as st

# =========================
# Config
# =========================
DEFAULT_BASE_URL = "http://127.0.0.1:8000"   # your backend base URL
QUERY_PATH       = "/query"                  # POST endpoint (expects {"query": "..."} JSON)
INGEST_PATH      = "/ingest"                 # POST endpoint (multipart form: files=<file> ...)

st.set_page_config(
    page_title="Legal MVP – RAG Demo",
    page_icon="⚖️",
    layout="wide",
)

# =========================
# Styles (professional: blue/grey/white)
# =========================
CSS = """
<style>
:root{
  --primary:#1e40af;
  --primary-600:#2563eb;
  --muted:#64748b;
  --bg:#f6f8fb;
  --card-bg:#ffffff;
  --shadow: 0 10px 24px rgba(2,6,23,0.06);
  --radius:18px;
}
[data-testid="stAppViewContainer"]{ background: var(--bg); }
.block-container{ padding-top: 2.2rem; padding-bottom: 3.2rem; max-width: 880px; }
h1,h2,h3,h4{ letter-spacing: .1px; }
.big-hero{ text-align: center; margin-bottom: 1.2rem; }
.big-hero .emoji{ font-size: 44px; line-height: 1; }
.big-hero .title{ font-size: 34px; font-weight: 800; color: var(--primary); margin-top: .2rem; }
.big-hero .subtitle{ color: var(--muted); margin-top: .25rem; font-size: 15px; }
.card{ background: var(--card-bg); border-radius: var(--radius); box-shadow: var(--shadow); padding: 18px 18px;
       border: 1px solid rgba(2,6,23,0.05); }
.card + .card{ margin-top:14px; }
.answer{ font-size: 16px; line-height: 1.6; }
sup{ font-size: .8em; color: var(--primary-600); }
.small-meta{ color: var(--muted); font-size: 12px; margin-top: 6px; }
footer{ color: var(--muted); font-size: 13px; text-align: center; margin-top: 32px; }
.stTextArea textarea{ border-radius: 14px !important; border: 1px solid rgba(2,6,23,0.08) !important; }
.stButton>button{ background: var(--primary-600); color: #fff; border-radius: 12px; padding: 0.6rem 1.1rem;
                  border: none; box-shadow: var(--shadow); }
.stButton>button:hover{ background: #1d4ed8; }
@media (max-width: 640px){
  .block-container{ padding-left: 14px; padding-right: 14px; }
  .big-hero .title{ font-size: 26px; }
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# =========================
# Helpers
# =========================
def superscript_markers(text: str) -> str:
    """Turn [1][2] markers into superscripts for readability."""
    return re.sub(r"\[(\d+)\]", r"<sup>[\1]</sup>", text or "")

def build_query(original: str, style: str) -> str:
    """Client-side hinting to style the answer without changing your backend contract."""
    if style == "Summary":
        return f"{original.strip()} (Respond concisely.)"
    else:
        return f"{original.strip()} (Provide a detailed, step-by-step explanation.)"

def call_backend(base_url: str, query: str, timeout: int = 90) -> requests.Response:
    url = base_url.rstrip("/") + QUERY_PATH
    return requests.post(url, json={"query": query}, timeout=timeout)

def ingest_documents(base_url: str, uploaded_files: List[Any], timeout: int = 300) -> requests.Response:
    """Send selected files to FastAPI /ingest as multipart form-data."""
    url = base_url.rstrip("/") + INGEST_PATH
    form_files = []
    for f in uploaded_files:
        data = f.getvalue()
        mt = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        form_files.append(("files", (f.name, data, mt)))
    return requests.post(url, files=form_files, timeout=timeout)

def ensure_session():
    if "history" not in st.session_state:
        st.session_state.history: List[Dict[str, Any]] = []

# =========================
# Sidebar (Settings + Ingestion)
# =========================
with st.sidebar:
    st.header("⚙️ Settings")
    base_url = st.text_input("Backend URL", value=DEFAULT_BASE_URL, help="Your FastAPI server")
    answer_style = st.radio("Answer style", ["Detailed", "Summary"], horizontal=True)
    show_raw = st.toggle("Show raw JSON", value=False)
    gen_html = st.toggle("Also fetch HTML report", value=False, help="Uses ?format=html (if supported)")

    st.divider()
    st.subheader("📄 Upload & Ingest Documents")
    uploaded_files = st.file_uploader(
        "Upload PDF / DOCX / TXT",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True,
        help="Files will be indexed in Qdrant via your FastAPI /ingest endpoint.",
    )
    ingest_btn = st.button("⬆️ Upload & Ingest", use_container_width=True, disabled=not uploaded_files)

    if ingest_btn:
        with st.spinner("Uploading and ingesting…"):
            try:
                resp_ing = ingest_documents(base_url, uploaded_files)
            except requests.exceptions.RequestException as e:
                st.error(f"Ingestion request failed: {e}")
                resp_ing = None

        if resp_ing is None:
            pass
        elif resp_ing.status_code != 200:
            try:
                err_json = resp_ing.json()
                st.error("Ingestion failed.")
                st.code(json.dumps(err_json, indent=2, ensure_ascii=False), language="json")
            except Exception:
                st.error(f"Ingestion failed: {resp_ing.text}")
        else:
            try:
                body = resp_ing.json()
            except Exception:
                body = {"raw": resp_ing.text}
            st.success("Ingestion successful ✅")
            st.caption("Response:")
            st.code(json.dumps(body, indent=2, ensure_ascii=False), language="json")

    st.divider()
    if st.button("🗑️ Clear history", use_container_width=True):
        st.session_state.history = []
        st.success("Cleared conversation history.")

# =========================
# Header
# =========================
st.markdown(
    """
<div class="big-hero">
  <div class="emoji">⚖️</div>
  <div class="title">Legal MVP – RAG Demo</div>
  <div class="subtitle">Ask a legal question. Answers are grounded with citations from your corpus.</div>
</div>
""",
    unsafe_allow_html=True,
)

# =========================
# Input Form
# =========================
ensure_session()
with st.form("qa_form", clear_on_submit=False):
    user_query = st.text_area(
        "Your question",
        placeholder="e.g., What are the maintenance provisions under Section 125 CrPC (BNSS)?",
        height=120,
    )
    colA, colB = st.columns([1, 1])
    with colA:
        submit = st.form_submit_button("Ask")
    with colB:
        now = datetime.now().strftime("%b %d, %I:%M %p")
        st.caption(f"Local time: {now}")

# =========================
# Handle Submission
# =========================
if submit:
    if not user_query.strip():
        st.warning("Please enter a question.")
    else:
        query_to_send = build_query(user_query, answer_style)
        t0 = time.perf_counter()
        with st.spinner("Thinking… contacting backend and composing a grounded answer."):
            try:
                resp = call_backend(base_url, query_to_send)
            except requests.exceptions.RequestException as e:
                st.error(f"Request error: {e}")
                resp = None

        latency_ms = int((time.perf_counter() - t0) * 1000)

        if resp is None:
            pass
        elif resp.status_code != 200:
            try:
                err_json = resp.json()
                st.error(f"Backend error {resp.status_code}")
                st.code(json.dumps(err_json, indent=2, ensure_ascii=False), language="json")
            except Exception:
                st.error(f"Backend error {resp.status_code}: {resp.text}")
        else:
            try:
                data = resp.json()
            except Exception:
                st.error("Backend did not return JSON.")
                st.text(resp.text)
                data = None

            if data:
                st.session_state.history.insert(0, {
                    "query": user_query.strip(),
                    "style": answer_style,
                    "data": data,
                    "latency_ms": latency_ms
                })

# =========================
# Render Latest Answer (as a card)
# =========================
if st.session_state.history:
    latest = st.session_state.history[0]
    data = latest["data"]
    answer_html = superscript_markers(data.get("answer", ""))
    citations = data.get("citations", []) or []
    q_text = latest["query"]
    latency_ms = latest["latency_ms"]

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(f"**🧑‍⚖️ Question:** {q_text}")

    # --- Confidence Badge & Refusal Banner ---
    confidence = data.get("confidence", None)
    refused = data.get("refused", False)

    if refused:
        st.error("🚫 **Answer Refused** — The system did not find enough reliable legal sources to "
                 "provide a trustworthy answer. This prevents hallucinated legal advice.")
    
    if confidence is not None:
        pct = round(confidence * 100, 1)
        if confidence >= 0.55:
            badge = f"🟢 **High Confidence** ({pct}%)"
        elif confidence >= 0.38:
            badge = f"🟡 **Medium Confidence** ({pct}%)"
        else:
            badge = f"🔴 **Low Confidence** ({pct}%)"
        st.markdown(f"📊 Retrieval Quality: {badge}")

    st.markdown('<div class="answer">', unsafe_allow_html=True)
    st.markdown(answer_html, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # --- Paralegal Dashboard (New UI) ---
    ctx = data.get("paralegal_context")
    if ctx:
        st.markdown("### 🏛️ Paralegal Dashboard")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Scenario", ctx.get("scenario", "N/A"))
            st.metric("Persona", ctx.get("persona", "N/A"))
        with col2:
            st.metric("Urgency", ctx.get("urgency", "N/A"))
            st.metric("Complexity", ctx.get("complexity", "N/A"))
        with col3:
            st.metric("Financial", ctx.get("financial_status", "Unknown"))
            if confidence is not None:
                st.metric("Confidence", f"{round(confidence * 100, 1)}%")
        
        if ctx.get("missing_facts"):
            st.warning(f"⚠️ Missing Facts: {', '.join(ctx.get('missing_facts'))}")
            
    # --- PDF Report Download (only if not refused) ---
    if not refused:
        report_url = data.get("report_url")
        if report_url:
            full_report_url = base_url.rstrip("/") + report_url
            st.link_button("📄 Download Formal Legal Report (PDF)", full_report_url)
    
    st.markdown(
        f'<div class="small-meta">Style: <b>{latest["style"]}</b> • Latency: <b>{latency_ms} ms</b></div>',
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    with st.expander("📚 Citations / Sources"):
        if citations:
            for i, c in enumerate(citations, start=1):
                source = c.get("source", "Unknown")
                page = c.get("page", "?")
                snippet = (c.get("text") or c.get("snippet") or "").strip().replace("\n", " ")
                if len(snippet) > 600:
                    snippet = snippet[:600] + "…"
                st.markdown(f"**[{i}] {source}**, p.{page} — {snippet}")
        else:
            st.info("No citations returned.")

    if show_raw:
        st.subheader("Raw JSON")
        st.code(json.dumps(data, indent=2, ensure_ascii=False), language="json")

    if gen_html:
        try:
            url = base_url.rstrip("/") + QUERY_PATH + "?format=html"
            t_html = time.perf_counter()
            html_resp = requests.post(url, json={"query": build_query(q_text, latest["style"])}, timeout=90)
            html_latency = int((time.perf_counter() - t_html) * 1000)
            if html_resp.status_code == 200 and "text/html" in html_resp.headers.get("content-type",""):
                html_bytes = html_resp.content
                st.download_button(
                    "⬇️ Download HTML report",
                    data=html_bytes,
                    file_name="legal_mvp_report.html",
                    mime="text/html",
                    use_container_width=True,
                )
                st.caption(f"HTML generated in {html_latency} ms")
            else:
                st.warning("Backend did not return HTML (enable ?format=html in your API).")
        except requests.exceptions.RequestException as e:
            st.warning(f"HTML report fetch failed: {e}")

# =========================
# Conversation History (previous answers as compact cards)
# =========================
if len(st.session_state.history) > 1:
    st.subheader("History")
    for item in st.session_state.history[1:5]:
        a_html = superscript_markers(item["data"].get("answer", ""))
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f"**🧑‍⚖️ {item['query']}**")
        st.markdown(a_html, unsafe_allow_html=True)
        st.markdown(
            f'<div class="small-meta">Style: <b>{item["style"]}</b> • Latency: <b>{item["latency_ms"]} ms</b></div>',
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

# =========================
# Footer
# =========================
st.markdown("---")
st.markdown(
    '<footer>Built with ❤️ using FastAPI + Streamlit + Qdrant.</footer>',
    unsafe_allow_html=True,
)
