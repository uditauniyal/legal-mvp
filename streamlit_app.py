# streamlit_app.py
# Modern Streamlit UI for Legal MVP (FastAPI + Qdrant RAG)
# Run: streamlit run streamlit_app.py

import json
import re
import time
from datetime import datetime
from typing import Dict, Any, List

import requests
import streamlit as st

# =========================
# Config
# =========================
DEFAULT_BASE_URL = "http://127.0.0.1:8000"   # your backend base URL
QUERY_PATH       = "/query"                  # POST endpoint (expects {"query": "..."} JSON)

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
  --primary:#1e40af; /* blue-800 */
  --primary-600:#2563eb; /* blue-600 */
  --muted:#64748b;  /* slate-500 */
  --bg:#f6f8fb;     /* light background */
  --card-bg:#ffffff;
  --shadow: 0 10px 24px rgba(2,6,23,0.06);
  --radius:18px;
}
[data-testid="stAppViewContainer"]{
  background: var(--bg);
}
.block-container{
  padding-top: 2.2rem;
  padding-bottom: 3.2rem;
  max-width: 880px;
}
h1,h2,h3,h4{
  letter-spacing: .1px;
}
.big-hero{
  text-align: center;
  margin-bottom: 1.2rem;
}
.big-hero .emoji{
  font-size: 44px;
  line-height: 1;
}
.big-hero .title{
  font-size: 34px;
  font-weight: 800;
  color: var(--primary);
  margin-top: .2rem;
}
.big-hero .subtitle{
  color: var(--muted);
  margin-top: .25rem;
  font-size: 15px;
}

.card{
  background: var(--card-bg);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 18px 18px;
  border: 1px solid rgba(2,6,23,0.05);
}
.card + .card{ margin-top:14px; }

.answer{
  font-size: 16px;
  line-height: 1.6;
}
sup{ font-size: .8em; color: var(--primary-600); }

.small-meta{
  color: var(--muted);
  font-size: 12px;
  margin-top: 6px;
}

footer{
  color: var(--muted);
  font-size: 13px;
  text-align: center;
  margin-top: 32px;
}

.stTextArea textarea{
  border-radius: 14px !important;
  border: 1px solid rgba(2,6,23,0.08) !important;
}

.stButton>button{
  background: var(--primary-600);
  color: #fff;
  border-radius: 12px;
  padding: 0.6rem 1.1rem;
  border: none;
  box-shadow: var(--shadow);
}
.stButton>button:hover{
  background: #1d4ed8;
}

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

def ensure_session():
    if "history" not in st.session_state:
        st.session_state.history: List[Dict[str, Any]] = []

# =========================
# Sidebar (Settings)
# =========================
with st.sidebar:
    st.header("⚙️ Settings")
    base_url = st.text_input("Backend URL", value=DEFAULT_BASE_URL, help="Your FastAPI server")
    answer_style = st.radio("Answer style", ["Detailed", "Summary"], horizontal=True)
    show_raw = st.toggle("Show raw JSON", value=False)
    gen_html = st.toggle("Also fetch HTML report", value=False, help="Uses ?format=html (if supported)")
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
            # Try to surface backend error nicely
            try:
                err_json = resp.json()
                st.error(f"Backend error {resp.status_code}")
                st.code(json.dumps(err_json, indent=2, ensure_ascii=False), language="json")
            except Exception:
                st.error(f"Backend error {resp.status_code}: {resp.text}")
        else:
            # Parse JSON answer
            try:
                data = resp.json()
            except Exception:
                st.error("Backend did not return JSON.")
                st.text(resp.text)
                data = None

            if data:
                # Save to history
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
    st.markdown('<div class="answer">', unsafe_allow_html=True)
    st.markdown(answer_html, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Small meta row
    st.markdown(
        f'<div class="small-meta">Style: <b>{latest["style"]}</b> • Latency: <b>{latency_ms} ms</b></div>',
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    # Citations expander
    with st.expander("📚 Citations / Sources"):
        if citations:
            for i, c in enumerate(citations, start=1):
                source = c.get("source", "Unknown")
                page = c.get("page", "?")
                snippet = (c.get("snippet") or "").strip().replace("\n", " ")
                if len(snippet) > 600:
                    snippet = snippet[:600] + "…"
                st.markdown(f"**[{i}] {source}**, p.{page} — {snippet}")
        else:
            st.info("No citations returned.")

    # Optional raw JSON
    if show_raw:
        st.subheader("Raw JSON")
        st.code(json.dumps(data, indent=2, ensure_ascii=False), language="json")

    # Optional HTML report fetch (if your backend supports ?format=html)
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
    for item in st.session_state.history[1:5]:  # show last 4 more
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
