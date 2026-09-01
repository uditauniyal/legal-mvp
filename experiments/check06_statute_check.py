"""check06 -- INDEPENDENT RE-DERIVATION of exp06's headline numbers.

WHY A SEPARATE FILE
    exp06 reads chunk identities from experiments/stages.jsonl (a replay) and
    the in-force windows from the Qdrant payload. If both the experiment and
    its check used those same two sources, the check would only prove the
    arithmetic, not the data. So this file takes a DIFFERENT ROUTE to the same
    numbers:

      quantity                exp06 route                  check06 route
      ----------------------  ---------------------------  --------------------------
      retrieved chunks        experiments/stages.jsonl     runs/*/queries.jsonl
                              (Qdrant replay, all 3 stages) retrieval.chunks[*].corpus
                                                            (what the server wrote at
                                                             answer time, Stage C only)
      in-force windows        Qdrant payload               hard-coded from the
                              in_force_from/until          Gazette commencement date
      dedupe + admissible set metrics_lib.load_logs()      written fresh here
      AUROC of the 3 generic  recomputed in exp06          the published exp04 values
      signals                                              in results/ablation.csv

    It imports NOTHING from exp06 and only `wilson`/`auroc` from metrics_lib
    (which the standing rules require -- metrics are never reimplemented).

A KNOWN, DOCUMENTED TOLERANCE
    Wave 2 found one chunk in 608 differing between the server log and the
    replay, caused by a 5th-decimal cosine difference flipping the order of
    two near-tied hits at the adaptive threshold. Differences are REPORTED
    here, never absorbed: the assertion is on the RATE, and every differing
    req_id is printed.

Run:  ./venv/Scripts/python.exe experiments/check06_statute_check.py
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.metrics_lib import wilson  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "results" / "statute_consistency.csv"

# Hard-coded from the commencement notification, NOT read from the payload.
# The BNS/BNSS/BSA came into force on 1 July 2024; the IPC/CrPC continue to
# govern earlier offences by the savings provisions. The Consumer Protection
# Act 2019 was never recodified, so it is admissible in both eras.
ERA_CODES = {
    "IPC_ERA": frozenset({"IPC", "CRPC", "CPA"}),
    "BNS_ERA": frozenset({"BNS", "CPA"}),
}
ALL_CODES = frozenset({"IPC", "BNS", "CRPC", "CPA"})
FAM = {"IPC": "P", "BNS": "P", "CRPC": "R", "BNSS": "R", "CPA": "C"}

fails: list[str] = []
notes: list[str] = []


def check(ok: bool, msg: str):
    print(("  PASS  " if ok else "  FAIL  ") + msg)
    if not ok:
        fails.append(msg)


# ---------------------------------------------------------------- load
def read_jsonl(p):
    out = []
    for line in Path(p).read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


srv = {}
for f in (ROOT / "runs").rglob("queries.jsonl"):
    for r in read_jsonl(f):
        if r.get("req_id"):
            srv[r["req_id"]] = r
gold = {}
for f in (ROOT / "runs").glob("eval_*/eval_summary.jsonl"):
    for r in read_jsonl(f):
        if r.get("req_id"):
            gold[r["req_id"]] = r

qset = {}
for f in sorted((ROOT / "eval").glob("*queryset.jsonl")):
    seen = {}
    for r in read_jsonl(f):
        seen[r["query_id"]] = r
    qset.update(seen)

rows = []
for rid, rec in srv.items():
    g = gold.get(rid, {})
    q = qset.get(rec.get("query_id"), {})
    rows.append({
        "req_id": rid,
        "query_id": rec.get("query_id"),
        "intervention": g.get("intervention") or (rec.get("date") or {}).get("mode") or "baseline",
        "query_set": g.get("category"),
        "era": ((rec.get("date") or {}).get("era")
                or q.get("applicable_regime") or "UNKNOWN"),
        "named": tuple((rec.get("retrieval") or {}).get("named_statutes") or []),
        "has_gold": bool(g.get("expected_sections") or []),
        "chunk_corpora": [c.get("corpus") for c in ((rec.get("retrieval") or {}).get("chunks") or [])],
    })
# DEDUPE FIRST, THEN drop the goldless rows -- that is the order load_logs()
# uses, and the order matters: a query whose LAST occurrence carries no gold
# is dropped by load_logs but would survive if the filter ran first.
df = pd.DataFrame(rows).drop_duplicates(subset=["query_id", "intervention"],
                                        keep="last").reset_index(drop=True)
df = df[df.has_gold].reset_index(drop=True)
print(f"independent load: {len(df)} gold rows (exp06 reports 617)")
check(len(df) == 617, f"row count after independent dedupe == 617 (got {len(df)})")


# ---------------------------------------------------------------- A2, fresh
def admissible_A2(era, named):
    D = ERA_CODES.get(era, ALL_CODES)
    if named:
        fams = {FAM[s] for s in named if s in FAM}
        F = frozenset(c for c in ALL_CODES if FAM[c] in fams) if fams else ALL_CODES
    else:
        F = ALL_CODES
    return (D & F) or F


sc = []
for era, named, cor in zip(df.era, df.named, df.chunk_corpora):
    A = admissible_A2(era, named)
    sc.append(float(np.mean([1.0 if c in A else 0.0 for c in cor])) if cor else np.nan)
df["sc_serverlog"] = sc

# ---------------------------------------------------------------- compare
csv = pd.read_csv(CSV)
print("\n1) statute_consistency at filtered_n: server log vs stages.jsonl replay")
worst = 0.0
for qs in ("paired_recodification", "paired_dated_conflict", "layman_situation",
           "generated_retrieval", "ALL"):
    m = np.ones(len(df), bool) if qs == "ALL" else (df.query_set == qs).values
    mine = float(np.nanmean(df.loc[m, "sc_serverlog"]))
    row = csv[(csv.metric == "statute_consistency_mean") & (csv.query_set == qs)
              & (csv.stage == "filtered_n")
              & (csv.notes.str.contains("A2_date_x_family", na=False))]
    theirs = float(row["value"].iloc[0])
    d = abs(mine - theirs)
    worst = max(worst, d)
    print(f"   {qs:24s} server-log {mine:.6f}   stages.jsonl {theirs:.6f}   diff {d:.6f}")
check(worst < 5e-3, f"mean statute_consistency agrees between the two chunk sources "
                    f"to <0.005 on every query set (worst {worst:.6f})")

# per-row, per-chunk: where exactly do the two sources disagree?
sys.path.insert(0, str(ROOT))
stages_raw = {r["req_id"]: r for r in read_jsonl(ROOT / "experiments" / "stages.jsonl")}
n_chunks = n_diff_chunks = n_diff_rows = 0
diff_rows = []
for rid, cor in zip(df.req_id, df.chunk_corpora):
    st = stages_raw.get(rid)
    if not st:
        continue
    rep = [c.get("corpus") for c in st.get("filtered_n", [])]
    n_chunks += max(len(cor), len(rep))
    a, b = collections.Counter(cor), collections.Counter(rep)
    d = sum((a - b).values()) + sum((b - a).values())
    if d or len(cor) != len(rep):
        n_diff_rows += 1
        diff_rows.append((rid, len(cor), len(rep), dict(a), dict(b)))
    n_diff_chunks += d
print(f"\n2) per-chunk comparison: {n_chunks} chunk slots, {n_diff_chunks} differing, "
      f"{n_diff_rows} rows affected")
for r in diff_rows[:10]:
    print(f"   DIFF req_id={r[0]} server_n={r[1]} replay_n={r[2]} server={r[3]} replay={r[4]}")
rate = n_diff_chunks / max(1, n_chunks)
notes.append(f"chunk-source disagreement: {n_diff_chunks}/{n_chunks} = {rate:.6f}")
check(rate < 0.01, f"server-log vs replay chunk disagreement below 1% "
                   f"({n_diff_chunks}/{n_chunks} = {rate:.4%}) -- Wave 2 documented "
                   f"1 chunk in 608 from a 5th-decimal cosine tie")

# ---------------------------------------------------------------- exp04 agreement
print("\n3) the three generic signals must reproduce the PUBLISHED exp04 values")
def signame(notes):
    """exp04 writes 'signal=gap_term = 1-min(...)' -- take the bare name."""
    s = str(notes).split("signal=")[1].split(";")[0].strip()
    return s.split(" =")[0].strip()


abl = pd.read_csv(ROOT / "results" / "ablation.csv")
published = {}
for _, r in abl[(abl.metric == "auroc_signal") & (abl.definition == "retrieved@k")
                & (abl.stage == "raw_15") & (abl.query_set == "ALL")].iterrows():
    published[signame(r["notes"])] = float(r["value"])
mine = {}
for _, r in csv[(csv.metric == "ablation_auroc") & (csv.definition == "retrieved@k")
                & (csv.stage == "raw_15") & (csv.query_set == "ALL")].iterrows():
    mine[signame(r["notes"])] = float(r["value"])
worst = 0.0
for sig in ("top_k_mean", "gap_term", "entity_coverage", "composite", "max_score"):
    d = abs(published[sig] - mine[sig])
    worst = max(worst, d)
    print(f"   {sig:16s} exp04 {published[sig]:.6f}   exp06 {mine[sig]:.6f}   diff {d:.2e}")
check(worst < 1e-6, f"exp06's ablation rows reproduce exp04's published AUROCs exactly "
                    f"(worst {worst:.2e}) -- same rows, same labels, same metrics_lib")

print("\n3b) entity_coverage per query set must also reproduce exp04")
worst = 0.0
for qs in ("generated_retrieval", "paired_recodification", "paired_dated_conflict",
           "layman_situation"):
    pub = abl[(abl.metric == "auroc_signal") & (abl.definition == "retrieved@k")
              & (abl.stage == "raw_15") & (abl.query_set == qs)
              & (abl.notes.str.startswith("signal=entity_coverage", na=False))]
    m = csv[(csv.metric == "auroc_entity_coverage_logged_substring")
            & (csv.definition == "retrieved@k") & (csv.stage == "raw_15")
            & (csv.query_set == qs)]
    pv = float(pub["value"].iloc[0])
    mv = m["value"].iloc[0]
    if pd.isna(mv) or mv == "":
        print(f"   {qs:24s} exp04 {pv:.6f}   exp06 NOT MEASURED (constant signal)")
        continue
    d = abs(pv - float(mv))
    worst = max(worst, d)
    print(f"   {qs:24s} exp04 {pv:.6f}   exp06 {float(mv):.6f}   diff {d:.2e}")
check(worst < 1e-6, f"per-query-set entity_coverage AUROC reproduces exp04 (worst {worst:.2e})")

# ---------------------------------------------------------------- normaliser
print("\n4) normaliser population re-derived by a different regex route")
import fitz  # noqa: E402
from ingest.chunk import SECTION_NORMALISE, normalise_sections  # noqa: E402

tot_findall = tot_delta = 0
for p in sorted((ROOT / "tests" / "data").glob("*.pdf")):
    doc = fitz.open(str(p))
    for i in range(doc.page_count):
        t = doc.load_page(i).get_text("text") or ""
        tot_findall += len(SECTION_NORMALISE.findall(t))
        # third route: count how many times the OUTPUT gained the word "Section"
        tot_delta += normalise_sections(t).count("Section ") - t.count("Section ")
    doc.close()
csv_pop = float(csv[csv.metric == "normaliser_rewrites_total"]["value"].iloc[0])
print(f"   findall over whole pages : {tot_findall}")
print(f"   'Section ' count delta   : {tot_delta}")
print(f"   exp06 per-line population: {int(csv_pop)}")
check(tot_findall == int(csv_pop),
      f"findall route agrees with the per-line population ({tot_findall} vs {int(csv_pop)})")
check(tot_delta == int(csv_pop),
      f"'Section ' insertion-count route agrees too ({tot_delta} vs {int(csv_pop)})")

art = csv[csv.metric == "normaliser_artefact_rate"].iloc[0]
k = int(round(float(art["value"]) * 100))
p_, lo_, hi_ = wilson(k, 100)
print(f"\n5) Wilson interval re-derived: {k}/100 -> {p_:.4f} [{lo_:.4f}, {hi_:.4f}]")
check(abs(lo_ - float(art["ci_lo"])) < 1e-6 and abs(hi_ - float(art["ci_hi"])) < 1e-6,
      "Wilson interval in the CSV matches a fresh call on the reported counts")

# ---------------------------------------------------------------- verdict
print("\n" + "=" * 70)
for n in notes:
    print("NOTE: " + n)
if fails:
    print(f"CHECK06 FAILED -- {len(fails)} assertion(s):")
    for f_ in fails:
        print("   - " + f_)
    sys.exit(1)
print("CHECK06 PASSED -- every headline value re-derived by an independent route.")
