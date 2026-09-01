"""exp06 -- THE FOURTH CONFIDENCE SIGNAL: statute_consistency.  Wave 3, Subagent 1.

WHAT THIS IS
    docs/TARGET_ARCHITECTURE.md line 348 specifies a fourth confidence signal
    that was never implemented:

        statute_consistency = fraction of retrieved chunks whose statute_code
                              is in the set implied by the query + date

    The three deployed signals (top_k_mean, score_gap, entity_coverage) all
    inspect similarity NUMBERS. This one inspects whether the passages came
    out of the right BOOK. A query about an offence committed in March 2023
    must be answered from the Indian Penal Code; the same offence in July 2026
    must be answered from the Bharatiya Nyaya Sanhita. No amount of cosine
    similarity can tell those apart, because the two texts are near-identical.

WHAT THIS IS NOT
    It is ANALYSIS. Nothing here changes the deployed confidence weights
    (0.55/0.15/0.30), the tier thresholds (0.55/0.38) or the 0.35 filter floor.
    Zero generation calls. Zero embedding calls. Zero writes to Qdrant, runs/,
    eval/, data/ or backup/. Reads only; writes only results/statute_consistency.csv.

--------------------------------------------------------------------------
THE DEFINITION, PRE-REGISTERED BEFORE ANY AUROC WAS COMPUTED
--------------------------------------------------------------------------
"The set implied by the query + date" is the whole design decision, so it is
written down here in full and FROZEN. Five variants are computed and ALL FIVE
are reported. A2 is declared PRIMARY in advance. No variant was added, removed
or altered after seeing a discrimination number -- see section 6 of
results/_explain_w3_s1.md.

WHAT IS IN THE CORPUS.  Verified by scrolling Qdrant `legal_mvp` (1,899
points, read-only): `corpus == statute_code` on all 1,899 points, and only
four codes exist --

    code   in_force_from   in_force_until   points
    IPC    1862-01-01      2024-07-01         595
    CRPC   1974-04-01      2024-07-01         742
    BNS    2024-07-01      (none)             424
    CPA    2020-07-20      (none)             138

The in-force windows are read from the PAYLOAD, not hand-written here. India
commenced the BNS/BNSS/BSA on 1 July 2024; offences before that date remain
under the IPC/CrPC/IEA by the savings provisions, which is exactly what
`in_force_until = 2024-07-01` encodes. BNSS, BSA and IEA are NOT in the
corpus, so a procedural question about a post-2024 incident has no admissible
successor text available -- handled by the fallback rule below and counted.

D(t)  DATE-ADMISSIBLE SET.  {c : in_force_from(c) <= t < in_force_until(c)}.
      Eras are evaluated at a representative date:
          IPC_ERA  -> 2024-06-30   =>  D = {IPC, CRPC, CPA}
          BNS_ERA  -> 2024-07-01   =>  D = {BNS, CPA}
          UNKNOWN  -> D = all four codes  (BOTH regimes admissible)
      The UNKNOWN branch is the one that matters most: 56 of 120 layman
      queries state no date, and treating those as errors would manufacture a
      result. They are treated as UNCONSTRAINED BY DATE, never as wrong.

F(q)  QUERY-ADMISSIBLE SET, from the statutes the query names. Source is
      `retrieval.named_statutes`, which the deployed system logged on every
      row. A named statute implies its SUBJECT-MATTER FAMILY, because the
      recodification renamed the books without moving the subject:
          PENAL      IPC, BNS
          PROCEDURE  CRPC, BNSS
          EVIDENCE   IEA, BSA
          CONSUMER   CPA          (never recodified)
      F = every corpus code whose family is named. Names nothing -> all four.

THE FIVE VARIANTS
    A1  date_only       A = D(era)
    A2  date_x_family   A = D(era) INTERSECT F(named);  if empty, A = F(named)
        *** PRIMARY ***  the fallback fires only when the successor code is
        absent from the corpus (procedure after July 2024). Counted and
        reported as `admissible_fallback_fired`.
    A3  family_only     A = F(named)              -- ablates the date
    A4  oracle_gold     A = expected_corpora from the query set, EITHER ->
        both era twins.  NOT DEPLOYABLE -- it reads the gold. Reported only as
        an upper bound on what a perfect query+date understanding could buy.
    A5  deployed_date   A2, but the era comes ONLY from the logged
        `date.era`. Fully deployable, no oracle input at all. The deployed
        date module ran on 98 of 617 rows, so A5 collapses to A3 elsewhere.

WHERE THE ERA COMES FROM (A1, A2, A3)
    1. `date.era` in the server log, if present (98 rows).
    2. else `applicable_regime` in the query set (a human annotation OF THE
       QUERY TEXT, not of the answer -- it says what the query's stated date
       implies, which a working date parser would recover).
    3. else UNKNOWN.
    Step 2 assumes a perfect date parser on 519 rows. That is disclosed, and
    A5 is reported precisely so the no-oracle version is on the record too.

THE MEASURE
    statute_consistency(row, stage) =
        (# chunks at that stage whose statute_code is in A) / (# chunks)
    Every chunk carries a statute_code, so nothing is dropped and the value
    is in [0, 1] by construction.

--------------------------------------------------------------------------
SECOND TASK -- entity_coverage recomputed from the payload
--------------------------------------------------------------------------
    Deployed (agents/retriever.py:117-119): the top-5 RERANKED chunk texts are
    concatenated and each query entity is looked for as a SUBSTRING. The
    ingestion normaliser rewrites any line starting "<number>." into
    "Section <number>.", so a table-of-contents row or a footnote marker can
    put the literal string "Section 506" into a chunk that is not Section 506.
    Recomputed here against the `section_number` PAYLOAD field instead, using
    metrics_lib.same_section(). Both are reported with the difference.

--------------------------------------------------------------------------
THIRD TASK -- the normaliser artefact rate
--------------------------------------------------------------------------
    100 rewritten lines sampled without replacement from all 3,302 rewrites
    across the four source PDFs, rng = numpy default_rng(SEED=20260901), and
    classified BY READING each one. Labels are stored in NORMALISER_LABELS
    below so the annotation is auditable and the rate is reproducible.

PAIRED CHECK -- experiments/check06_statute_check.py
    Recomputes statute_consistency for the paired sets from the RAW
    runs/*/queries.jsonl `retrieval.chunks[*].corpus` field, a route that
    shares no code with this file, and asserts agreement.

Run:  ./venv/Scripts/python.exe experiments/exp06_statute_consistency.py
"""
from __future__ import annotations

import collections
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.metrics_lib import (  # noqa: E402
    SEED, N_BOOT, STAGES, load_logs, load_stages, load_queryset,
    correctness_label, auroc, auroc_bootstrap_ci, paired_bootstrap_auroc_diff,
    cluster_bootstrap, ece, same_section, normalise_section, wilson,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "statute_consistency.csv"

# ---- the corpus, READ from Qdrant at run time (never hard-coded) --------
COLLECTION = "legal_mvp"

# subject-matter families. IEA/BSA/BNSS listed for completeness; only the
# four codes actually present in the collection can ever enter an admissible
# set, because the set is intersected with the corpus codes.
FAMILY = {"IPC": "PENAL", "BNS": "PENAL",
          "CRPC": "PROCEDURE", "BNSS": "PROCEDURE",
          "IEA": "EVIDENCE", "BSA": "EVIDENCE",
          "CPA": "CONSUMER"}

ERA_DATE = {"IPC_ERA": "2024-06-30", "BNS_ERA": "2024-07-01"}

VARIANTS = ("A1_date_only", "A2_date_x_family", "A3_family_only",
            "A4_oracle_gold", "A5_deployed_date")
PRIMARY = "A2_date_x_family"

QUERY_SETS = ("generated_retrieval", "paired_dated_conflict",
              "layman_situation", "paired_recodification")

DEFS = [("retrieved@k", 15), ("cited", ""), ("grounded", "")]

ENTITY_NEUTRAL = 0.5          # agents/retriever.py:45 -- READ, never written

rows_out: list[dict] = []


def emit(metric, value, n, query_set="ALL", definition="", stage="", k="",
         ci_lo="", ci_hi="", cluster_ci_lo="", cluster_ci_hi="", notes=""):
    rows_out.append({
        "metric": metric, "query_set": query_set, "definition": definition,
        "stage": stage, "k": k, "value": value, "n": n,
        "ci_lo": ci_lo, "ci_hi": ci_hi,
        "cluster_ci_lo": cluster_ci_lo, "cluster_ci_hi": cluster_ci_hi,
        "notes": notes,
    })


def r6(x):
    return "" if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), 6)


# ======================================================================
# PART 0 -- load everything
# ======================================================================
t0 = time.time()
print("== PART 0: loading ==")

from qdrant_client import QdrantClient  # noqa: E402

qc = QdrantClient(url="http://127.0.0.1:6333")
pts, _ = qc.scroll(COLLECTION, limit=5000, with_payload=True, with_vectors=False)
print(f"   Qdrant: {len(pts)} points scrolled (READ-ONLY)")

IN_FORCE: dict[str, tuple[str, str | None]] = {}
mismatch_corpus_statute = 0
full_text: dict[tuple, str] = {}
for p in pts:
    pl = p.payload
    c, sc = pl.get("corpus"), pl.get("statute_code")
    if c != sc:
        mismatch_corpus_statute += 1
    until = pl.get("in_force_until")
    if until in (None, "None", ""):
        until = None
    IN_FORCE[sc] = (pl.get("in_force_from"), until)
    key = (pl.get("doc_name"), str(pl.get("page")), pl.get("section_number") or "",
           (pl.get("text") or "")[:160])
    full_text[key] = pl.get("text") or ""

CORPUS_CODES = frozenset(IN_FORCE)
print(f"   corpus codes {sorted(CORPUS_CODES)}  in-force {IN_FORCE}")
print(f"   corpus != statute_code on {mismatch_corpus_statute} points")

df = load_logs()
n_before = len(df)
df = df[df["expected_sections"].map(len) > 0].reset_index(drop=True)
print(f"   load_logs: {n_before} deduped rows -> {len(df)} with gold")

stages = load_stages()

# raw server log, for the fields load_logs does not carry
srv: dict[str, dict] = {}
for f in (ROOT / "runs").rglob("queries.jsonl"):
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                r = json.loads(line)
                if r.get("req_id"):
                    srv[r["req_id"]] = r
            except json.JSONDecodeError:
                pass

# query sets, for applicable_regime / expected_corpora
qset: dict[str, dict] = {}
for f in sorted((ROOT / "eval").glob("*queryset.jsonl")):
    for rec in load_queryset(f).to_dict("records"):
        qset[rec["query_id"]] = rec
print(f"   query sets: {len(qset)} query_ids")


def dig(rid, *ks):
    d = srv.get(rid)
    for k in ks:
        d = (d or {}).get(k)
    return d


df["era_log"] = [dig(r, "date", "era") for r in df.req_id]
df["named"] = [tuple(dig(r, "retrieval", "named_statutes") or []) for r in df.req_id]
df["entities"] = [list(dig(r, "router", "entities") or []) for r in df.req_id]
df["era_qset"] = [(qset.get(q) or {}).get("applicable_regime") for q in df.query_id]
df["expected_corpora"] = [(qset.get(q) or {}).get("expected_corpora") for q in df.query_id]
df["era"] = [lg or qs or "UNKNOWN" for lg, qs in zip(df.era_log, df.era_qset)]
df["era"] = df["era"].replace({None: "UNKNOWN"})
df["has_stage"] = [r in stages for r in df.req_id]
print(f"   rows with stage records: {int(df.has_stage.sum())} / {len(df)}")
print(f"   era: {dict(df.era.value_counts())}   era from log: {int(df.era_log.notna().sum())}")

emit("rows_analysed", float(len(df)), len(df), notes=(
    f"load_logs() returned {n_before} deduplicated rows (859 before dedupe); "
    f"{n_before - len(df)} dropped for having no gold section; "
    f"{int(df.has_stage.sum())} of {len(df)} have stage records; "
    f"{df.pair_id.nunique()} clusters by pair_id; pair_id missing on "
    f"{int(df.pair_id.isna().sum())} rows"))
emit("qdrant_corpus_statute_code_mismatches", float(mismatch_corpus_statute), len(pts),
     notes="points where payload corpus != statute_code; 0 means the two fields "
           "are interchangeable and stages.jsonl `corpus` IS the statute_code")


# ======================================================================
# PART 1 -- the admissible sets
# ======================================================================
print("== PART 1: admissible sets ==")


def date_admissible(era: str) -> frozenset:
    """Codes in force at the representative date for this era, read from the
    Qdrant in_force_from / in_force_until payload."""
    if era not in ERA_DATE:
        return CORPUS_CODES                      # UNKNOWN -> both regimes
    t = ERA_DATE[era]
    out = set()
    for c, (frm, until) in IN_FORCE.items():
        if frm and t < frm:
            continue
        if until and t >= until:
            continue
        out.add(c)
    return frozenset(out)


def family_admissible(named: tuple) -> frozenset:
    if not named:
        return CORPUS_CODES
    fams = {FAMILY.get(s) for s in named if FAMILY.get(s)}
    if not fams:
        return CORPUS_CODES
    return frozenset(c for c in CORPUS_CODES if FAMILY.get(c) in fams)


def oracle_admissible(row) -> frozenset:
    ec = row["expected_corpora"]
    if isinstance(ec, list) and ec:
        s = frozenset(c for c in ec if c in CORPUS_CODES)
        if s:
            return s
    single = row["expected_corpus"]
    if single == "EITHER":
        return frozenset({"IPC", "BNS"}) & CORPUS_CODES
    if single in CORPUS_CODES:
        return frozenset({single})
    return CORPUS_CODES


fallback_fired = collections.Counter()


def admissible(row, variant: str) -> frozenset:
    D = date_admissible(row["era"])
    F = family_admissible(row["named"])
    if variant == "A1_date_only":
        return D
    if variant == "A3_family_only":
        return F
    if variant == "A4_oracle_gold":
        return oracle_admissible(row)
    if variant == "A5_deployed_date":
        D = date_admissible(row["era_log"] or "UNKNOWN")
    inter = D & F
    if not inter:
        fallback_fired[variant] += 1
        return F
    return inter


for v in VARIANTS:
    df[f"adm_{v}"] = [admissible(r, v) for r in df.to_dict("records")]

for v in VARIANTS:
    for st in STAGES:
        col = f"sc_{v}_{st}"
        vals = []
        for rid, A in zip(df.req_id, df[f"adm_{v}"]):
            ch = stages.get(rid, {}).get(st, [])
            vals.append(float(np.mean([1.0 if c.get("corpus") in A else 0.0 for c in ch]))
                        if ch else np.nan)
        df[col] = vals

# Are any two variants numerically identical? If so, say so LOUDLY rather than
# publishing two columns of the same number under different names.
for i, v1 in enumerate(VARIANTS):
    for v2 in VARIANTS[i + 1:]:
        a = df[f"sc_{v1}_raw_15"].values
        b = df[f"sc_{v2}_raw_15"].values
        ndiff = int(np.nansum(np.abs(a - b) > 1e-12))
        emit("variant_rows_differing", float(ndiff), len(df), stage="raw_15",
             notes=f"{v1} vs {v2}: rows where statute_consistency differs at raw_15. "
                   f"0 means the two definitions are the SAME measurement on this data")

# How often is the value 1.0 FOR FREE, because the Qdrant corpus filter the
# query itself produced already restricted retrieval to an admissible code?
for v in VARIANTS:
    forced = sum(1 for f_, A in zip(df.filter_applied, df[f"adm_{v}"])
                 if isinstance(f_, str) and f_ in A)
    emit("statute_consistency_forced_to_1_by_filter", float(forced), len(df),
         notes=f"variant={v}; rows where retrieval.filter_applied is a single corpus "
               f"that is itself inside the admissible set, so every retrieved chunk is "
               f"admissible BY CONSTRUCTION and the signal cannot fail. "
               f"filter_applied was None (unfiltered) on "
               f"{int(df.filter_applied.isna().sum())} rows")

for v in VARIANTS:
    emit("admissible_fallback_fired", float(fallback_fired.get(v, 0)), len(df),
         notes=f"variant={v}; rows where D(era) INTERSECT F(named) was empty and the "
               f"rule fell back to F(named) -- happens only when the successor code "
               f"(BNSS/BSA) is absent from the corpus")
    sizes = collections.Counter(tuple(sorted(a)) for a in df[f"adm_{v}"])
    emit("admissible_set_sizes", float(np.mean([len(a) for a in df[f"adm_{v}"]])), len(df),
         notes=f"variant={v}; MEAN size of the admissible set; distribution: "
               + "; ".join(f"{'+'.join(k) or 'EMPTY'}={n}" for k, n in sizes.most_common()))
    for st in STAGES:
        s = df[f"sc_{v}_{st}"]
        emit("statute_consistency_mean", r6(s.mean()), int(s.notna().sum()),
             stage=st, notes=f"variant={v}; mean over all rows; "
                             f"fraction exactly 1.0 = {float((s == 1.0).mean()):.4f}; "
                             f"fraction exactly 0.0 = {float((s == 0.0).mean()):.4f}")
        for qs in QUERY_SETS:
            m = df.query_set == qs
            ss = df.loc[m, f"sc_{v}_{st}"]
            emit("statute_consistency_mean", r6(ss.mean()), int(ss.notna().sum()),
                 query_set=qs, stage=st,
                 notes=f"variant={v}; fraction exactly 1.0 = {float((ss == 1.0).mean()):.4f}")

print("   variant means (raw_15):",
      {v: round(float(df[f'sc_{v}_raw_15'].mean()), 4) for v in VARIANTS})
print("   fallback fired:", dict(fallback_fired))


# ======================================================================
# PART 2 -- labels
# ======================================================================
print("== PART 2: correctness labels ==")
recs = df.to_dict("records")
labels: dict[tuple, np.ndarray] = {}
for definition, k in DEFS:
    for st in STAGES:
        ys = []
        for rec in recs:
            rec["_stage"] = st
            ys.append(correctness_label(rec, definition,
                                        k=(k if k else 15), stages=stages))
        labels[(definition, st)] = np.asarray(ys, int)
    for st in STAGES:
        y = labels[(definition, st)]
        emit("positives", float(y.sum()), len(df), definition=definition,
             stage=st, k=(k if k else ""),
             notes=f"count of label==1; prevalence {y.mean():.4f}"
                   + ("; label does not depend on the stage" if definition != "retrieved@k" else ""))
    print(f"   {definition:12s} positives per stage: "
          + str({s: int(labels[(definition, s)].sum()) for s in STAGES}))


# ======================================================================
# PART 3 -- AUROC / ECE grid
# ======================================================================
print("== PART 3: AUROC + ECE grid  (this is the slow part) ==")

GROUPS = [("ALL", np.ones(len(df), bool))] + \
         [(qs, (df.query_set == qs).values) for qs in QUERY_SETS]


def auroc_row(metric, s, y, cl, group, definition, stage, k, notes, clustered):
    ok = ~np.isnan(s)
    s2, y2 = s[ok], y[ok]
    if len(np.unique(y2)) < 2 or len(s2) < 8:
        emit(metric, "", int(ok.sum()), query_set=group, definition=definition,
             stage=stage, k=k, notes="NOT MEASURED: " + notes +
             f"; positives={int(y2.sum())} negatives={int((1 - y2).sum())}")
        return None
    if len(np.unique(s2)) < 2:
        # A constant score has AUROC exactly 0.5 by the average-rank tie rule.
        # Bootstrapping it is 10,000 identical answers, so it is skipped and
        # the degeneracy is stated instead of buried.
        emit(metric, 0.5, int(ok.sum()), query_set=group, definition=definition,
             stage=stage, k=k, ci_lo=0.5, ci_hi=0.5,
             notes=notes + f"; SIGNAL IS CONSTANT at {s2[0]:.4f} on every one of these "
                           f"rows -> AUROC is 0.5 by the tie rule and the signal carries "
                           f"NO information here, by construction rather than by measurement")
        return 0.5
    pt, lo, hi = auroc_bootstrap_ci(s2, y2, cluster_ids=None)
    clo = chi = ""
    if clustered:
        cids = cl[ok]
        if pd.notna(cids).all():
            _, c1, c2 = auroc_bootstrap_ci(s2, y2, cluster_ids=cids)
            clo, chi = r6(c1), r6(c2)
    emit(metric, r6(pt), int(ok.sum()), query_set=group, definition=definition,
         stage=stage, k=k, ci_lo=r6(lo), ci_hi=r6(hi),
         cluster_ci_lo=clo, cluster_ci_hi=chi, notes=notes)
    return pt


cluster_ids = df.pair_id.fillna("__NA__").values

for definition, k in DEFS:
    for st in STAGES:
        y_all = labels[(definition, st)]
        for group, mask in GROUPS:
            yg = y_all[mask]
            cl = cluster_ids[mask]
            for v in VARIANTS:
                s = df.loc[mask, f"sc_{v}_{st}"].values.astype(float)
                is_primary = (v == PRIMARY)
                metric = ("auroc_statute_consistency" if is_primary
                          else f"auroc_statute_consistency_{v}")
                note = (f"signal=statute_consistency variant={v}"
                        + (" [PRIMARY]" if is_primary else "")
                        + ("; ORACLE -- reads the gold expected_corpora, NOT DEPLOYABLE"
                           if v == "A4_oracle_gold" else ""))
                # clustered CI only for the primary variant, pooled + per set
                auroc_row(metric, s, yg, cl, group, definition, st, k, note,
                          clustered=is_primary)
            # the generic signals, same rows, same labels -- the ablation picture
            if group == "ALL":
                gap_term = 1.0 - np.minimum(df.loc[mask, "score_gap"].values / 0.3, 1.0)
                for name, arr, nt in [
                    ("top_k_mean", df.loc[mask, "top_k_mean"].values.astype(float),
                     "mean of the top-5 similarity scores; blend weight 0.55"),
                    ("gap_term", gap_term.astype(float),
                     "1-min(score_gap/0.3,1); blend weight 0.15"),
                    ("entity_coverage", df.loc[mask, "entity_coverage"].values.astype(float),
                     "substring match of query entities in top-5 chunk text; blend weight 0.30"),
                    ("composite", df.loc[mask, "composite"].values.astype(float),
                     "the DEPLOYED score, weights 0.55/0.15/0.30"),
                    ("max_score", df.loc[mask, "max_score"].values.astype(float),
                     "single best similarity; not part of the composite"),
                ]:
                    auroc_row("ablation_auroc", arr, yg, cl, group, definition, st, k,
                              f"signal={name}; {nt}", clustered=(definition == "retrieved@k"))
                sp = df.loc[mask, f"sc_{PRIMARY}_{st}"].values.astype(float)
                auroc_row("ablation_auroc", sp, yg, cl, group, definition, st, k,
                          f"signal=statute_consistency; FOURTH ROW; variant={PRIMARY}; "
                          "fraction of retrieved chunks whose statute_code is admissible "
                          "for the query+date", clustered=(definition == "retrieved@k"))

        # ECE -- pooled and per set, primary variant plus the generic ones
        for group, mask in GROUPS:
            yg = y_all[mask]
            if len(np.unique(yg)) < 2:
                continue
            for v in VARIANTS:
                s = df.loc[mask, f"sc_{v}_{st}"].values.astype(float)
                ok = ~np.isnan(s)
                if ok.sum() < 10:
                    continue
                metric = ("ece_statute_consistency" if v == PRIMARY
                          else f"ece_statute_consistency_{v}")
                emit(metric, r6(ece(s[ok], yg[ok])), int(ok.sum()), query_set=group,
                     definition=definition, stage=st, k=k,
                     notes=f"variant={v}; 10 quantile bins; |mean score - accuracy| "
                           f"averaged over bins weighted by bin count. NOTE: "
                           f"statute_consistency is a CONSISTENCY fraction, not a "
                           f"probability of being right, so its ECE is a "
                           f"miscalibration-as-a-probability reading, not a defect")
            if group == "ALL":
                for name in ("composite", "max_score", "top_k_mean", "entity_coverage"):
                    a = df.loc[mask, name].values.astype(float)
                    emit("ece_reference", r6(ece(a, yg)), int(mask.sum()), query_set=group,
                         definition=definition, stage=st, k=k,
                         notes=f"signal={name}; 10 quantile bins; reference point for the row above")
        print(f"   grid done: {definition}/{st}   t={time.time() - t0:.0f}s")


# ======================================================================
# PART 4 -- paired comparisons
# ======================================================================
print("== PART 4: paired bootstrap comparisons ==")
for definition, k in DEFS:
    for st in STAGES:
        y_all = labels[(definition, st)]
        for group, mask in GROUPS:
            yg = y_all[mask]
            s = df.loc[mask, f"sc_{PRIMARY}_{st}"].values.astype(float)
            ok = ~np.isnan(s)
            if len(np.unique(yg[ok])) < 2 or ok.sum() < 8:
                for other in ("composite", "max_score"):
                    emit(f"auroc_diff_statute_consistency_vs_{other}", "", int(ok.sum()),
                         query_set=group, definition=definition, stage=st, k=k,
                         notes="NOT MEASURED: one class absent or too few rows")
                continue
            for other in ("composite", "max_score"):
                b = df.loc[mask, other].values.astype(float)[ok]
                d = paired_bootstrap_auroc_diff(s[ok], b, yg[ok])
                emit(f"auroc_diff_statute_consistency_vs_{other}", r6(d["diff"]),
                     int(ok.sum()), query_set=group, definition=definition, stage=st, k=k,
                     ci_lo=r6(d["ci_lo"]), ci_hi=r6(d["ci_hi"]),
                     notes=f"PAIRED bootstrap, same rows: AUROC(statute_consistency "
                           f"[{PRIMARY}]) - AUROC({other}); p_two_sided={d['p_two_sided']:.4f}; "
                           + ("DIFFERENT" if d["p_two_sided"] < 0.05 else
                              "NOT DISTINGUISHABLE") + f" from {other}")
        print(f"   paired done: {definition}/{st}   t={time.time() - t0:.0f}s")


# ======================================================================
# PART 5 -- entity_coverage, both ways
# ======================================================================
print("== PART 5: entity_coverage recomputed from the payload ==")


def ec_payload(rid, entities):
    """entity_coverage using the section_number PAYLOAD, not chunk text."""
    if not entities:
        return ENTITY_NEUTRAL, True
    ch = stages.get(rid, {}).get("reranked_15", [])[:5]
    refs = [f"{c.get('corpus')} {c.get('section_number')}"
            for c in ch if c.get("section_number")]
    hits = sum(1 for e in entities if any(same_section(e, r) for r in refs))
    return hits / len(entities), False


def ec_substring(rid, entities):
    """Reconstruct the DEPLOYED substring rule from the full Qdrant text of the
    top-5 reranked chunks. Used to validate the top-5 reconstruction against
    the logged value."""
    if not entities:
        return ENTITY_NEUTRAL, 0
    ch = stages.get(rid, {}).get("reranked_15", [])[:5]
    parts, missing = [], 0
    for c in ch:
        key = (c.get("doc"), str(c.get("page")), c.get("section_number") or "",
               (c.get("text_head") or "")[:160])
        t = full_text.get(key)
        if t is None:
            missing += 1
            t = c.get("text_head") or ""
        parts.append(t)
    hay = " ".join(parts).lower()
    return sum(1 for e in entities if e.lower() in hay) / len(entities), missing


ec_pay, ec_sub, ec_miss = [], [], 0
for rid, ents in zip(df.req_id, df.entities):
    p, _ = ec_payload(rid, ents)
    s, m = ec_substring(rid, ents)
    ec_pay.append(p)
    ec_sub.append(s)
    ec_miss += m
df["ec_payload"] = ec_pay
df["ec_substring_recomputed"] = ec_sub

logged = df["entity_coverage"].values.astype(float)
recon = df["ec_substring_recomputed"].values.astype(float)
payl = df["ec_payload"].values.astype(float)
dev = np.abs(logged - recon)

off = np.flatnonzero(dev > 1e-4)
off_desc = "; ".join(
    f"req_id={df.req_id.iloc[i]} set={df.query_set.iloc[i]} logged={logged[i]:.2f} "
    f"reconstructed={recon[i]:.2f} entities={df.entities.iloc[i]}" for i in off[:5])
emit("entity_coverage_substring_reconstruction_max_abs_dev", r6(dev.max()), len(df),
     notes=f"|logged entity_coverage - reconstructed substring rule| over the top-5 "
           f"RERANKED chunks with full Qdrant text; rows off by >1e-4: "
           f"{len(off)} of {len(df)}; chunk texts not found by (doc,page,section,head) "
           f"key: {ec_miss}. This validates that the top-5 reconstruction matches what "
           f"the deployed system saw, which is what makes the payload version comparable. "
           f"Deviating rows: {off_desc or 'NONE'}")
emit("entity_coverage_substring_reconstruction_rows_off", float(len(off)), len(df),
     notes="rows where the reconstruction does not match the logged value. Any such row "
           "is a PRE-FIX log: entity_coverage used to default to 1.0 when no entity was "
           "extracted, and was changed to ENTITY_NEUTRAL=0.5. REPORTED, not absorbed")
emit("entity_coverage_logged_mean", r6(logged.mean()), len(df),
     notes="the DEPLOYED value: substring match of query entities in top-5 chunk text")
emit("entity_coverage_payload_mean", r6(payl.mean()), len(df),
     notes="recomputed: entity matched against the section_number PAYLOAD of the "
           "top-5 reranked chunks via metrics_lib.same_section()")
emit("entity_coverage_mean_signed_diff", r6((payl - logged).mean()), len(df),
     notes="payload minus logged; negative means the substring rule was OVER-counting")
emit("entity_coverage_mean_abs_diff", r6(np.abs(payl - logged).mean()), len(df),
     notes="mean |payload - logged|")
ch_up = int((payl > logged + 1e-9).sum())
ch_dn = int((payl < logged - 1e-9).sum())
emit("entity_coverage_rows_changed", float(ch_up + ch_dn), len(df),
     notes=f"rows where the payload value differs from the logged value; "
           f"payload HIGHER on {ch_up}, LOWER on {ch_dn} "
           f"(lower = the substring rule had a false match)")
emit("entity_coverage_distinct_values_logged", float(len(set(np.round(logged, 4)))), len(df),
     notes="distinct logged values: " + ", ".join(
         f"{v:.2f}" for v in sorted(set(np.round(logged, 4)))))
emit("entity_coverage_distinct_values_payload", float(len(set(np.round(payl, 4)))), len(df),
     notes="distinct payload values: " + ", ".join(
         f"{v:.2f}" for v in sorted(set(np.round(payl, 4)))))
emit("entity_coverage_max_logged", r6(logged.max()), len(df),
     notes="GAPS.md claims entity_coverage can exceed 1.0. Verified against these logs.")
emit("entity_coverage_neutral_default_fraction", r6(float((logged == ENTITY_NEUTRAL).mean())),
     len(df), notes=f"fraction sitting exactly at ENTITY_NEUTRAL=0.5; "
                    f"entity_coverage_default_used flag agrees on "
                    f"{int((df.entity_default_used.astype(bool) == (logged == 0.5)).sum())} "
                    f"of {len(df)} rows. GAPS.md claims a free 0.30 neutral default -- "
                    f"the deployed constant is 0.5 weighted at 0.30, i.e. 0.15 of composite")
lay = df.query_set == "layman_situation"
emit("entity_coverage_layman_all_neutral", r6(float((logged[lay.values] == 0.5).mean())),
     int(lay.sum()), query_set="layman_situation",
     notes="fraction of layman rows sitting exactly at 0.5 -- no layman query names a section")

for definition, k in DEFS:
    st = "raw_15"
    y = labels[(definition, st)]
    for group, mask in GROUPS:
        yg = y[mask]
        if len(np.unique(yg)) < 2:
            continue
        for nm, arr in (("logged_substring", logged), ("payload_section_number", payl)):
            a = arr[mask]
            if len(np.unique(a)) < 2:
                emit(f"auroc_entity_coverage_{nm}", "", int(mask.sum()), query_set=group,
                     definition=definition, stage=st, k=k,
                     notes=f"NOT MEASURED: signal is CONSTANT ({a[0]:.2f}) on these rows")
                continue
            pt, lo, hi = auroc_bootstrap_ci(a, yg)
            emit(f"auroc_entity_coverage_{nm}", r6(pt), int(mask.sum()), query_set=group,
                 definition=definition, stage=st, k=k, ci_lo=r6(lo), ci_hi=r6(hi),
                 notes=f"entity_coverage computed the {nm} way")
        if len(np.unique(logged[mask])) > 1 and len(np.unique(payl[mask])) > 1:
            d = paired_bootstrap_auroc_diff(payl[mask], logged[mask], yg)
            emit("auroc_diff_entity_coverage_payload_vs_logged", r6(d["diff"]),
                 int(mask.sum()), query_set=group, definition=definition, stage=st, k=k,
                 ci_lo=r6(d["ci_lo"]), ci_hi=r6(d["ci_hi"]),
                 notes=f"PAIRED bootstrap: AUROC(payload) - AUROC(logged substring); "
                       f"p_two_sided={d['p_two_sided']:.4f}")

# constancy claim from Wave 2
const_frac = float(((logged == 0.5)).mean())
emit("entity_coverage_constant_fraction", r6(const_frac), len(df),
     notes="Wave 2 reported entity_coverage is CONSTANT for 43.4% of queries "
           "(the neutral-default rows). Recomputed here.")
print(f"   logged mean {logged.mean():.4f}  payload mean {payl.mean():.4f}  "
      f"max_dev_vs_reconstruction {dev.max():.6f}")


# ======================================================================
# PART 6 -- the normaliser artefact rate
# ======================================================================
print("== PART 6: normaliser artefact rate ==")
import fitz  # noqa: E402
from ingest.chunk import SECTION_NORMALISE  # noqa: E402

PDF_DIR = ROOT / "tests" / "data"
population = []
for p in sorted(PDF_DIR.glob("*.pdf")):
    doc = fitz.open(str(p))
    for i in range(doc.page_count):
        lines = (doc.load_page(i).get_text("text") or "").split("\n")
        for j, ln in enumerate(lines):
            m = SECTION_NORMALISE.match(ln)      # (?m)^ anchored -> per-line match
            if m:
                population.append({
                    "doc": p.name, "page": i + 1, "line_no": j, "num": m.group(1),
                    "line": ln.strip()[:200],
                    "ctx": " ".join(lines[j:j + 3]).strip()[:300]})
    doc.close()

rng = np.random.default_rng(SEED)
sample_idx = sorted(rng.choice(len(population), size=100, replace=False).tolist())
sample = [population[i] for i in sample_idx]

# Manual classification. Each entry is (population index, class). Classified by
# READING the line and its two following lines.
#   GENUINE   the heading of a substantive provision, printed in the body of
#             the Act. In the IPC/CrPC the title is followed by an em-dash and
#             the provision text; in the BNS the number is followed directly by
#             the provision text.
#   CONTENTS  a row of the ARRANGEMENT OF SECTIONS index at the front of the
#             PDF: the section number and its title, no body, immediately
#             followed by the next numbered title or a CHAPTER heading.
#   FOOTNOTE  the numbered amendment-footnote apparatus at the foot of a page
#             ("2. Ins. by Act 25 of 2005, s. 44 (w.e.f. 23-6-2005)."). The
#             number is a FOOTNOTE MARKER, not a section number at all.
NORMALISER_LABELS = {
    17: "CONTENTS", 20: "CONTENTS", 36: "CONTENTS", 45: "CONTENTS", 102: "CONTENTS",
    112: "GENUINE", 167: "GENUINE", 204: "GENUINE",
    240: "GENUINE", 386: "GENUINE", 415: "GENUINE", 434: "GENUINE", 455: "GENUINE",
    469: "GENUINE", 472: "GENUINE",
    627: "CONTENTS", 642: "CONTENTS", 646: "CONTENTS", 677: "CONTENTS", 705: "CONTENTS",
    724: "CONTENTS", 738: "CONTENTS", 770: "CONTENTS", 786: "CONTENTS", 788: "CONTENTS",
    792: "CONTENTS", 808: "CONTENTS", 833: "CONTENTS", 846: "CONTENTS", 888: "CONTENTS",
    932: "CONTENTS", 938: "CONTENTS", 997: "CONTENTS", 1021: "CONTENTS", 1067: "CONTENTS",
    1074: "CONTENTS", 1125: "CONTENTS", 1136: "CONTENTS", 1139: "CONTENTS",
    1174: "FOOTNOTE", 1235: "FOOTNOTE",
    1295: "GENUINE", 1322: "GENUINE",
    1358: "FOOTNOTE", 1360: "FOOTNOTE",
    1384: "GENUINE",
    1398: "FOOTNOTE", 1430: "FOOTNOTE",
    1468: "GENUINE",
    1551: "FOOTNOTE",
    1571: "GENUINE", 1609: "GENUINE", 1641: "GENUINE",
    1654: "FOOTNOTE",
    1685: "GENUINE", 1748: "GENUINE",
    1844: "FOOTNOTE",
    1861: "GENUINE", 1867: "GENUINE", 1901: "GENUINE",
    1955: "FOOTNOTE", 1993: "FOOTNOTE", 2003: "FOOTNOTE",
    2025: "CONTENTS", 2078: "CONTENTS", 2132: "CONTENTS", 2143: "CONTENTS",
    2156: "CONTENTS", 2184: "CONTENTS", 2216: "CONTENTS", 2227: "CONTENTS",
    2325: "CONTENTS", 2342: "CONTENTS", 2369: "CONTENTS", 2425: "CONTENTS",
    2433: "CONTENTS", 2456: "CONTENTS", 2459: "CONTENTS", 2515: "CONTENTS",
    2526: "CONTENTS", 2537: "CONTENTS",
    2564: "GENUINE",
    2575: "FOOTNOTE", 2576: "FOOTNOTE",
    2658: "GENUINE", 2771: "GENUINE", 2845: "GENUINE", 2911: "GENUINE", 2931: "GENUINE",
    2937: "GENUINE",
    2989: "FOOTNOTE",
    3019: "GENUINE", 3024: "GENUINE",
    3051: "FOOTNOTE",
    3059: "GENUINE", 3121: "GENUINE", 3129: "GENUINE", 3172: "GENUINE", 3175: "GENUINE",
    3259: "FOOTNOTE",
}

assert len(population) == 3302, f"population changed: {len(population)}"
assert set(NORMALISER_LABELS) == set(sample_idx), (
    "the manual labels no longer line up with the drawn sample -- "
    "STOP, do not report a rate")

cls = collections.Counter(NORMALISER_LABELS[i] for i in sample_idx)
n_s = len(sample_idx)
artefact_strict = cls["CONTENTS"] + cls["FOOTNOTE"]
p, lo, hi = wilson(artefact_strict, n_s)
emit("normaliser_rewrites_total", float(len(population)), len(population),
     notes="lines rewritten into 'Section N.' form by ingest.chunk.SECTION_NORMALISE "
           "across the four source PDFs in tests/data/, extracted with PyMuPDF exactly "
           "as ingest/extract.py does")
emit("normaliser_artefact_rate", r6(p), n_s, ci_lo=r6(lo), ci_hi=r6(hi),
     notes=f"PRIMARY (strict): the rewritten line is NOT the heading of a substantive "
           f"provision. CONTENTS={cls['CONTENTS']} + FOOTNOTE={cls['FOOTNOTE']} out of "
           f"{n_s}; GENUINE={cls['GENUINE']}. 95% Wilson interval. Sample: 100 drawn "
           f"without replacement from all {len(population)} rewrites, "
           f"numpy default_rng(SEED={SEED}), labels in NORMALISER_LABELS")
pf, lof, hif = wilson(cls["FOOTNOTE"], n_s)
emit("normaliser_artefact_rate_number_not_a_section", r6(pf), n_s,
     ci_lo=r6(lof), ci_hi=r6(hif),
     notes=f"LENIENT: only lines where the digits are not a section number at all "
           f"(amendment-footnote markers, 'N. Subs. by Act ...'). {cls['FOOTNOTE']}/{n_s}. "
           f"95% Wilson interval")
pc, loc_, hic = wilson(cls["CONTENTS"], n_s)
emit("normaliser_contents_rate", r6(pc), n_s, ci_lo=r6(loc_), ci_hi=r6(hic),
     notes=f"table-of-contents index rows: right number, no provision body. "
           f"{cls['CONTENTS']}/{n_s}. 95% Wilson interval. ingest.chunk."
           f"is_contents_entry() is designed to drop these DOWNSTREAM -- this rate "
           f"is measured at REWRITE time, before that filter")
pg, log_, hig = wilson(cls["GENUINE"], n_s)
emit("normaliser_genuine_rate", r6(pg), n_s, ci_lo=r6(log_), ci_hi=r6(hig),
     notes=f"genuine substantive provision headings. {cls['GENUINE']}/{n_s}")

# how many of the sampled lines actually survived into the index?
qd_sections = {(pl["corpus"], str(pl["page"]), pl["section_number"])
               for pl in (p_.payload for p_ in pts) if pl.get("section_number")}
DOC2CORPUS = {"a2019-35.pdf": "CPA", "Bharatiya_Nyaya_Sanhita_2023.pdf": "BNS",
              "repealedfileopen.pdf": "IPC",
              "the_code_of_criminal_procedure,_1973.pdf": "CRPC"}
surv = collections.Counter()
for i in sample_idx:
    s_ = population[i]
    key = (DOC2CORPUS[s_["doc"]], str(s_["page"]), s_["num"])
    surv[(NORMALISER_LABELS[i], key in qd_sections)] += 1
emit("normaliser_artefact_survival_to_index",
     r6((surv[("CONTENTS", True)] + surv[("FOOTNOTE", True)]) / max(1, artefact_strict)),
     artefact_strict,
     notes="fraction of the SAMPLED artefacts that still appear in Qdrant as a "
           "(corpus, page, section_number) triple, i.e. survived the downstream "
           "contents/footnote filters. Counts: "
           + "; ".join(f"{c}/{'in_index' if b else 'dropped'}={n}"
                       for (c, b), n in sorted(surv.items())))
print(f"   population {len(population)}; classes {dict(cls)}; "
      f"artefact_rate {p:.3f} [{lo:.3f}, {hi:.3f}]")

# examples for the explanation block
examples = {c: [population[i] for i in sample_idx if NORMALISER_LABELS[i] == c][:12]
            for c in ("GENUINE", "CONTENTS", "FOOTNOTE")}
print("   examples written to stdout for the explanation block:")
for c, ee in examples.items():
    for e in ee[:10]:
        print(f"     {c:8s} {e['doc'][:20]} p{e['page']:>3} n={e['num']:>5} :: {e['ctx'][:150]}")


# ======================================================================
# WRITE
# ======================================================================
out = pd.DataFrame(rows_out, columns=[
    "metric", "query_set", "definition", "stage", "k", "value", "n",
    "ci_lo", "ci_hi", "cluster_ci_lo", "cluster_ci_hi", "notes"])
OUT.parent.mkdir(parents=True, exist_ok=True)
out.to_csv(OUT, index=False)
print(f"\nwrote {OUT}  ({len(out)} rows)  total {time.time() - t0:.0f}s")
