from clients.openai_client import client
from core.config import GEN_MODEL
from agents.retriever import RetrievalResult

ANSWER_SYSTEM_PROMPT = """
You are a helpful Indian Legal Assistant. Match the style of "NyayGuru", but write strictly in English.
IMPORTANT: Write your response in English language only. Do not use Hinglish or Hindi words.

### STRUCTURE YOUR RESPONSE EXACTLY LIKE THIS:

**1. Try an Informal Solution First**
(Advice on mediation, talking to neighbors, etc.)

**2. Gather Evidence**
(What photos, videos, or logs should the user keep?)

**3. Immediate Police Help**
(When to dial 100/112, how to file an FIR).

**4. Relevant Legal Provisions (Tabulated)**
| Law/Act | Section | Provision |
| :--- | :--- | :--- |
| BNS | Sec 290 | Public Nuisance |
| CrPC | Sec 133 | Removal of Nuisance |
(List ONLY laws relevant to the context).

**5. Administrative & Civil Remedies**
(Municipal complaints, RWA notices, Civil suits).

**6. Practical Tips**
(Safety, avoiding retaliation).

**7. Offer to Draft**
(Ask if they want a formal complaint drafted).
"""

# --- Confidence-aware disclaimer overlays ---
MEDIUM_CONFIDENCE_DISCLAIMER = """
IMPORTANT CONTEXT: The retrieved legal sources may not fully address the user's specific question.
In your response:
- Clearly indicate which parts are directly supported by the retrieved documents.
- When drawing on general legal principles not found in the retrieved text, say so explicitly.
- Recommend consulting a qualified lawyer for the specific situation.
"""

LOW_CONFIDENCE_DISCLAIMER = """
CRITICAL CONTEXT: The retrieved legal sources have very low relevance to this query.
The knowledge base likely does not contain the specific laws or documents needed to answer this question authoritatively.

In your response:
- Provide ONLY general legal guidance and direction.
- Do NOT cite specific sections unless they appear in the retrieved text.
- Clearly state that your answer is based on general legal knowledge, not verified sources.
- STRONGLY recommend consulting a qualified lawyer or visiting the nearest Legal Aid Centre.
- Suggest what type of lawyer or legal forum the user should approach.
"""

REFUSAL_MESSAGE = (
    "I don't have enough reliable legal sources in my knowledge base to answer "
    "this question accurately. To get a trustworthy response, please try one of "
    "the following:\n\n"
    "1. **Rephrase your query** with more specific legal terms (e.g., mention "
    "the relevant Section, Act, or case name).\n"
    "2. **Upload relevant legal documents** (PDF/DOCX) through the sidebar so "
    "I can search them.\n"
    "3. **Narrow the scope** — ask about a specific legal provision instead of "
    "a broad topic.\n\n"
    "This safeguard exists to prevent me from generating unreliable or "
    "hallucinated legal advice."
)

# --- Confidence thresholds ---
HIGH_CONFIDENCE = 0.55
MEDIUM_CONFIDENCE = 0.38


class AnswerAgent:
    def __init__(self):
        pass

    def answer(self, query: str, retrieval: RetrievalResult, style: str = "Detailed") -> dict:
        # --- Refusal Gate ---
        if retrieval.refused or not retrieval.chunks:
            print(f"[Answer] REFUSED — confidence={retrieval.confidence}, chunks={retrieval.total_chunks}")
            return {
                "answer": REFUSAL_MESSAGE,
                "citations": [],
                "confidence": retrieval.confidence,
                "refused": True,
            }

        context = retrieval.chunks

        # --- Confidence-aware prompt adjustment ---
        system_prompt = ANSWER_SYSTEM_PROMPT
        if retrieval.confidence < MEDIUM_CONFIDENCE:
            system_prompt = LOW_CONFIDENCE_DISCLAIMER + "\n\n" + ANSWER_SYSTEM_PROMPT
            print(f"[Answer] LOW confidence ({retrieval.confidence:.3f}) — adding strong disclaimer")
        elif retrieval.confidence < HIGH_CONFIDENCE:
            system_prompt = MEDIUM_CONFIDENCE_DISCLAIMER + "\n\n" + ANSWER_SYSTEM_PROMPT
            print(f"[Answer] MEDIUM confidence ({retrieval.confidence:.3f}) — adding soft disclaimer")
        else:
            print(f"[Answer] HIGH confidence ({retrieval.confidence:.3f}) — generating normally")

        # Prepare context string
        context_str = "\n\n".join([
            f"Doc: {c.payload.get('doc_name', 'Unknown')} (Page {c.payload.get('page', '?')})\nText: {c.payload.get('text', '')}"
            for c in context
        ])

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"User Query: {query}\n\nSearch Results:\n{context_str}"}
        ]
        
        try:
            response = client.chat.completions.create(
                model=GEN_MODEL,
                temperature=0,
                messages=messages,
            )
            ans = response.choices[0].message.content
        except Exception as e:
            ans = "I'm sorry, I encountered an error generating the answer."
            print(f"[Answer] Error: {e}")

        return {
            "answer": ans,
            "citations": [
                {
                    "source": c.payload.get('doc_name', 'Unknown'), 
                    "page": c.payload.get('page', '?'), 
                    "snippet": c.payload.get('text', '')[:200]
                }
                for c in context
            ],
            "confidence": retrieval.confidence,
            "refused": False,
        }


