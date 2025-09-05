from clients.qdrant_client import qdrant, ensure_collection, COLLECTION
from clients.openai_client import embed_texts
from qdrant_client.models import PointStruct
import uuid


def index_chunks(chunks: list[dict]):
    """Embed and index document chunks into Qdrant with safe UUID IDs."""
    client = qdrant()
    ensure_collection(client)

    BATCH = 64
    for i in range(0, len(chunks), BATCH):
        batch = chunks[i:i+BATCH]

        # Embed texts for the batch
        vecs = embed_texts([c["text"] for c in batch])

        # Assign UUIDs as IDs, keep original chunk_id in payload
        points = [
            PointStruct(
                id=str(uuid.uuid4()),   # ✅ safe unique UUID
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
