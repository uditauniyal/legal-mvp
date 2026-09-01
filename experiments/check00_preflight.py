"""Pre-flight checks before the Option A re-run.

CHECK 1  Is the Qdrant collection still the index the original runs used?
CHECK 3  Do duplicated query_id rows AGREE with each other?

Read-only. Writes nothing. Zero API cost (Qdrant is local).
"""
import json, io, sys, glob, collections
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, ".")
from clients.qdrant_client import COLLECTION, qdrant

print("=" * 78)
print("CHECK 1 -- is the index the same one the original runs used?")
print("=" * 78)

cl = qdrant()
info = cl.get_collection(COLLECTION)
print("  collection      : %s" % COLLECTION)
print("  points_count    : %d   (expected 1899)" % info.points_count)

by_corpus = collections.Counter()
text_by_key = {}
off = None
while True:
    pts, off = cl.scroll(collection_name=COLLECTION, limit=500, offset=off,
                         with_payload=True, with_vectors=False)
    for p in pts:
        pl = p.payload or {}
        by_corpus[pl.get("corpus")] += 1
        k = (pl.get("doc_name"), pl.get("page"))
        text_by_key.setdefault(k, []).append(pl.get("text") or "")
    if off is None:
        break

print("  composition     :")
for k, v in by_corpus.most_common():
    print("      %-6s %5d  %5.1f%%" % (k, v, 100 * v / sum(by_corpus.values())))

EXPECTED = {"CRPC": 742, "IPC": 595, "BNS": 424, "CPA": 138}
match = all(by_corpus.get(k) == v for k, v in EXPECTED.items())
print("  matches the Phase E rebuild (CRPC 742/IPC 595/BNS 424/CPA 138)? %s" % match)

# strongest test: do chunks recorded in OLD runs still exist with the same text?
rows = []
for f in glob.glob("runs/*/queries.jsonl"):
    for l in open(f, encoding="utf-8"):
        try: rows.append(json.loads(l))
        except: pass

checked = found = mismatch = 0
examples = []
for r in rows[:400]:
    for c in ((r.get("retrieval") or {}).get("chunks") or [])[:3]:
        head = (c.get("text_head") or "").strip()
        if not head:
            continue
        checked += 1
        cands = text_by_key.get((c.get("doc"), c.get("page")), [])
        if any(" ".join(t.split()).startswith(" ".join(head.split())[:60]) for t in cands):
            found += 1
        else:
            mismatch += 1
            if len(examples) < 3:
                examples.append((c.get("doc"), c.get("page"), head[:60]))

print("  logged chunks re-found in Qdrant by (doc,page,text prefix):")
print("      checked %d   found %d   MISSING %d   (%.1f%% found)" %
      (checked, found, mismatch, 100 * found / max(checked, 1)))
for e in examples:
    print("      missing example: %s p.%s  %r" % e)

verdict1 = (info.points_count == 1899) and match and (mismatch == 0)
print()
print("  VERDICT: %s" % ("SAME INDEX -- safe to re-run" if verdict1
                         else "INDEX DIFFERS -- STOP, re-run would not be comparable"))

print()
print("=" * 78)
print("CHECK 3 -- do duplicated query_id rows AGREE with each other?")
print("=" * 78)

srows = []
for f in glob.glob("runs/eval_*/eval_summary.jsonl"):
    for l in open(f, encoding="utf-8"):
        try: srows.append(json.loads(l))
        except: pass

by_id = collections.defaultdict(list)
for r in srows:
    by_id[r.get("query_id")].append(r)
dups = {k: v for k, v in by_id.items() if len(v) > 1}
print("  summary rows %d, unique query_id %d, ids appearing more than once %d"
      % (len(srows), len(by_id), len(dups)))

# compare the fields that a metric would actually consume
FIELDS = ["confidence", "n_citations", "refused", "expected_sections",
          "intervention", "req_id"]
agree = collections.Counter()
disagree_examples = collections.defaultdict(list)
for qid, group in dups.items():
    for f in FIELDS:
        vals = {json.dumps(g.get(f), sort_keys=True) for g in group}
        if len(vals) == 1:
            agree[f + " AGREE"] += 1
        else:
            agree[f + " DISAGREE"] += 1
            if len(disagree_examples[f]) < 3:
                disagree_examples[f].append((qid, sorted(vals)[:2]))

print()
print("  across %d duplicated ids:" % len(dups))
for f in FIELDS:
    a, d = agree[f + " AGREE"], agree[f + " DISAGREE"]
    flag = "" if d == 0 else "   <-- DISAGREES"
    print("      %-20s agree %4d   disagree %4d%s" % (f, a, d, flag))

for f, ex in disagree_examples.items():
    if not ex:
        continue
    print()
    print("      %s -- examples:" % f)
    for qid, vals in ex:
        print("        %s" % qid)
        for v in vals:
            print("            %s" % v[:110])

# is disagreement explained by intervention mode?
mixed_mode = sum(1 for g in dups.values()
                 if len({x.get("intervention") for x in g}) > 1)
print()
print("  duplicated ids whose rows came from DIFFERENT intervention modes: %d" % mixed_mode)
print("      (those SHOULD differ -- baseline vs both are different conditions)")
