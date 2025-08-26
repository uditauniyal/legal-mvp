from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from core.config import QDRANT_URL, QDRANT_API_KEY

COLLECTION = "legal_mvp"

def qdrant():
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

def ensure_collection(client, dim=1536):
    collections = [c.name for c in client.get_collections().collections]
    if COLLECTION not in collections:
        client.recreate_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
