"""Isolate TRUE non-determinism: same query_id, SAME intervention mode.

Rows that differ because they ran under different intervention modes are two
conditions, not duplicates. Only same-mode repeats can reveal non-determinism.
Read-only, zero cost.
"""
import json, io, sys, glob, collections, statistics
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

srows = []
for f in glob.glob("runs/eval_*/eval_summary.jsonl"):
    for l in open(f, encoding="utf-8"):
        try: srows.append(json.loads(l))
        except: pass

# key on (query_id, intervention) -- the true "same condition" key
by_cond = collections.defaultdict(list)
for r in srows:
    by_cond[(r.get("query_id"), r.get("intervention"))].append(r)

dups = {k: v for k, v in by_cond.items() if len(v) > 1}
print("rows %d | distinct (query_id, mode) %d | repeated under SAME mode %d"
      % (len(srows), len(by_cond), len(dups)))
print()

if not dups:
    print("No same-condition repeats. All 222 'duplicates' are different modes.")
    raise SystemExit

conf_d, ncit_d, ref_d = [], [], 0
identical = 0
for (qid, mode), g in dups.items():
    cs = [x.get("confidence") for x in g if x.get("confidence") is not None]
    ns = [x.get("n_citations") for x in g if x.get("n_citations") is not None]
    rs = {x.get("refused") for x in g}
    if len(set(cs)) <= 1 and len(set(ns)) <= 1 and len(rs) <= 1:
        identical += 1
    if len(cs) > 1: conf_d.append(max(cs) - min(cs))
    if len(ns) > 1: ncit_d.append(max(ns) - min(ns))
    if len(rs) > 1: ref_d += 1

print("Of %d same-condition repeats:" % len(dups))
print("  byte-identical on confidence, n_citations and refused : %d (%.1f%%)"
      % (identical, 100*identical/len(dups)))
print("  refusal decision flipped                              : %d" % ref_d)
print()

def summarise(name, xs, fmt="%.6f"):
    if not xs:
        print("  %-28s no data" % name); return
    nz = [x for x in xs if x != 0]
    print("  %-28s n=%d  differ=%d  max=%s  median(nonzero)=%s"
          % (name, len(xs), len(nz), fmt % max(xs),
             (fmt % statistics.median(nz)) if nz else "-"))

summarise("confidence spread", conf_d)
summarise("n_citations spread", ncit_d, "%d")

print()
print("Largest confidence differences:")
for (qid, mode), g in sorted(dups.items(),
        key=lambda kv: -(max([x.get('confidence') or 0 for x in kv[1]])
                         - min([x.get('confidence') or 0 for x in kv[1]])))[:6]:
    cs = sorted({x.get("confidence") for x in g})
    ns = sorted({x.get("n_citations") for x in g})
    print("  %-7s %-9s confidence=%s  n_citations=%s" % (qid, mode, cs, ns))

print()
print("Largest n_citations differences:")
for (qid, mode), g in sorted(dups.items(),
        key=lambda kv: -(max([x.get('n_citations') or 0 for x in kv[1]])
                         - min([x.get('n_citations') or 0 for x in kv[1]])))[:6]:
    ns = sorted({x.get("n_citations") for x in g})
    cs = sorted({x.get("confidence") for x in g})
    print("  %-7s %-9s n_citations=%s  confidence=%s" % (qid, mode, ns, cs))
