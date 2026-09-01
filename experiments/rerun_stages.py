"""Option A -- re-run RETRIEVAL ONLY, capturing all three stages with section_number.

WHY THIS EXISTS
    The original run logs store chunk records with five keys:
        doc, page, corpus, score, text_head
    There is no section_number. It exists in the Qdrant payload but was never
    copied into the log. Two recovery routes both fail: (doc,page) is ambiguous
    for 76% of keys, and text_head identifies only 80.9% of passages because
    19.1% begin mid-provision ("Explanation.-A threat to injure...").

    That 19.1% IS the counting bug. Without this re-run the fix cannot be
    verified, only assumed.

WHAT IT REPLAYS, AND WHY
    It replays the filter each query ACTUALLY received, read from
    retrieval.filter_applied in the log -- it does NOT recompute the filter
    from the Router. Recomputing risks choosing a different filter, which
    would make Stage C incomparable by construction and defeat the whole
    point of the reproducibility check.

THE THREE STAGES
    A  raw_15       what Qdrant returned, in score order
    B  reranked_15  same 15, reordered by entity match (score order destroyed)
    C  filtered_n   what survived the adaptive filter and reached the model

NO GENERATION. Embeddings only. ~859 short queries, about 6 paise.
Writes ONLY to experiments/stages.jsonl. Never touches runs/ or backup/.
"""
import json, io, sys, glob, collections
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, ".")

from clients.openai_client import embed_texts
from clients.qdrant_client import COLLECTION, qdrant
from qdrant_client.models import Filter

OUT = Path("experiments/stages.jsonl")
MIN_SCORE_FLOOR, ADAPTIVE_DROP = 0.35, 0.15      # copied from agents/retriever.py

# ---- load server log, dedupe on (query_id, intervention-ish key) -------------
rows = []
for f in glob.glob("runs/*/queries.jsonl"):
    for l in open(f, encoding="utf-8"):
        try: rows.append(json.loads(l))
        except: pass
seen = {}
for r in rows:
    mode = (r.get("date") or {}).get("mode") or "baseline"
    seen[(r.get("query_id"), mode)] = r          # last write wins
work = list(seen.values())
print("server-log rows %d -> unique (query_id, mode) %d" % (len(rows), len(work)))

def chunk_rec(h, stage):
    pl = h.payload or {}
    return {"stage": stage, "doc": pl.get("doc_name"), "page": pl.get("page"),
            "corpus": pl.get("corpus"),
            "section_number": pl.get("section_number"),      # THE MISSING FIELD
            "score": round(float(h.score), 6),
            "text_head": (pl.get("text") or "")[:160]}

cl = qdrant()
texts = [(r.get("router") or {}).get("rewritten_query") or r.get("query_raw") or "" for r in work]
print("embedding %d queries (retrieval only, no answers)..." % len(texts))
vecs, _meta = embed_texts(texts)

written = skipped = 0
with OUT.open("w", encoding="utf-8") as fh:
    for r, v in zip(work, vecs):
        rr = r.get("retrieval") or {}
        filt = rr.get("filter_applied")
        corpora = [filt] if isinstance(filt, str) else (list(filt) if filt else [])
        must = []
        if len(corpora) == 1:   must = [{"key": "corpus", "match": {"value": corpora[0]}}]
        elif len(corpora) > 1:  must = [{"key": "corpus", "match": {"any": corpora}}]
        flt = Filter(**{"must": must}) if must else None

        hits = cl.search(collection_name=COLLECTION, query_vector=v,
                         query_filter=flt, limit=15, with_payload=True)
        if not hits and must:                       # replay the recorded fallback
            hits = cl.search(collection_name=COLLECTION, query_vector=v,
                             limit=15, with_payload=True)
        if not hits:
            skipped += 1
            continue

        stage_a = list(hits)                                   # score order

        ents = (r.get("router") or {}).get("entities") or []    # STAGE B
        if ents:
            pri = [h for h in hits if any(e.lower() in ((h.payload or {}).get("text") or "").lower() for e in ents)]
            oth = [h for h in hits if h not in pri]
            stage_b = pri + oth
        else:
            stage_b = list(hits)

        scores = [h.score for h in stage_b]                     # STAGE C
        thr = max(max(scores) - ADAPTIVE_DROP, MIN_SCORE_FLOOR)
        stage_c = [h for h in stage_b if h.score >= thr]
        if len(stage_c) < 3 and len(stage_b) >= 3:
            stage_c = stage_b[:3]

        fh.write(json.dumps({
            "req_id": r.get("req_id"), "query_id": r.get("query_id"),
            "mode": (r.get("date") or {}).get("mode") or "baseline",
            "filter_applied": filt,
            "raw_15":      [chunk_rec(h, "raw_15")      for h in stage_a],
            "reranked_15": [chunk_rec(h, "reranked_15") for h in stage_b],
            "filtered_n":  [chunk_rec(h, "filtered_n")  for h in stage_c],
        }, ensure_ascii=False) + "\n")
        written += 1

print("wrote %d rows -> %s   (skipped %d with no hits)" % (written, OUT, skipped))

# how much did we recover?
recs = [json.loads(l) for l in OUT.open(encoding="utf-8")]
tot = sum(len(x["filtered_n"]) for x in recs)
have = sum(1 for x in recs for c in x["filtered_n"] if c["section_number"])
print("section_number present on %d/%d Stage-C chunks (%.1f%%)" % (have, tot, 100*have/max(tot,1)))
