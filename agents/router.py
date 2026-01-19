import re
from typing import Literal, Optional, List
from pydantic import BaseModel

# --- Data Models ---
class QueryPlan(BaseModel):
    original_query: str
    rewritten_query: str
    intent: Literal["statute", "case_law", "comparison", "general"]
    target_corpus: Optional[str] = None  # "BNS", "BNSS", "IPC", "Constitution", etc.
    entities: List[str] = []
    boost_terms: List[str] = []

# --- Regex Patterns ---
# Detects "Section 41", "Article 21", "Order 39 Rule 1"
SEC_RE = re.compile(r'(?i)\b(section|sec|article|art|order|rule)\s+(\d+[A-Za-z]?)')
# Detects specific act names
ACT_MAP = {
    "ipc": "BNS", "bns": "BNS", "penal code": "BNS",
    "crpc": "BNSS", "bnss": "BNSS", "criminal procedure": "BNSS",
    "iea": "BSA", "bsa": "BSA", "evidence act": "BSA",
    "constitution": "Constitution"
}
# Detects case law indicators
CASE_RE = re.compile(r'(?i)(\s+v\.\s+|\s+vs\.\s+|judgment|appeal|petition|scc|air\s+\d+)')

class RouterAgent:
    def __init__(self):
        pass

    def route(self, query: str) -> QueryPlan:
        q_lower = query.lower()
        intent = "general"
        target_corpus = None
        entities = []
        boosts = []

        # 1. Detect Corpus (Statute)
        for key, corpus in ACT_MAP.items():
            if key in q_lower:
                target_corpus = corpus
                break
        
        # 2. Extract Entities (Section numbers)
        sec_matches = SEC_RE.findall(query)
        for label, num in sec_matches:
            # Standardize "Section 41"
            normalized = f"{label.capitalize()} {num}"
            entities.append(normalized)
            boosts.append(normalized)
            # High priority boost
            boosts.append(f"{label.capitalize()} {num}.") 
            intent = "statute"

        # 3. Detect Case Law
        if CASE_RE.search(query):
            intent = "case_law"
            target_corpus = "Judgments"

        # 4. Fallback Logic
        if target_corpus and intent == "general":
            # If user mentioned an Act (e.g. "IPC") but no section, it's still a legal statute query
            intent = "statute"


        # 5. Comparison Logic (Simple)
        if "difference between" in q_lower or " vs " in q_lower:
            if intent == "statute":
                intent = "comparison"

        # Construct Rewritten Query
        # We prepend boosts to make them prominent for vector search (if simple concatenation)
        # But for valid SQL-like filtering, we use the structured 'target_corpus'
        rewritten = query
        if boosts:
            rewritten = f"{' '.join(boosts)} {query}"

        return QueryPlan(
            original_query=query,
            rewritten_query=rewritten,
            intent=intent,
            target_corpus=target_corpus,
            entities=entities,
            boost_terms=boosts
        )
