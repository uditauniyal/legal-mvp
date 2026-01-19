import json
from agents.router import QueryPlan
from clients.openai_client import chat_json

# --- Prompts ---
SYSTEM_PROMPT = """You are an Indian Legal Assistant. Answer the user's question based ONLY on the provided Context.
Respond in English unless the user explicitly asks for another language.
match the answer style: {style}.
If the context doesn't contain the answer, say "Insufficient information".

Output Format: JSON only
{{
    "answer": "Your comprehensive answer here...",
    "citations": [
        {{ "source": "doc_name", "page": 123, "snippet": "exact quote..." }}
    ]
}}
"""

class AnswerAgent:
    def __init__(self):
        pass

    def answer(self, query: str, context: list, style: str = "Detailed") -> dict:
        if not context:
            return {
                "answer": "Insufficient information in provided sources.",
                "citations": []
            }

        # Prepare Context String
        ctx_str = ""
        for i, hit in enumerate(context):
            meta = hit.payload
            ctx_str += f"\n[Source: {meta.get('doc_name')} | Page: {meta.get('page')}]\n{meta.get('text')}\n"

        # Prepare Messages
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT.format(style=style)},
            {"role": "user", "content": f"User Query: {query}\n\nContext:\n{ctx_str}"}
        ]

        # Call LLM
        # Logic to repair JSON is handled inside `validate.py` in the old code,
        # but here we can try to do it robustly or import the old validator logic.
        # For this upgraded agent, let's keep it simple and clean.
        
        try:
            raw_response = chat_json(messages, max_tokens=2048) # Using 2048 as fixed previously
            return json.loads(raw_response)
        except json.JSONDecodeError:
            # Fallback for malformed JSON (we could add retry here)
            return {
                "answer": "Error generating answer (Invalid JSON).",
                "citations": []
            }
        except Exception as e:
             return {
                "answer": f"Error: {str(e)}",
                "citations": []
            }
