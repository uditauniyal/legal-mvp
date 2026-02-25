from dataclasses import dataclass, field
from typing import List, Any

from clients.qdrant_client import qdrant, COLLECTION
from clients.openai_client import embed_texts
from qdrant_client.models import Filter
from agents.router import QueryPlan

# --- Filtering thresholds ---
MIN_SCORE_FLOOR = 0.35       # Absolute floor — below this, chunks are noise
ADAPTIVE_DROP = 0.15         # Keep chunks within this range of top score


@dataclass
class RetrievalResult:
    """Wraps retrieved chunks with quality metadata."""
    chunks: List[Any] = field(default_factory=list)
    confidence: float = 0.0       # 0.0–1.0 composite confidence
    top_k_mean: float = 0.0       # Mean of top-5 scores
    score_gap: float = 0.0        # Gap between best and 5th score
    entity_coverage: float = 0.0  # Fraction of entities found in top chunks
    max_score: float = 0.0
    total_chunks: int = 0         # Chunks passed to LLM (after filtering)
    total_retrieved: int = 0      # Raw chunks from Qdrant (before filtering)
    refused: bool = False         # True ONLY if zero usable results


def compute_confidence(scores: list, entities: list, chunks: list) -> dict:
    """Composite confidence: top-5 mean + entity coverage + score gap analysis."""
    if not scores:
        return {"confidence": 0.0, "top_k_mean": 0.0, "score_gap": 0.0, "entity_coverage": 0.0}

    top_k = sorted(scores, reverse=True)[:5]

    # Signal 1: Top-k mean (what your best retrievals look like)
    top_k_mean = sum(top_k) / len(top_k)

    # Signal 2: Score drop-off (small gap = consistent relevance)
    score_gap = top_k[0] - top_k[-1] if len(top_k) > 1 else 0.0

    # Signal 3: Entity coverage (did we find chunks mentioning the entities?)
    if entities:
        entity_hits = sum(
            1 for c in chunks[:5]
            if any(e.lower() in c.payload.get("text", "").lower() for e in entities)
        )
        entity_coverage = entity_hits / len(entities)
    else:
        entity_coverage = 1.0  # No entities to match — neutral

    # Weighted composite
    gap_penalty = min(score_gap / 0.3, 1.0)  # Normalize gap to 0–1
    confidence = (
        0.55 * top_k_mean +
        0.15 * (1.0 - gap_penalty) +
        0.30 * entity_coverage
    )

    return {
        "confidence": round(min(confidence, 1.0), 4),
        "top_k_mean": round(top_k_mean, 4),
        "score_gap": round(score_gap, 4),
        "entity_coverage": round(entity_coverage, 4),
    }


class RetrievalAgent:
    def __init__(self):
        self.client = qdrant()

    def retrieve(self, plan: QueryPlan, limit: int = 15) -> RetrievalResult:
        # 1. Embed the query
        q_vec = embed_texts([plan.rewritten_query])[0]

        # 2. Build Filter
        must_filters = []
        if plan.target_corpus:
            must_filters.append({"key": "corpus", "match": {"value": plan.target_corpus}})
        payload_filter = {"must": must_filters} if must_filters else None
        flt = Filter(**payload_filter) if payload_filter else None

        # 3. Search Qdrant
        print(f"[Retrieval] Query: '{plan.rewritten_query[:80]}...' | Filter: {plan.target_corpus}")
        res = self.client.search(
            collection_name=COLLECTION,
            query_vector=q_vec,
            query_filter=flt,
            limit=limit,
            with_payload=True
        )

        # 4. Fallback: no results with filter → try without
        if not res and plan.target_corpus:
            print(f"[Retrieval] No results with filter '{plan.target_corpus}'. Searching all...")
            res = self.client.search(
                collection_name=COLLECTION,
                query_vector=q_vec,
                limit=limit,
                with_payload=True
            )

        total_retrieved = len(res)

        # 5. Reranking — prioritize entity matches (before filtering)
        if plan.entities and res:
            prioritized = []
            others = []
            for hit in res:
                text = hit.payload.get("text", "").lower()
                if any(e.lower() in text for e in plan.entities):
                    prioritized.append(hit)
                else:
                    others.append(hit)
            res = prioritized + others

        # 6. Score-based chunk filtering (adaptive + floor)
        all_scores = [hit.score for hit in res] if res else []
        if res:
            top_score = res[0].score
            adaptive_threshold = max(top_score - ADAPTIVE_DROP, MIN_SCORE_FLOOR)
            filtered = [hit for hit in res if hit.score >= adaptive_threshold]
            # Ensure at least 3 chunks pass (avoid over-filtering)
            if len(filtered) < 3 and len(res) >= 3:
                filtered = res[:3]
            print(f"[Retrieval] {total_retrieved} raw -> {len(filtered)} after filter "
                  f"(threshold={adaptive_threshold:.3f}) | "
                  f"Scores: {[round(s, 3) for s in all_scores[:5]]}...")
        else:
            filtered = []
            print(f"[Retrieval] 0 chunks returned from Qdrant")

        # 7. Compute composite confidence
        conf = compute_confidence(all_scores, plan.entities, res)

        # Only refuse when zero usable chunks
        refused = len(filtered) == 0

        print(f"[Retrieval] Confidence: {conf['confidence']:.4f} "
              f"(top5={conf['top_k_mean']:.3f}, gap={conf['score_gap']:.3f}, "
              f"entity={conf['entity_coverage']:.2f}) | "
              f"Chunks: {len(filtered)} | Refused: {refused}")

        return RetrievalResult(
            chunks=filtered,
            confidence=conf["confidence"],
            top_k_mean=conf["top_k_mean"],
            score_gap=conf["score_gap"],
            entity_coverage=conf["entity_coverage"],
            max_score=round(all_scores[0], 4) if all_scores else 0.0,
            total_chunks=len(filtered),
            total_retrieved=total_retrieved,
            refused=refused,
        )

