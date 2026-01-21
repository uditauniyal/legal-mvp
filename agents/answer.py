from clients.openai_client import client
from core.config import GEN_MODEL

ANSWER_SYSTEM_PROMPT = """
You are a helpful Indian Legal Assistant. Match the style of "NyayGuru".

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

class AnswerAgent:
    def __init__(self):
        pass

    def answer(self, query: str, context: list[dict], style: str = "Detailed") -> dict:
        # Prepare context string
        # Context items are ScoredPoint objects from Qdrant, so we access .payload
        context_str = "\n\n".join([
            f"Doc: {c.payload.get('doc_name', 'Unknown')} (Page {c.payload.get('page', '?')})\nText: {c.payload.get('text', '')}"
            for c in context
        ])

        messages = [
            {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
            {"role": "user", "content": f"User Query: {query}\n\nSearch Results:\n{context_str}"}
        ]
        
        try:
            # We want direct text, not JSON
            response = client.chat.completions.create(
                model=GEN_MODEL,
                temperature=0,
                messages=messages,
            )
            ans = response.choices[0].message.content
        except Exception as e:
            ans = "I'm sorry, I encountered an error generating the answer."
            print(f"[Answer] Error: {e}")

        # Citations are just the context chunks used
        return {
            "answer": ans,
            "citations": [
                {
                    "source": c.payload.get('doc_name', 'Unknown'), 
                    "page": c.payload.get('page', '?'), 
                    "snippet": c.payload.get('text', '')[:200]
                }
                for c in context
            ]
        }
