from clients.qdrant_client import qdrant, COLLECTION
from clients.openai_client import embed_texts
from qdrant_client.models import Filter

client = qdrant()

query = "Section 41A"
print(f"Querying: {query}")

try:
    # 1. Embed
    q_vec = embed_texts([query])[0]
    
    # 2. Filter (mimic decision_agent)
    payload_filter = {"must": [{"key":"corpus","match":{"value": "BNSS"}}]}
    flt = Filter(**payload_filter)
    
    # 3. Search
    res = client.search(
        collection_name=COLLECTION, 
        query_vector=q_vec, 
        query_filter=flt,
        limit=20,
        with_payload=True
    )
    
    with open("debug_output.txt", "w", encoding="utf-8") as f:
        f.write(f"Search results for '{query}': {len(res)}\n")
        found = False
        for i, hit in enumerate(res):
            text = hit.payload.get('text', '')
            f.write(f"\n[{i+1}] Score: {hit.score}\n")
            f.write(f"Page: {hit.payload.get('page')}\n")
            f.write(f"Text: {text[:200]}...\n")
            
            if "41A" in text:
                f.write(" [MATCH FOUND in text]\n")
                found = True

except Exception as e:
    import traceback
    traceback.print_exc()
