from clients.qdrant_client import qdrant, COLLECTION
from clients.openai_client import embed_texts
from qdrant_client.models import Filter

client = qdrant()

query = "punishment" # Generic query
print(f"Querying generic term to check BNS presence...")

try:
    # 1. Embed
    q_vec = embed_texts([query])[0]
    
    # 2. Filter for BNS
    payload_filter = {"must": [{"key":"corpus","match":{"value": "BNS"}}]}
    flt = Filter(**payload_filter)
    
    # 3. Search
    res = client.search(
        collection_name=COLLECTION, 
        query_vector=q_vec, 
        query_filter=flt,
        limit=5,
        with_payload=True
    )
    
    print(f"BNS Docs Found: {len(res)}")
    with open("debug_output.txt", "w", encoding="utf-8") as f:
        f.write(f"BNS Search Results: {len(res)}\n")
        if len(res) == 0:
            f.write("No documents found with corpus='BNS'.\n")
        for i, hit in enumerate(res):
            f.write(f"\n[{i+1}] {hit.payload.get('doc_name')} (Score: {hit.score})\n")

except Exception as e:
    import traceback
    traceback.print_exc()
