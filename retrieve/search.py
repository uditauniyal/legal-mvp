from clients.qdrant_client import qdrant, COLLECTION
from qdrant_client.models import Filter

def search(vec: list[float], top_k=24, payload_filter=None):
    client = qdrant()
    flt = Filter(**payload_filter) if payload_filter else None
    res = client.search(collection_name=COLLECTION, query_vector=vec, with_payload=True,
                        limit=top_k, query_filter=flt)
    return res
