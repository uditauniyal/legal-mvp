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
    # --- logging field (C3) ---
    # WHICH rule selected the corpus, not just which corpus. This is the
    # difference between "it picked BNS" (a fact) and "it picked BNS
    # because the domain fallback fired" (a finding).
    decision_path: str = "unset"

    # Context passed through from Intake
    case_context: Optional[CaseContext] = None

# --- Regex Patterns ---
SEC_RE = re.compile(r'(?i)\b(section|sec|article|art|order|rule)\s+(\d+[A-Za-z]?)')
# Words in the query -> the corpus tag to filter on.
#
# WHAT THESE VALUES MUST MATCH
#   The corpus tags actually written by ingest/registry.py: IPC, BNS, CRPC, CPA.
#   Nothing else exists in the index, so any other value filters to zero results.
#
# WHAT WAS WRONG BEFORE
#   "ipc" -> "BNS".  That was a workaround from when the IPC document was
#   mis-tagged and unreachable: pointing IPC queries at the BNS at least
#   returned something. Now that the IPC is correctly tagged (31.8% of the
#   index), the workaround actively breaks it -- measured live, a query naming
#   "Section 302 IPC" retrieved BNS text at confidence 0.737 (HIGH tier).
#
#   "consumer protection" -> "Unknown".  No chunk has ever carried that tag
#   since the corpus was rebuilt, so consumer queries filtered to zero results,
#   the filter was silently dropped, and search fell back across an index
#   dominated by the largest document. That is the CrPC drift.
#
# NOTE ON DATES
#   A named code is a HINT about what the user believes, not a fact about which
#   law governs. Someone may say "302" out of habit for an offence committed in
#   2025, where the BNS applies. Only the event date settles it. Until the Date
#   Resolver exists, this map takes the user at their word.
ACT_MAP = {
    # penal codes -- kept SEPARATE, which is the whole point
    "ipc": "IPC", "indian penal code": "IPC", "penal code": "IPC",
    "bns": "BNS", "nyaya sanhita": "BNS", "bharatiya nyaya sanhita": "BNS",
    # procedure
    "crpc": "CRPC", "cr.p.c": "CRPC", "criminal procedure": "CRPC",
    "code of criminal procedure": "CRPC",
    "bnss": "CRPC",          # BNSS is not indexed; CrPC is its predecessor
    "nagarik suraksha": "CRPC",
    # consumer
    "consumer protection": "CPA", "consumer court": "CPA",
    "consumer commission": "CPA", "consumer forum": "CPA",
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
        decision_path = "no_match"

        if len(matched_corpora) == 1:
            target_corpus = matched_corpora.pop()
            decision_path = "act_map_single"
        elif len(matched_corpora) > 1:
            target_corpus = None  # Multi-corpus query — search everything
            decision_path = "act_map_multi_no_filter"
            print(f"[Router] Multi-corpus query detected: {matched_corpora} -> no filter")
        
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
                decision_path = "domain_fallback_criminal"
            elif "Civil" in context.predicted_legal_domain:
                target_corpus = None  # Don't filter — search everything for civil queries
                decision_path = "domain_fallback_civil_no_filter"

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
            decision_path=decision_path,
            case_context=context
        )


