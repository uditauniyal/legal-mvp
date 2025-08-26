def build_snippets(points):
    out = []
    for idx, p in enumerate(points, start=1):
        payload = p.payload
        snippet = payload.get("text","").strip().replace("\n"," ")
        out.append({
            "n": idx,
            "source": payload["doc_name"],
            "page": payload.get("page", 1),
            "snippet": snippet[:900]
        })
    return out
