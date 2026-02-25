import re
from typing import Literal, Optional, List
from pydantic import BaseModel
from agents.intake import CaseContext

# --- Data Models ---
class QueryPlan(BaseModel):
    original_query: str
    rewritten_query: str
    intent: Literal["statute", "case_law", "comparison", "general"]
    target_corpus: Optional[str] = None
    entities: List[str] = []
    boost_terms: List[str] = []
    # Context passed through from Intake
    case_context: Optional[CaseContext] = None

# --- Regex Patterns ---
SEC_RE = re.compile(r'(?i)\b(section|sec|article|art|order|rule)\s+(\d+[A-Za-z]?)')
ACT_MAP = {
    "ipc": "BNS", "bns": "BNS", "penal code": "BNS", "nyaya sanhita": "BNS",
    "crpc": "BNSS", "bnss": "BNSS", "criminal procedure": "BNSS",
    "iea": "BSA", "bsa": "BSA", "evidence act": "BSA",
    "constitution": "Constitution",
    "consumer protection": "Unknown",
}
CASE_RE = re.compile(r'(?i)(\s+v\.\s+|\s+vs\.\s+|judgment|appeal|petition|scc|air\s+\d+)')

class RouterAgent:
    def route(self, context: CaseContext) -> QueryPlan:
        query = context.original_query
        q_lower = query.lower()
        intent = "general"
        target_corpus = None
        entities = []
        boosts = []

        # 1. Corpus Mapping — collect ALL matching corpora
        matched_corpora = set()
        for key, corpus in ACT_MAP.items():
            if key in q_lower:
                matched_corpora.add(corpus)

        # If exactly ONE corpus matched, use it as a filter
        # If MULTIPLE matched (e.g., "IPC" + "CrPC"), don't filter — search everything
        if len(matched_corpora) == 1:
            target_corpus = matched_corpora.pop()
        elif len(matched_corpora) > 1:
            target_corpus = None  # Multi-corpus query — search everything
            print(f"[Router] Multi-corpus query detected: {matched_corpora} → no filter")
        
        # 2. Extract Entities
        sec_matches = SEC_RE.findall(query)
        for label, num in sec_matches:
            normalized = f"{label.capitalize()} {num}"
            entities.append(normalized)
            boosts.append(normalized)
            boosts.append(f"{label.capitalize()} {num}.") 
            intent = "statute"

        # 3. Case Law Detection
        if CASE_RE.search(query) or "judgment" in q_lower:
            intent = "case_law"
            # Don't force target_corpus to "Judgments" — we may not have judgment docs
            # Let vector similarity find the most relevant statutory provisions instead

        # 4. Fallback based on Domain from Intake (only if no corpus matched at all)
        if not target_corpus and not matched_corpora:
            if "Criminal" in context.predicted_legal_domain:
                target_corpus = "BNS"
            elif "Civil" in context.predicted_legal_domain:
                target_corpus = None  # Don't filter — search everything for civil queries

        # 5. Enrich Context with Intake Issues
        boosts.extend(context.legal_issues)

        # 6. Rewriting
        rewritten = query
        if boosts:
             rewritten = f"{' '.join(context.legal_issues)} {' '.join(entities)} {query}"

        print(f"[Router] Intent: {intent} | Corpus: {target_corpus} | Entities: {entities}")

        return QueryPlan(
            original_query=query,
            rewritten_query=rewritten,
            intent=intent,
            target_corpus=target_corpus,
            entities=entities,
            boost_terms=boosts,
            case_context=context
        )


