from clients.qdrant_client import qdrant, ensure_collection, COLLECTION
from clients.openai_client import embed_texts
from qdrant_client.models import PointStruct
import uuid

# A fixed namespace for uuid5. uuid5 turns a NAME into a UUID
# deterministically: the same name always yields the same UUID. That is
# what makes re-ingestion replace rather than duplicate.
CHUNK_NAMESPACE = uuid.UUID("6f1c2a7e-9b41-4f5d-8a3c-1e7d0b2f4a56")


def index_chunks(chunks: list[dict]):
    """Embed and index document chunks into Qdrant with safe UUID IDs."""
    client = qdrant()
    ensure_collection(client)

    BATCH = 64
    for i in range(0, len(chunks), BATCH):
        batch = chunks[i:i+BATCH]

        # Embed texts for the batch.
        # embed_texts returns (vectors, CallMeta) — meta is discarded here
        # because ingest is not part of the per-query run log.
        vecs, _meta = embed_texts([c["text"] for c in batch])

        # Assign UUIDs as IDs, keep original chunk_id in payload
        points = [
            PointStruct(
                # Derived from chunk_id, NOT random. uuid4() here produced
                # 618 duplicate chunks (34% of the index) because every
                # ingest generated fresh ids and upsert had nothing to match.
                id=str(uuid.uuid5(CHUNK_NAMESPACE, c["chunk_id"])),
                vector=v,
                payload={
                    **c,
                    "original_chunk_id": c.get("chunk_id")  # keep original for traceability
                }
            )
            for c, v in zip(batch, vecs)
        ]

        # Upsert to Qdrant
        client.upsert(collection_name=COLLECTION, points=points)
