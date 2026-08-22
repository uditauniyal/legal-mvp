from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from core.config import QDRANT_URL, QDRANT_API_KEY, COLLECTION, EMBED_DIM

# COLLECTION and EMBED_DIM now come from core.config so that the collection
# name and the vector size cannot drift away from the embedding model that
# produced them. Changing EMBED_MODEL means a new collection, not a reused one.

def qdrant():
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

def ensure_collection(client, dim=EMBED_DIM):
    collections = [c.name for c in client.get_collections().collections]
    if COLLECTION not in collections:
        client.recreate_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
