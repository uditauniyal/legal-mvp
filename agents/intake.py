from pydantic import BaseModel
from typing import Literal, List, Optional
from clients.openai_client import chat_json
import json

class CaseContext(BaseModel):
    original_query: str
    scenario: str
    user_persona: str # e.g. "Layman", "Paralegal"
    urgency: str # e.g. "Immediate", "Deferred"
    financial_status: str # e.g. "Low Income", "Affluent", "Unknown"
    complexity: str # e.g. "Low", "Medium", "High"
    predicted_legal_domain: str # e.g. "Criminal", "Civil", "Constitutional"
    legal_issues: List[str]
    missing_facts: List[str] # What else should the user have told us?

    # --- logging fields (added for C3) ---
    # These are NOT legal analysis. They record what happened during the
    # LLM call so that a silent failure shows up in the run log.
    llm_ok: bool = True          # did the LLM call succeed?
    fallback_used: bool = False  # were hardcoded defaults substituted?
    llm_error: Optional[str] = None  # what went wrong, if anything
    raw_response_chars: int = 0  # length of what came back, for debugging

INTAKE_SYSTEM_PROMPT = """
You are the "Intake Agent" for a Legal AI. Your goal is to triage the user's legal problem.

### INPUT:
User Query (Natural Language)

### ANALYSIS TASKS:
1. **Scenario**: Summarize the fact pattern in 2-4 words (e.g., "Neighbor Nuisance", "BNS vs IPC Comparison").
    - "Paralegal": 
      * AUTOMATIC TRIGGER: If user cites specific sections/Acts (e.g. "Section 156(3) CrPC", "420 IPC", "BNS").
      * AUTOMATIC TRIGGER: If user cites Case Law or uses "vs." / "versus" (e.g. "Narinder Singh vs. State").
      * AUTOMATIC TRIGGER: If user asks about "Quashing", "FIR Registration", "Bail", "Injunction", or "Writ".
      * AUTOMATIC TRIGGER: If user asks to "Draft" a legal document.
      
    - "Layman": 
      * ONLY if none of the above apply. 
      * Typically vague: "Someone cheated me", "Can I go to jail?", "What are my rights?".

    RULE: Even if the query is a question ("Can I...?"), if it contains technical terms (Sections, Case Names, "Quash"), it is PARALEGAL.
    "My dad is in a coma" -> Layman
    "Can 307 IPC be quashed?" -> Paralegal (Technical terminology override)
3. **Urgency**: Is there an immediate threat to life/liberty/safety or a critical deadline (e.g. arrest imminent)? (Immediate/Deferred).
   - "Immediate": Domestic violence, physical abuse, active cyber-crime, threats of arrest/eviction tonight.
   - "Deferred": General queries, past events.
4. **Financial Status**: Can we infer if they are seeking free aid? (Low Income/Affluent/Unknown).
   - "Low Income": Mentions "no money", "cannot afford lawyer", "legal aid", or very small amounts (e.g. < 10k loan harassment).
   - "Affluent": High value property (> 1Cr), large business disputes, high net worth context.
   - "Unknown": Default.
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
                # 1500, not 600: this model spends output tokens on internal
                # reasoning before the visible answer. Measured 422/600 used
                # on a SIMPLE query, so 600 overflows on hard ones and the
                # truncated JSON fails to parse. See docs/PROJECT_CONTEXT.md
                # -> llm-token-costs.
                max_tokens=1500
            )

            # Robust JSON Extraction: Find first '{' and last '}'
            start = response.find('{')
            end = response.rfind('}')
            
            if start != -1 and end != -1:
                json_str = response[start:end+1]
            else:
                json_str = response # Try parsing raw if no brackets found (risky but better than nothing)
            
            data = json.loads(json_str)
            
            # Map JSON to Pydantic (safety)
            context = CaseContext(
                original_query=query,
                scenario=data.get("scenario", "General Query"),
                user_persona=data.get("Persona", data.get("user_persona", "Layman")), # Handle case sensitivity
                urgency=data.get("Urgency", data.get("urgency", "Deferred")),
                financial_status=data.get("Financial Status", data.get("financial_status", "Unknown")),
                complexity=data.get("Complexity", data.get("complexity", "Medium")),
                predicted_legal_domain=data.get("Domain", data.get("predicted_legal_domain", "General")),
                legal_issues=data.get("Issues", data.get("legal_issues", [])),
                missing_facts=data.get("Missing Facts", data.get("missing_facts", [])),
                llm_ok=True,
                fallback_used=False,
                raw_response_chars=len(response or ""),
            )

        except Exception as e:
            # This branch used to be invisible: it printed to a terminal and
            # carried on with hardcoded defaults. The Router then routed on a
            # domain the LLM never actually produced, and nothing in the
            # response said so. Now it is recorded. See docs/GAPS.md.
            print(f"[Intake] LLM CRASH: {e}")
            context = CaseContext(
                original_query=query,
                scenario="Legal Query",
                user_persona="Layman", # Check below will override this
                urgency="Deferred",
                financial_status="Unknown",
                complexity="Medium", # Assume medium if technical
                predicted_legal_domain="General",
                legal_issues=[],
                missing_facts=[],
                llm_ok=False,
                fallback_used=True,
                llm_error=f"{type(e).__name__}: {e}",
            )
            return self._apply_paralegal_override(context, query)

        # Apply override to the successful LLM result too (in case LLM was lazy)
        return self._apply_paralegal_override(context, query)

    def _apply_paralegal_override(self, context: CaseContext, query: str) -> CaseContext:
        """Force Paralegal persona if technical keywords are found in the query."""
        import re
        
        # Keywords that strongly suggest a legal professional or student
        triggers = [
            r"Section\s+\d+",    # Section 156
            r"Order\s+\d+",      # Order 39
            r"Article\s+\d+",    # Article 226
            r"vs\.",             # Case law vs.
            r"versus",           # Case law versus
            r"Quash",            # Quashing
            r"FIR",              # FIR
            r"Bail",             # Bail
            r"Writ",             # Writ petition
            r"Jurisdiction",     # Jurisdiction
            r"Cognizance",       # Cognizance
            r"Draft",            # Draft application
            r"CrPC",             # Code of Criminal Procedure
            r"IPC",              # Indian Penal Code
            r"CPC",              # Civil Procedure Code
            r"BNS",              # Bharatiya Nyaya Sanhita
        ]
        
        for pattern in triggers:
            if re.search(pattern, query, re.IGNORECASE):
                # Detected technical term -> Force Paralegal
                # We create a new copy with updated persona
                return context.model_copy(update={"user_persona": "Paralegal"})
        
        return context
