from clients.qdrant_client import qdrant, ensure_collection, COLLECTION
from clients.openai_client import embed_texts
from qdrant_client.models import PointStruct

def index_chunks(chunks: list[dict]):
    client = qdrant()
    ensure_collection(client)
    BATCH = 64
    for i in range(0, len(chunks), BATCH):
        batch = chunks[i:i+BATCH]
        vecs = embed_texts([c["text"] for c in batch])
        points = [PointStruct(id=c["chunk_id"], vector=v, payload=c) for c, v in zip(batch, vecs)]
        client.upsert(collection_name=COLLECTION, points=points)
