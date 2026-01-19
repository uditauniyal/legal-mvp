from clients.qdrant_client import qdrant, COLLECTION
from clients.openai_client import embed_texts
from qdrant_client.models import Filter, PointStruct
from agents.router import QueryPlan

class RetrievalAgent:
    def __init__(self):
        self.client = qdrant()

    def retrieve(self, plan: QueryPlan, limit: int = 15):
        # 1. Embed the query (use rewritten for better context)
        q_vec = embed_texts([plan.rewritten_query])[0]

        # 2. Build Filter
        must_filters = []
        if plan.target_corpus:
            must_filters.append({"key": "corpus", "match": {"value": plan.target_corpus}})
        
        # Add boosts as strict filters? No, boosts are for ranking.
        # But if we have specific "entities" (Section 41), we might want to ensure we get them.
        # For now, rely on vector similarity + Boost terms in the query string.

        payload_filter = {"must": must_filters} if must_filters else None
        flt = Filter(**payload_filter) if payload_filter else None

        # 3. Search
        print(f"[Retrieval] Searching for: '{plan.rewritten_query}' | Filter: {plan.target_corpus}")
        res = self.client.search(
            collection_name=COLLECTION,
            query_vector=q_vec,
            query_filter=flt,
            limit=limit,
            with_payload=True
        )

        # 4. Fallback: If no results with filter, try without filter (General Search)
        if not res and plan.target_corpus:
            print(f"[Retrieval] No results with filter. Relaxing filter...")
            res = self.client.search(
                collection_name=COLLECTION,
                query_vector=q_vec,
                limit=limit,
                with_payload=True
            )

        # 5. Reranking (Logical)
        # If we have specific entities (e.g. "Section 41"), prioritize chunks that mention them explicitly.
        if plan.entities:
            # Simple client-side re-ranking
            # Move exact matches of "Section 41" to the top
            prioritized = []
            others = []
            for hit in res:
                text = hit.payload.get("text", "").lower()
                # Check if any entity is in the text
                if any(e.lower() in text for e in plan.entities):
                    prioritized.append(hit)
                else:
                    others.append(hit)
            res = prioritized + others

        return res
