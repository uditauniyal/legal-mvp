from dataclasses import dataclass, field
from typing import List, Any, Optional

from clients.qdrant_client import qdrant, COLLECTION
from clients.openai_client import embed_one
from qdrant_client.models import Filter
from agents.router import QueryPlan

from core.citations import named_statutes
from core.recodification import CORPORA_IN_INDEX

# --- Filtering thresholds ---
MIN_SCORE_FLOOR = 0.35       # Absolute floor — below this, chunks are noise
ADAPTIVE_DROP = 0.15         # Keep chunks within this range of top score

# --- Refusal ---
#
# WHY THERE IS NO MEANINGFUL SCORE THRESHOLD HERE
#     Measured on this index with 15 probe queries:
#
#         in corpus,     lowest max score   0.278  ("my landlord is not
#                                                    returning my deposit" —
#                                                    the CPA IS indexed)
#         out of corpus, highest max score  0.519  ("grounds for divorce under
#                                                    the Hindu Marriage Act" —
#                                                    never indexed)
#
#     The out-of-corpus query scores HIGHER than five of six legitimate ones.
#     The distributions are inverted, not merely overlapping, so any cutoff
#     that rejects the Hindu Marriage Act query also rejects most real work.
#     This is why an out-of-corpus Negotiable Instruments query previously came
#     back at HIGH confidence 0.73: the score carried no information about
#     whether we hold the law, and nothing else was being consulted.
#
#     So the floor below is set only where non-legal input separates cleanly
#     (nonsense queries topped out at 0.208). It is a garbage filter, NOT a
#     corpus-boundary check, and must never be described as one.
#
#     The corpus boundary is checked by NAME instead — see the gate in
#     retrieve(). That is deterministic where the score is not.
NONSENSE_FLOOR = 0.25

# Value of the entity-coverage signal when no entity could be extracted.
# 0.5 = "unknown", not 1.0 = "perfect". See the comment at its use site.
ENTITY_NEUTRAL = 0.5


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

    # --- logging fields (C3) ---
    scores_raw: List[float] = field(default_factory=list)
    #   Every score BEFORE filtering. Saved so the confidence ablation can be
    #   recomputed offline from the log, with no re-querying and no cost.
    filter_fallback_fired: bool = False
    #   True when the corpus filter matched nothing and was silently dropped.
    #   This is the mechanism behind the CrPC drift (docs/GAPS.md #5).
    entity_coverage_default_used: bool = False
    #   True when no entity was extracted and the signal fell back to its
    #   neutral value. It used to default to 1.0, handing out the full 0.30
    #   weight for free (docs/GAPS.md #2); it is now ENTITY_NEUTRAL.
    filter_applied: Optional[str] = None
    embed_provider: Optional[str] = None

    # --- corpus boundary (E7) ---
    named_statutes: List[str] = field(default_factory=list)
    #   Every Act named in the query, whether or not a section was cited.
    unavailable_statutes: List[str] = field(default_factory=list)
    #   Those we never indexed. Deterministic, unlike the similarity score.
    refusal_reason: Optional[str] = None
    #   None, "out_of_corpus_statute", "below_nonsense_floor", or
    #   "no_chunks". Recorded so refusals can be counted BY CAUSE — a gate
    #   that fires for the wrong reason is not a working gate.
    partial_corpus_coverage: bool = False
    #   The query named several Acts and we hold only some. Answerable, but
    #   the answer is structurally incomplete and must say so.


def compute_confidence(scores: list, entities: list, chunks: list) -> dict:
    """Composite confidence: top-5 mean + entity coverage + score gap analysis."""
    if not scores:
        return {"confidence": 0.0, "top_k_mean": 0.0, "score_gap": 0.0,
                "entity_coverage": 0.0, "entity_coverage_default_used": not entities}

    top_k = sorted(scores, reverse=True)[:5]

    # Signal 1: Top-k mean (what your best retrievals look like)
    top_k_mean = sum(top_k) / len(top_k)

    # Signal 2: Score drop-off (small gap = consistent relevance)
    score_gap = top_k[0] - top_k[-1] if len(top_k) > 1 else 0.0

    # Signal 3: Entity coverage (did we find chunks mentioning the entities?)
    default_used = not entities
    if entities:
        # COUNT ENTITIES FOUND, NOT CHUNKS THAT MATCHED.
        #
        # This used to iterate over chunks[:5] and divide by len(entities),
        # which counts different things on each side of the division. One
        # entity found in all five chunks gave 5/1 = 5.0 for a value that is
        # weighted at 0.30 in a composite capped at 1.0 -- so the cap silently
        # absorbed the error and the score looked plausible.
        #
        # The question this signal is meant to answer is "how much of what the
        # user asked about did we actually find?", so the numerator must be
        # entities, and the value is then bounded to [0, 1] by construction.
        haystack = " ".join(c.payload.get("text", "") for c in chunks[:5]).lower()
        entity_hits = sum(1 for e in entities if e.lower() in haystack)
        entity_coverage = entity_hits / len(entities)
    else:
        # NO ENTITY EXTRACTED -> the signal is UNKNOWN, not perfect.
        #
        # This used to be 1.0, which handed the signal's full 0.30 weight to
        # every query that named no section. Since the HIGH tier begins at
        # 0.55, that free 0.30 alone carried mediocre retrieval over the line
        # -- and layman queries, the ones this project exists for, name a
        # section almost never. The system was therefore most confident
        # exactly where it had the least evidence.
        #
        # ENTITY_NEUTRAL is the midpoint: it neither rewards nor punishes a
        # query for a signal that could not be computed. The flag below is
        # logged on every run so the ablation can recompute either version
        # offline without re-querying.
        entity_coverage = ENTITY_NEUTRAL

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
        "entity_coverage_default_used": default_used,
    }


class RetrievalAgent:
    def __init__(self):
        self.client = qdrant()

    def retrieve(self, plan: QueryPlan, limit: int = 15) -> RetrievalResult:
        # 1. Embed the query
        # embed_one returns (vector, CallMeta); the meta records which provider
        # actually served the request, which the run log needs.
        q_vec, self.last_embed_meta = embed_one(plan.rewritten_query)

        # 2. Build Filter
        #
        # target_corpora (a list) wins over target_corpus (a single value)
        # when set. Qdrant expresses "any of these" as match:{any:[...]},
        # which is what continuing conduct needs: incidents either side of
        # 1 July 2024 answer to different codes, so both must be searchable
        # in one pass rather than by running the query twice and merging.
        corpora = list(plan.target_corpora or ([plan.target_corpus] if plan.target_corpus else []))
        must_filters = []
        if len(corpora) == 1:
            must_filters.append({"key": "corpus", "match": {"value": corpora[0]}})
        elif len(corpora) > 1:
            must_filters.append({"key": "corpus", "match": {"any": corpora}})
        payload_filter = {"must": must_filters} if must_filters else None
        flt = Filter(**payload_filter) if payload_filter else None

        # 3. Search Qdrant
        print(f"[Retrieval] Query: '{plan.rewritten_query[:80]}...' "
              f"| Filter: {corpora or None}")
        res = self.client.search(
            collection_name=COLLECTION,
            query_vector=q_vec,
            query_filter=flt,
            limit=limit,
            with_payload=True
        )

        # 4. Fallback: no results with filter → try without
        filter_fallback_fired = False
        if not res and corpora:
            # The filter matched nothing, so we drop it entirely. Previously
            # this happened silently; now it is recorded, because an
            # unfiltered search runs over an index that is ~48% CrPC and the
            # base rate alone then dominates the results.
            filter_fallback_fired = True
            print(f"[Retrieval] No results with filter {corpora}. Searching all...")
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
        # NOTE: all_scores is in RERANKED order, not descending score order.
        # Kept that way deliberately so the log shows what the pipeline
        # actually produced -- but it means positional access is never safe
        # here. Anything wanting "the best score" must ask for the maximum.
        all_scores = [hit.score for hit in res] if res else []
        if res:
            # Was res[0].score. Step 5 above moves entity-matching hits to the
            # front REGARDLESS of score, so res[0] is the reranked winner, not
            # the highest-scoring chunk. With a promoted hit at 0.31 and a real
            # best of 0.58, the adaptive threshold fell by 0.27 and the filter
            # stopped filtering -- quietly widening every affected result set.
            top_score = max(all_scores)
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

        # 8. Corpus boundary gate.
        #
        # Checked by NAME, not by score, for the reason documented at
        # NONSENSE_FLOOR above: similarity cannot separate "we do not hold
        # this Act" from "this is a hard question about an Act we do hold".
        #
        # Refuse only when EVERY Act the user named is missing. A query naming
        # both the IPC and the NI Act is partly answerable, and refusing it
        # outright would be worse than answering the half we can while saying
        # which half is missing.
        named = named_statutes(getattr(plan, "original_query", "") or "")
        unavailable = sorted(named - set(CORPORA_IN_INDEX))
        gate_fired = bool(named) and len(unavailable) == len(named)
        partial = bool(unavailable) and not gate_fired

        max_score = max(all_scores) if all_scores else 0.0

        if len(filtered) == 0:
            refused, reason = True, "no_chunks"
        elif gate_fired:
            refused, reason = True, "out_of_corpus_statute"
        elif max_score < NONSENSE_FLOOR:
            refused, reason = True, "below_nonsense_floor"
        else:
            refused, reason = False, None

        if unavailable:
            print(f"[Retrieval] Named statutes {sorted(named)}; "
                  f"not in corpus: {unavailable}"
                  f"{' -> REFUSING' if gate_fired else ' -> partial coverage'}")

        print(f"[Retrieval] Confidence: {conf['confidence']:.4f} "
              f"(top5={conf['top_k_mean']:.3f}, gap={conf['score_gap']:.3f}, "
              f"entity={conf['entity_coverage']:.2f}) | "
              f"Chunks: {len(filtered)} | Refused: {refused}"
              f"{' (' + reason + ')' if reason else ''}")

        return RetrievalResult(
            chunks=filtered,
            confidence=conf["confidence"],
            top_k_mean=conf["top_k_mean"],
            score_gap=conf["score_gap"],
            entity_coverage=conf["entity_coverage"],
            # Same reranking hazard as the threshold above: all_scores[0] is
            # the first RERANKED hit, not the maximum.
            max_score=round(max_score, 4),
            total_chunks=len(filtered),
            total_retrieved=total_retrieved,
            refused=refused,
            refusal_reason=reason,
            named_statutes=sorted(named),
            unavailable_statutes=unavailable,
            partial_corpus_coverage=partial,
            scores_raw=[round(float(x), 6) for x in all_scores],
            filter_fallback_fired=filter_fallback_fired,
            entity_coverage_default_used=conf.get("entity_coverage_default_used", False),
            filter_applied=(corpora[0] if len(corpora) == 1 else corpora or None),
            embed_provider=getattr(self.last_embed_meta, "provider_name", None),
        )

