"""Addition 2 -- does the re-run reproduce Stage C? And how big is the counting bug REALLY?

Read-only over experiments/stages.jsonl and runs/. Zero cost.
"""
import json, io, sys, glob, re, collections
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

SECTION_HEAD = re.compile(r"Section\s+(\d+[A-Za-z]?)")   # the OLD analysis rule

new = {}
for l in open("experiments/stages.jsonl", encoding="utf-8"):
    r = json.loads(l); new[r["req_id"]] = r

old = {}
for f in glob.glob("runs/*/queries.jsonl"):
    for l in open(f, encoding="utf-8"):
        try:
            r = json.loads(l); old[r.get("req_id")] = r
        except: pass

print("=" * 78)
print("ADDITION 2 -- does the re-run reproduce the original Stage C?")
print("=" * 78)
shared = [k for k in new if k in old]
print("  req_ids in both: %d" % len(shared))

exact = same_len = diff = 0
examples = []
for k in shared:
    o = [( (c.get("doc")), c.get("page"), round(float(c.get("score") or 0), 4))
         for c in ((old[k].get("retrieval") or {}).get("chunks") or [])]
    n = [(c["doc"], c["page"], round(c["score"], 4)) for c in new[k]["filtered_n"]]
    if o == n:
        exact += 1
    else:
        diff += 1
        if len(o) == len(n): same_len += 1
        if len(examples) < 3:
            examples.append((k, len(o), len(n), o[:2], n[:2]))

print("  EXACT match (same chunks, same order, same score to 4dp): %d/%d  (%.1f%%)"
      % (exact, len(shared), 100*exact/max(len(shared),1)))
print("  differ: %d   (of which same length: %d)" % (diff, same_len))
for k, lo, ln, oo, nn in examples:
    print("    %s  old n=%d new n=%d" % (k, lo, ln))
    print("        old[:2] %s" % (oo,))
    print("        new[:2] %s" % (nn,))

print()
print("=" * 78)
print("HOW BIG IS THE COUNTING BUG, REALLY?")
print("=" * 78)
print("A chunk with section_number=None is NOT a section (preamble, a split")
print("continuation, or a demoted footnote). Counting it as 'not the gold")
print("section' is CORRECT. The bug is only chunks that HAVE a section_number")
print("but whose text_head does not reveal it.")
print()

tot = with_sn = no_sn = 0
recoverable = missed = wrong = 0
miss_ex, wrong_ex = [], []
for r in new.values():
    for c in r["filtered_n"]:
        tot += 1
        sn, head = c.get("section_number"), c.get("text_head") or ""
        if not sn:
            no_sn += 1
            continue
        with_sn += 1
        m = SECTION_HEAD.search(head)
        if not m:
            missed += 1
            if len(miss_ex) < 3: miss_ex.append((c["corpus"], sn, head[:66]))
        elif m.group(1).upper() != str(sn).upper():
            wrong += 1
            if len(wrong_ex) < 3: wrong_ex.append((c["corpus"], sn, m.group(1), head[:60]))
        else:
            recoverable += 1

print("  Stage-C chunks total                     : %d" % tot)
print("  with NO section_number (correctly a miss): %d  (%.1f%%)" % (no_sn, 100*no_sn/tot))
print("  WITH a section_number                    : %d  (%.1f%%)" % (with_sn, 100*with_sn/tot))
print()
print("  Of those WITH a section_number, the old text-parsing rule:")
print("     recovered it correctly : %d  (%.1f%%)" % (recoverable, 100*recoverable/max(with_sn,1)))
print("     FOUND NOTHING          : %d  (%.1f%%)   <- silently counted as a miss" % (missed, 100*missed/max(with_sn,1)))
print("     found the WRONG number : %d  (%.1f%%)   <- worse: a false match" % (wrong, 100*wrong/max(with_sn,1)))
print()
print("  => the real counting-bug rate is %.1f%% of identifiable passages"
      % (100*(missed+wrong)/max(with_sn,1)))
for c, sn, h in miss_ex:
    print("     MISSED  %-5s s.%-6s %r" % (c, sn, h))
for c, sn, got, h in wrong_ex:
    print("     WRONG   %-5s真 s.%-5s parsed s.%-5s %r" % (c, sn, got, h))
