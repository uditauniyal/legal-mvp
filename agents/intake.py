from pydantic import BaseModel
from typing import Literal, List, Optional
from clients.openai_client import chat_json
import json

class CaseContext(BaseModel):
    original_query: str
    scenario: str
    user_persona: Literal["Layman", "Paralegal"]
    urgency: Literal["Immediate", "Deferred"]
    financial_status: Literal["Low Income", "Affluent", "Unknown"]
    complexity: Literal["Low", "Medium", "High"]
    predicted_legal_domain: str # e.g. "Criminal", "Civil", "Constitutional"
    legal_issues: List[str]
    missing_facts: List[str] # What else should the user have told us?

INTAKE_SYSTEM_PROMPT = """
You are the "Intake Agent" for a Legal AI. Your goal is to triage the user's legal problem.

### INPUT:
User Query (Natural Language)

### ANALYSIS TASKS:
1. **Scenario**: Summarize the fact pattern in 2-4 words (e.g., "Neighbor Nuisance", "BNS vs IPC Comparison").
2. **Persona**: 
   - "Paralegal": If the query cites specific sections (e.g. "Section 133"), Acts (CrPC/BNS), asks for "Analysis", "Drafting", or comparisons ("vs"). 
   - "Layman": If the query describes a problem in plain language (e.g. "My neighbor is annoying").
3. **Urgency**: Is there an immediate threat to life/liberty or deadline? (Immediate/Deferred).
4. **Financial Status**: Can we infer if they are seeking free aid? (Low Income/Unknown).
5. **Complexity**: 
   - "High": Comparative analysis (BNS vs IPC), Constitutional queries.
   - "Medium": Specific procedural queries.
   - "Low": Simple fact-based questions.
6. **Domain**: Criminal, Civil, Family, Corporate, Constitutional, etc.
7. **Issues**: List potential legal causes of action.
8. **Missing Facts**: What vital info is missing?

### OUTPUT:
Return ONLY a JSON object matching the CaseContext schema.
"""

class IntakeAgent:
    def analyze(self, query: str) -> CaseContext:
        try:
            response = chat_json(
                messages=[
                    {"role": "system", "content": INTAKE_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Query: {query}"}
                ],
                model="gpt-4o",
                max_tokens=600
            )
            data = json.loads(response)
            
            # Map JSON to Pydantic (safety)
            return CaseContext(
                original_query=query,
                scenario=data.get("scenario", "General Query"),
                user_persona=data.get("Persona", data.get("user_persona", "Layman")), # Handle case sensitivity
                urgency=data.get("Urgency", data.get("urgency", "Deferred")),
                financial_status=data.get("Financial Status", data.get("financial_status", "Unknown")),
                complexity=data.get("Complexity", data.get("complexity", "Medium")),
                predicted_legal_domain=data.get("Domain", data.get("predicted_legal_domain", "General")),
                legal_issues=data.get("Issues", data.get("legal_issues", [])),
                missing_facts=data.get("Missing Facts", data.get("missing_facts", []))
            )
        except Exception as e:
            print(f"[Intake] LLM Error: {e}")
            # Fallback
            return CaseContext(
                original_query=query,
                scenario="General Legal Query",
                user_persona="Layman",
                urgency="Deferred",
                financial_status="Unknown",
                complexity="Low",
                predicted_legal_domain="General",
                legal_issues=[],
                missing_facts=[]
            )
