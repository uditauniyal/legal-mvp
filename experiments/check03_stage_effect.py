"""Which retrieval stage reproduces the README's layman figure?

Uses the AUTHORITATIVE section_number from the re-run, so text-parsing is
out of the picture entirely. The only variable is the stage.
"""
import json, io, sys, glob, re, math, collections
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

def wilson(k, n):
    if not n: return 0,0,0
    z=1.959963985; p=k/n; d=1+z*z/n
    c=(p+z*z/(2*n))/d; h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return p, max(0,c-h), min(1,c+h)
def pct(k,n):
    p,lo,hi = wilson(k,n); return "%5.1f%% [%4.1f,%5.1f]" % (100*p,100*lo,100*hi)

def base(s):
    m = re.match(r"\d+[A-Za-z]?", str(s or "").replace(" ","").upper())
    return m.group(0) if m else str(s or "").upper()

new = {}
for l in open("experiments/stages.jsonl", encoding="utf-8"):
    r = json.loads(l); new[r["req_id"]] = r

gold = {}
for f in glob.glob("runs/eval_*/eval_summary.jsonl"):
    for l in open(f, encoding="utf-8"):
        try:
            r = json.loads(l)
            if r.get("req_id"): gold[r["req_id"]] = r     # dedupe, last wins
        except: pass

def hit(g_sections, chunks, strict=True):
    for g in g_sections or []:
        act, num = g.split(" ", 1)
        num = num.replace(" ", "").upper()
        for c in chunks:
            if c.get("corpus") != act: continue
            sn = str(c.get("section_number") or "").upper()
            if not sn: continue
            if sn == num or (not strict and base(sn) == base(num)):
                return True
    return False

print("LAYMAN SET -- gold section retrieved, by stage")
print("Authoritative section_number. Only the STAGE varies.")
print()
print("  %-14s%4s   %-22s   %-22s" % ("STAGE","N","STRICT","LENIENT (base number)"))
print("  " + "-"*70)
for stage in ("raw_15", "reranked_15", "filtered_n"):
    n = s_hit = l_hit = 0
    for rid, r in new.items():
        g = gold.get(rid)
        if not g or g.get("category") != "layman_situation": continue
        n += 1
        s_hit += hit(g.get("expected_sections"), r[stage], True)
        l_hit += hit(g.get("expected_sections"), r[stage], False)
    print("  %-14s%4d   %-22s   %-22s" % (stage, n, pct(s_hit,n), pct(l_hit,n)))

print()
print("  README publishes 7.5%% (strict) for the layman set.")
print("  My 26-Aug 'correction' claimed the true value was 15.0%%.")
print()
print("ALL SETS, strict, by stage")
print("  %-24s%5s   %-20s %-20s %-20s" % ("QUERY SET","N","raw_15","reranked_15","filtered_n"))
print("  " + "-"*92)
cats = collections.Counter(g.get("category") for g in gold.values())
for cat in ["generated_retrieval","paired_recodification","layman_situation","paired_dated_conflict"]:
    row = {}
    n = 0
    for stage in ("raw_15","reranked_15","filtered_n"):
        k = n2 = 0
        for rid, r in new.items():
            g = gold.get(rid)
            if not g or g.get("category") != cat: continue
            n2 += 1
            k += hit(g.get("expected_sections"), r[stage], True)
        row[stage] = pct(k, n2); n = n2
    if n:
        print("  %-24s%5d   %-20s %-20s %-20s" % (cat, n, row["raw_15"], row["reranked_15"], row["filtered_n"]))
