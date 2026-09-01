"""check04 -- INDEPENDENT RE-DERIVATION for exp04_ablation.py.  Wave 2, Subagent 4.

WHY A SECOND ROUTE AT ALL
    exp04 rests on one assumption: that the `composite` value sitting in the
    logs was produced by the formula that sits in agents/retriever.py. If it
    was not -- if the logged score came from an older formula, or a different
    weighting, or a build that no longer exists -- then every weight sweep and
    every leave-one-out in exp04 is a sweep over a formula the system never
    ran, and the paper would be reporting an ablation of fiction.

    So it is asserted, not assumed, and asserted by a route that shares no
    code with exp04: this file reads runs/*/queries.jsonl with the json module
    directly. It does not import exp04. It does not import metrics_lib. It
    does not call load_logs(). If both routes are wrong they have to be wrong
    in the same way by coincidence, which is the point of a paired check.

WHAT IT ASSERTS
    1. RECONSTRUCTION. For every logged query,
           0.55*top_k_mean + 0.15*(1 - min(score_gap/0.3, 1.0)) + 0.30*entity_coverage
       capped at 1.0 and rounded to 4dp equals the LOGGED composite, to within
       2e-4. That tolerance is the rounding floor: four quantities are each
       stored to 4 decimals, so the reconstruction cannot be expected to agree
       more closely than about 1e-4.

       IF THIS FAILS IT IS A MAJOR FINDING and it must be reported as one, NOT
       fixed by tweaking the formula until it matches. The assert message says
       so.

    2. THE BRIEF'S FORMULA DOES NOT RECONSTRUCT. The task brief stated the
       composite as 0.55*top_k_mean + 0.15*score_gap + 0.30*entity_coverage,
       without the transform. That is asserted to FAIL, so the discrepancy is
       recorded as a positive finding rather than silently absorbed.

    3. WEIGHT ARITHMETIC. The leave-one-out renormalisation is checked against
       the worked example in the brief: dropping score_gap must give
       0.647/0.353, and every renormalised weight vector must sum to 1.0.

    4. THE SWEEP GRID. 231 weightings, every one summing to 1.0 in exact
       integer units of 0.05, and the deployed 0.55/0.15/0.30 present among
       them (it must be, or the sweep could not be compared to it).

    5. LABEL COUNTS. positives under each definition, re-derived here from the
       raw eval_summary rows with a locally written matcher, and compared with
       the counts exp04 wrote into results/ablation.csv. `cited` uses a
       deliberately simple number-and-statute comparison rather than
       metrics_lib.same_section, so it is a genuinely separate implementation;
       it is reported side by side rather than asserted equal, because a
       simpler matcher is expected to differ slightly.

ZERO API calls. Reads only. Writes nothing.

Run:  ./venv/Scripts/python.exe experiments/check04_ablation_check.py
"""
from __future__ import annotations

import itertools
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

W = (0.55, 0.15, 0.30)
GAP_NORM = 0.3
TOL = 2e-4


def read_jsonl(p):
    out = []
    for line in Path(p).read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def load_server_records():
    """runs/*/queries.jsonl keyed by req_id. No load_logs(), no pandas."""
    recs = {}
    for f in (ROOT / "runs").rglob("queries.jsonl"):
        for r in read_jsonl(f):
            if r.get("req_id"):
                recs[r["req_id"]] = r
    return recs


def load_gold():
    gold = {}
    for f in (ROOT / "runs").glob("eval_*/eval_summary.jsonl"):
        for r in read_jsonl(f):
            if r.get("req_id"):
                gold[r["req_id"]] = r
    return gold


# --------------------------------------------------------------- 1 & 2

def check_reconstruction(recs):
    devs, brief_devs, n = [], [], 0
    worst = None
    for rid, r in recs.items():
        c = r.get("confidence") or {}
        tk, sg = c.get("top_k_mean"), c.get("score_gap")
        ec, comp = c.get("entity_coverage"), c.get("composite")
        if None in (tk, sg, ec, comp):
            continue
        n += 1
        gap_term = 1.0 - min(sg / GAP_NORM, 1.0)
        recon = min(W[0] * tk + W[1] * gap_term + W[2] * ec, 1.0)
        d = abs(round(recon, 4) - comp)
        devs.append(d)
        brief_devs.append(abs(min(W[0] * tk + W[1] * sg + W[2] * ec, 1.0) - comp))
        if worst is None or d > worst[1]:
            worst = (rid, d, tk, sg, ec, comp, recon)

    mx = max(devs)
    print("1. RECONSTRUCTION  (independent route: raw queries.jsonl, json module)")
    print("   rows checked          : %d" % n)
    print("   max |recon - logged|  : %.8f   (tolerance %.1e)" % (mx, TOL))
    print("   mean                  : %.8f" % (sum(devs) / n))
    print("   rows over 1e-3        : %d" % sum(1 for d in devs if d > 1e-3))
    print("   worst row             : %s  tk=%.4f gap=%.4f ec=%.4f  logged=%.4f "
          "recon=%.6f" % (worst[0], worst[2], worst[3], worst[4], worst[5], worst[6]))
    assert mx < TOL, (
        "\n\n*** MAJOR FINDING -- DO NOT ADJUST THE FORMULA TO MATCH ***\n"
        "The LOGGED composite is NOT reproduced by the formula in\n"
        "agents/retriever.py:137-142. Max deviation %.6f over %d rows.\n"
        "This means the logged confidence came from arithmetic that is not\n"
        "in the current source, and EVERY ablation number in exp04 is an\n"
        "ablation of a formula the system never ran. Report it. Stop.\n" % (mx, n))
    print("   -> AGREES. The logged composite IS the deployed formula.\n")

    bmx = max(brief_devs)
    bmean = sum(brief_devs) / n
    print("2. THE TASK BRIEF'S FORMULA  0.55*tk + 0.15*score_gap + 0.30*ec")
    print("   max |recon - logged|  : %.6f" % bmx)
    print("   mean                  : %.6f" % bmean)
    print("   rows over 1e-3        : %d of %d" % (sum(1 for d in brief_devs if d > 1e-3), n))
    assert bmx > 1e-2, (
        "The brief's untransformed formula unexpectedly reconstructs the "
        "logged composite. Re-derive before trusting either.")
    print("   -> DOES NOT RECONSTRUCT, as expected. The deployed system\n"
          "      transforms the gap first: 0.15 * (1 - min(gap/0.3, 1)).\n"
          "      A SMALL gap earns the weight; the brief had it inverted.\n")
    return n, mx, bmx, bmean


# --------------------------------------------------------------- 3 & 4

def check_weight_arithmetic():
    print("3. LEAVE-ONE-OUT RENORMALISATION")
    names = ("top_k_mean", "gap_term", "entity_coverage")
    for i, nm in enumerate(names):
        w = list(W)
        w[i] = 0.0
        s = sum(w)
        w = tuple(x / s for x in w)
        assert abs(sum(w) - 1.0) < 1e-12, "renormalised weights must sum to 1.0"
        print("   drop %-16s -> %s   sum=%.12f"
              % (nm, "/".join("%.3f" % x for x in w), sum(w)))
    w = list(W); w[1] = 0.0; s = sum(w)
    got = (w[0] / s, w[2] / s)
    assert abs(got[0] - 0.647) < 5e-4 and abs(got[1] - 0.353) < 5e-4, (
        "the brief's worked example says dropping score_gap gives 0.647/0.353; "
        "got %.4f/%.4f" % got)
    print("   -> matches the brief's worked example: 0.647 / 0.353\n")

    print("4. SWEEP GRID")
    n = 20
    grid = [(a * 0.05, b * 0.05, (n - a - b) * 0.05)
            for a, b in itertools.product(range(n + 1), repeat=2) if n - a - b >= 0]
    assert len(grid) == 231, "expected C(22,2)=231 weightings, got %d" % len(grid)
    assert all(abs(sum(w) - 1.0) < 1e-9 for w in grid), "a weighting does not sum to 1.0"
    assert any(all(abs(x - y) < 1e-9 for x, y in zip(w, W)) for w in grid), (
        "the deployed 0.55/0.15/0.30 is not on the grid, so the sweep cannot "
        "be compared against it")
    print("   %d weightings, all sum to 1.0, deployed 0.55/0.15/0.30 present\n"
          % len(grid))
    return len(grid)


# --------------------------------------------------------------- 5

_NUM = re.compile(r"(\d+[A-Za-z]?)")
_WORDS = re.compile(r"\b(SECTIONS?|SECS?|S|ARTICLES?|ARTS?|ORDERS?|RULES?)\b\.?")


def simple_key(s):
    """Deliberately simple: uppercase statute prefix if recognised, plus the
    first number. NOT metrics_lib.same_section -- that is the point.

    THE WORD "SECTION" MUST GO FIRST. Squashing "BNS Section 351" to
    "BNSSECTION351" and then testing startswith("BNSS") attributes it to the
    BNSS -- a different statute -- and silently loses the match. That is the
    same class of bug as defect E2 (comparing "IPC Section 302" with
    "Section 302" and calling them different), rediscovered here by writing a
    naive matcher on purpose. It cost 69 spurious negatives before it was
    caught.
    """
    t = _WORDS.sub(" ", str(s or "").upper())
    t = re.sub(r"[^A-Z0-9]+", "", t)
    m = _NUM.search(t)
    if not m:
        return None
    num = m.group(1)
    st = ""
    for k in ("BNSS", "CRPC", "BNS", "IPC", "CPA", "BSA", "IEA", "CPC", "NI"):
        if t.startswith(k):
            st = k
            break
    return (st, num)


def check_labels(recs, gold):
    print("5. LABEL COUNTS  (locally written matcher, not metrics_lib)")
    seen, cited_pos, grounded_pos, n = set(), 0, 0, 0
    for rid, r in recs.items():
        g = gold.get(rid)
        if not g:
            continue
        qid = g.get("query_id") or r.get("query_id")
        inter = g.get("intervention") or (r.get("date") or {}).get("mode") or "baseline"
        key = (qid, inter)
        if key in seen:
            continue                       # dedupe: (query_id, intervention)
        seen.add(key)
        exp = g.get("expected_sections") or []
        if not exp:
            continue
        n += 1
        ver = r.get("verifier") or {}
        ck = {simple_key(c) for c in (ver.get("cited") or [])}
        ck.discard(None)
        for e in exp:
            k = simple_key(e)
            if k is None:
                continue
            if any(ck_i[1] == k[1] and (not ck_i[0] or not k[0] or ck_i[0] == k[0])
                   for ck_i in ck):
                cited_pos += 1
                break
        ur = ver.get("ungrounded_rate")
        if ur is not None and float(ur) == 0.0:
            grounded_pos += 1

    print("   labelled rows (this route) : %d" % n)
    print("   cited positives            : %d" % cited_pos)
    print("   grounded positives         : %d" % grounded_pos)

    csv = ROOT / "results" / "ablation.csv"
    if csv.exists():
        rows = [l.split(",") for l in csv.read_text(encoding="utf-8").splitlines()]
        vals = {}
        for r in rows[1:]:
            if len(r) > 6 and r[0] == "positives":
                vals[r[2]] = r[5]
        print("   exp04 wrote                : %s" % vals)
        if "grounded" in vals:
            assert abs(float(vals["grounded"]) - grounded_pos) < 0.5, (
                "grounded positives disagree: exp04 %s vs this route %d"
                % (vals["grounded"], grounded_pos))
            print("   -> grounded AGREES across both routes.")
        if "cited" in vals:
            print("   -> cited: exp04 %s, simple matcher %d (a looser matcher is "
                  "expected to differ; not asserted)" % (vals["cited"], cited_pos))
    else:
        print("   results/ablation.csv not written yet -- run exp04 first.")
    print()
    return n, cited_pos, grounded_pos


def main():
    print("=" * 78)
    print("check04 -- INDEPENDENT RE-DERIVATION OF THE CONFIDENCE COMPOSITE")
    print("=" * 78)
    recs = load_server_records()
    gold = load_gold()
    print("server records: %d   gold records: %d\n" % (len(recs), len(gold)))
    check_reconstruction(recs)
    check_weight_arithmetic()
    check_labels(recs, gold)
    print("=" * 78)
    print("ALL ASSERTIONS PASSED.")
    print("Headline re-derived independently: the logged composite IS")
    print("0.55*top_k_mean + 0.15*(1-min(score_gap/0.3,1)) + 0.30*entity_coverage.")
    print("=" * 78)


if __name__ == "__main__":
    main()
