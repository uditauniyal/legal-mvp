"""check05 -- PAIRED CHECK for exp05_robustness.py.

Wave 2, Subagent 5.  Four independent checks on results/robustness.csv.

WHY THIS FILE IS ALLOWED TO COMPUTE THINGS ITSELF
    Everywhere else in this project the rule is "import metrics_lib, never
    reimplement".  A paired check is the one deliberate exception, because a
    check that calls the same function as the thing it is checking cannot
    detect a bug in that function -- it would agree with a wrong answer just
    as happily as with a right one.  The re-derivations below therefore go
    through DIFFERENT code on purpose, and that independence is confined to
    this file.  Nothing here is imported by anything else.

THE FOUR CHECKS

  CHECK 1  Layman retrieval rate, re-derived from the raw JSONL.
           Reads experiments/stages.jsonl and runs/eval_*/eval_summary.jsonl
           directly and matches gold to retrieved chunks with a hand-rolled
           comparison -- no load_logs(), no correctness_label(), no
           same_section().  Asserts it equals the value exp05 wrote.

  CHECK 2  THE MAIN ONE.  For every headline value that is an AVERAGE over
           clustered rows, the CLUSTERED interval must be at least as wide as
           the NAIVE one.  A clustered interval that comes out NARROWER is a
           bug in either the clustering or the statistic, and is reported
           loudly rather than explained away.

  CHECK 3  The clustered interval's width is re-derived ANALYTICALLY, without
           any bootstrap at all.  For a mean over equal-sized clusters the
           cluster-robust standard error is std(cluster means)/sqrt(#clusters)
           and the naive one is sqrt(p(1-p)/n).  If the bootstrap is doing what
           it claims, its two interval widths must track 1.96 * those two
           standard errors.  This is what proves the widening is real and not
           an artefact of how the resample was coded.

  CHECK 4  The "naive = row bootstrap" substitution is validated against the
           closed-form Wilson interval on the same counts.  exp05 uses a row
           bootstrap rather than Wilson for its naive column so that the only
           difference between the naive and clustered columns is the cluster
           definition; this check is the evidence that the substitution does
           not itself move the number.

  Two DIAGNOSTICS also print, and neither is an assertion.  The first is the
  per-query-set clustering structure -- how often the variants of one situation
  all succeed or all fail together, and the resulting design effect -- which is
  what explains why clustering widens some sets and narrows others.  The
  second:

  the paired IPC-vs-BNS gap is a
  WITHIN-cluster difference, where clustering is expected to NARROW rather
  than widen.  The mechanism is measured (the within-situation correlation
  between the IPC and BNS outcomes) and printed, so the narrowing can be
  confirmed as pairing rather than assumed to be.

ZERO API calls.  Reads only.  Writes nothing.

Run:  ./venv/Scripts/python.exe experiments/check05_robustness_check.py
"""
from __future__ import annotations

import glob
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "results" / "robustness.csv"

FAILURES: list[str] = []
LOUD: list[str] = []


def fail(msg):
    FAILURES.append(msg)
    print("  FAIL: " + msg)


def loud(msg):
    LOUD.append(msg)
    print("  !! LOUD: " + msg)


def ok(msg):
    print("  ok:   " + msg)


# ------------------------------------------------------------------ helpers

def load_csv() -> pd.DataFrame:
    if not CSV.exists():
        print("results/robustness.csv does not exist -- run exp05_robustness.py first")
        sys.exit(2)
    df = pd.read_csv(CSV)
    df["restriction"] = df["notes"].fillna("").str.extract(r"restriction=([A-Za-z_]+)")
    return df


def pick(df, metric, definition=None, stage=None, restriction="none", query_set=None):
    m = df[df["metric"] == metric]
    if definition is not None:
        m = m[m["definition"] == definition]
    if stage is not None:
        m = m[m["stage"].fillna("") == stage]
    if query_set is not None:
        m = m[m["query_set"] == query_set]
    m = m[m["restriction"] == restriction]
    if len(m) != 1:
        raise AssertionError(
            "expected exactly 1 row for metric=%s defn=%s stage=%s restriction=%s, got %d"
            % (metric, definition, stage, restriction, len(m)))
    return m.iloc[0]


def w(row, lo, hi):
    a, b = row[lo], row[hi]
    if pd.isna(a) or pd.isna(b):
        return float("nan")
    return float(b) - float(a)


# ------------------------------------------------------------------ CHECK 1

def independent_layman_rate() -> tuple[int, int]:
    """Layman gold-in-raw_15 rate, computed WITHOUT metrics_lib.

    Deliberately mirrors the hand-rolled matcher in check03_stage_effect.py:
    a chunk hits when its `corpus` equals the gold statute and its
    AUTHORITATIVE `section_number` equals the gold number, both squashed of
    whitespace and upper-cased.  Deduplication on req_id is done here too, by
    last-wins, matching load_logs().
    """
    stages = {}
    with open(ROOT / "experiments" / "stages.jsonl", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                r = json.loads(line)
                stages[r["req_id"]] = r

    gold = {}
    for f in glob.glob(str(ROOT / "runs" / "eval_*" / "eval_summary.jsonl")):
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if r.get("req_id"):
                    gold[r["req_id"]] = r          # last wins

    def squash(s):
        return re.sub(r"\s+", "", str(s or "")).upper()

    k = n = 0
    for rid, rec in stages.items():
        g = gold.get(rid)
        if not g or g.get("category") != "layman_situation":
            continue
        exp = g.get("expected_sections") or []
        if not exp:
            continue
        n += 1
        hit = False
        for gs in exp:
            parts = str(gs).split(" ", 1)
            if len(parts) != 2:
                continue
            act, num = parts[0].upper(), squash(parts[1])
            for c in rec.get("raw_15", []):
                if str(c.get("corpus") or "").upper() != act:
                    continue
                if squash(c.get("section_number")) == num:
                    hit = True
                    break
            if hit:
                break
        k += int(hit)
    return k, n


def check1(df):
    print("-" * 78)
    print("CHECK 1  layman raw_15 rate re-derived from raw JSONL, no metrics_lib")
    print("-" * 78)
    k, n = independent_layman_rate()
    rate = k / n if n else float("nan")
    row = pick(df, "layman_rate", "retrieved@15", "raw_15", "none")
    got = float(row["value"])
    print("  independent route : %d/%d = %.6f" % (k, n, rate))
    print("  exp05 CSV         : %.6f  (n=%s)" % (got, row["n"]))
    if int(row["n"]) != n:
        fail("layman n disagrees: independent %d vs CSV %s" % (n, row["n"]))
    if abs(rate - got) > 1e-9:
        fail("layman rate disagrees: independent %.6f vs CSV %.6f" % (rate, got))
    else:
        ok("layman rate agrees to 1e-9 by an independent route")
    print()
    return k, n


# ------------------------------------------------------------------ CHECK 2

# statistics that are AVERAGES over clustered rows -> clustering MUST NOT narrow
AVERAGING_METRICS = ("layman_rate", "auroc_composite", "auroc_max_score",
                     "paired_rate_ipc", "paired_rate_bns")
# statistics that are WITHIN-cluster differences -> clustering is expected to narrow
DIFFERENCE_METRICS = ("paired_gap_ipc_minus_bns", "auroc_diff_composite_minus_max")

TOL = 1.02      # same tolerance exp05 uses; percentile bootstrap on a discrete
                # statistic is lumpy and ratios within 2% are noise


def _pooled_design_effect(sub: pd.DataFrame, col: str) -> float:
    """Analytic (clustered SE / naive SE) for the MEAN of `col`, pooled over
    everything in `sub`.

    NOT the right statistic for explaining a narrowing, and kept only so the
    two can be printed side by side.  It mixes the differences BETWEEN query
    sets into the cluster-level variance -- the layman set retrieves at 15%
    and the paired IPC arm at 88%, and that spread inflates the cluster
    variance regardless of what happens WITHIN a situation.  It therefore
    reports > 1 even on subsets where clustering demonstrably narrows.
    """
    if len(sub) < 3:
        return float("nan")
    p = float(sub[col].mean())
    if p in (0.0, 1.0):
        return float("nan")
    cm = sub.groupby("pair_id")[col].mean()
    if len(cm) < 2:
        return float("nan")
    se_naive = math.sqrt(p * (1 - p) / len(sub))
    se_clust = float(cm.std(ddof=1) / math.sqrt(len(cm)))
    if se_naive == 0:
        return float("nan")
    return se_clust / se_naive


def label_design_effect(sub: pd.DataFrame, col: str) -> float:
    """Row-weighted mean of the WITHIN-query-set design effects.

    This is the statistic that actually predicts whether clustering widens,
    because it isolates the within-situation correlation from the differences
    between query sets.  Above 1 means the phrasings of a situation AGREE more
    than chance, so clustering must widen.  Below 1 means they DISAGREE more
    than chance -- which is by construction in the contrastive sets, where the
    IPC-named and BNS-named phrasings of one situation are built to come out
    differently -- and clustering legitimately narrows.

    Confirmed directly: AUROC on the two positively-correlated sets widens
    under clustering (width_ratio 0.688) and on the two contrastive sets
    narrows (width_ratio 1.197).  See section 6 of results/_explain_w2_s5.md.
    """
    tot, acc = 0, 0.0
    for _, g in sub.groupby("query_set"):
        de = _pooled_design_effect(g, col)
        if math.isnan(de):
            continue
        acc += de * len(g)
        tot += len(g)
    return acc / tot if tot else float("nan")


def restricted_frames(df):
    """The same subsets exp05 used, rebuilt here and VERIFIED against the row
    counts exp05 recorded, so this file is not merely assuming they match."""
    import experiments.exp05_robustness as e
    lab = e.build_frame()
    frames = {
        "none": lab,
        "exclude_legacy_criminal":
            lab[~lab["query_set"].astype(str).str.startswith("criminal")],
        "exclude_entity_default_used": lab[lab["entity_default_used"] != True],  # noqa: E712
        "exclude_filter_applied_null": lab[lab["filter_applied"].notna()],
        "one_variant_per_pair_id": e.one_per_cluster(lab),
    }
    recorded = {}
    for _, r in df[df["metric"] == "n_rows_after_restriction"].iterrows():
        recorded[r["restriction"]] = int(r["value"])
    for name, n in recorded.items():
        if name in frames and len(frames[name]) != n:
            fail("restriction %s rebuilt with %d rows but exp05 recorded %d -- the "
                 "check is not looking at the same subset" % (name, len(frames[name]), n))
    return frames


# which correctness column backs each (definition, stage) pair
LABEL_COL = {
    ("retrieved@15", "raw_15"): "lab_retrieved_raw_15",
    ("retrieved@15", "reranked_15"): "lab_retrieved_reranked_15",
    ("retrieved@15", "filtered_n"): "lab_retrieved_filtered_n",
    ("cited", ""): "lab_cited",
    ("grounded", ""): "lab_grounded",
}
QSET_FILTER = {
    "layman_rate": "layman_situation",
    "paired_rate_ipc": "paired_recodification",
    "paired_rate_bns": "paired_recodification",
}


def check2(df):
    """Clustering must WIDEN wherever the rows inside a situation are
    POSITIVELY correlated.  Where they are NEGATIVELY correlated, narrowing is
    correct and the check must say so rather than fail blindly.

    The test is therefore: every narrowing must be ACCOUNTED FOR by a measured
    negative intra-cluster correlation on that exact subset.  A narrowing with
    NON-negative correlation is an unexplained narrowing and a hard failure --
    that is the case that would indicate a real bug.
    """
    print("-" * 78)
    print("CHECK 2  clustering must widen wherever intra-cluster correlation is > 0")
    print("-" * 78)
    frames = restricted_frames(df)
    sub = df[df["metric"].isin(AVERAGING_METRICS)].copy()
    sub = sub[sub["ci_lo"].notna() & sub["cluster_ci_lo"].notna()]
    n_checked = n_narrow = n_unexplained = 0
    for _, r in sub.iterrows():
        wn, wc = w(r, "ci_lo", "ci_hi"), w(r, "cluster_ci_lo", "cluster_ci_hi")
        # A zero-width interval means the statistic was constant in every
        # resample -- e.g. layman `grounded`, which is 0/120 with no positives
        # at all. There is no ratio to form and nothing to check.
        if math.isnan(wn) or math.isnan(wc) or wn == 0 or wc == 0:
            continue
        # an arm with exactly one row per cluster is a no-op case: clustering
        # cannot change anything there, so equality is the correct outcome
        if "one row per cluster in this arm" in str(r["notes"]):
            continue
        n_checked += 1
        ratio = wn / wc
        if ratio <= TOL:
            continue
        n_narrow += 1
        # measure the intra-cluster correlation on this exact subset
        stage = "" if pd.isna(r["stage"]) else str(r["stage"])
        col = LABEL_COL.get((r["definition"], stage))
        frame = frames.get(r["restriction"])
        de = float("nan")
        if col is not None and frame is not None:
            f = frame
            qs = QSET_FILTER.get(r["metric"])
            if qs:
                f = f[f["query_set"] == qs]
            de = label_design_effect(f, col)
            de_pooled = _pooled_design_effect(f, col)
        else:
            de_pooled = float("nan")
        verdict = ("EXPLAINED by negative within-situation correlation"
                   if (not math.isnan(de) and de < 1.0) else "UNEXPLAINED")
        if verdict == "UNEXPLAINED":
            n_unexplained += 1
        loud("clustered NARROWER: metric=%s defn=%s stage=%s restriction=%s  "
             "naive_w=%.4f clustered_w=%.4f width_ratio=%.3f  "
             "within_set_DE=%s (pooled_DE=%s)  -> %s"
             % (r["metric"], r["definition"], stage, r["restriction"], wn, wc,
                ratio, ("%.3f" % de) if not math.isnan(de) else "NOT MEASURED",
                ("%.3f" % de_pooled) if not math.isnan(de_pooled) else "n/a",
                verdict))
    print("  checked %d averaging values; %d narrowed under clustering; "
          "%d of those UNEXPLAINED" % (n_checked, n_narrow, n_unexplained))
    if n_unexplained:
        # Deliberately left FAILING.  The honest position is that these are not
        # accounted for, and the fix is not to keep weakening the test until it
        # passes.  What is known: the cluster bootstrap machinery reproduces the
        # analytic design effect to four significant figures on a clean case
        # (CHECK 3, 1.933 vs 1.932), and the narrowing is stable across five
        # seeds, so it is neither a coding error in the resampler nor Monte
        # Carlo noise.  What is NOT known: AUROC is a RANK statistic, and the
        # mean-based design-effect argument used above does not transfer to it
        # directly -- its cluster-robust variance depends on the covariance of
        # placement values, which was not derived here.  Until that is settled,
        # the clustered AUROC intervals on these restricted subsets should not
        # be relied on.  Recorded in results/_explain_w2_s5.md section 6/7.
        fail("%d narrowings are NOT accounted for by within-situation outcome "
             "correlation -- all are AUROC (a rank statistic) on restricted "
             "subsets; UNRESOLVED, see _explain_w2_s5.md sections 6 and 7"
             % n_unexplained)
    else:
        ok("every narrowing is accounted for by measured negative intra-cluster "
           "correlation; no unexplained narrowing")
    print()


# ------------------------------------------------------------------ CHECK 3

def check3(df, k, n):
    """Analytic re-derivation of the two interval widths -- no bootstrap."""
    print("-" * 78)
    print("CHECK 3  layman interval widths re-derived analytically (no bootstrap)")
    print("-" * 78)
    # rebuild per-cluster means by the independent route's own join
    stages = {}
    with open(ROOT / "experiments" / "stages.jsonl", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                r = json.loads(line)
                stages[r["req_id"]] = r
    gold = {}
    for f in glob.glob(str(ROOT / "runs" / "eval_*" / "eval_summary.jsonl")):
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    try:
                        r = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if r.get("req_id"):
                        gold[r["req_id"]] = r

    def squash(s):
        return re.sub(r"\s+", "", str(s or "")).upper()

    per_cluster: dict[str, list[int]] = {}
    for rid, rec in stages.items():
        g = gold.get(rid)
        if not g or g.get("category") != "layman_situation":
            continue
        exp = g.get("expected_sections") or []
        if not exp:
            continue
        hit = False
        for gs in exp:
            parts = str(gs).split(" ", 1)
            if len(parts) != 2:
                continue
            act, num = parts[0].upper(), squash(parts[1])
            for c in rec.get("raw_15", []):
                if str(c.get("corpus") or "").upper() == act and \
                        squash(c.get("section_number")) == num:
                    hit = True
                    break
            if hit:
                break
        per_cluster.setdefault(g.get("pair_id"), []).append(int(hit))

    means = np.array([np.mean(v) for v in per_cluster.values()])
    sizes = {len(v) for v in per_cluster.values()}
    p = k / n
    se_naive = math.sqrt(p * (1 - p) / n)
    se_clust = float(means.std(ddof=1) / math.sqrt(len(means)))
    icc_note = "cluster sizes %s, %d clusters" % (sorted(sizes), len(means))
    print("  %s" % icc_note)
    print("  analytic naive SE      %.5f  -> 95%% width %.4f" % (se_naive, 2 * 1.959963985 * se_naive))
    print("  analytic clustered SE  %.5f  -> 95%% width %.4f" % (se_clust, 2 * 1.959963985 * se_clust))
    print("  analytic design effect (clustered SE / naive SE) = %.3f" % (se_clust / se_naive))

    row = pick(df, "layman_rate", "retrieved@15", "raw_15", "none")
    wn, wc = w(row, "ci_lo", "ci_hi"), w(row, "cluster_ci_lo", "cluster_ci_hi")
    print("  bootstrap naive width      %.4f" % wn)
    print("  bootstrap clustered width  %.4f" % wc)
    print("  bootstrap design effect    %.3f" % (wc / wn))

    if se_clust <= se_naive:
        fail("analytic clustered SE (%.5f) is not larger than naive SE (%.5f) -- "
             "the widening claim is not supported analytically" % (se_clust, se_naive))
    else:
        ok("analytic SEs confirm clustering widens (design effect %.2f)"
           % (se_clust / se_naive))

    # the bootstrap and the analytic design effect should agree in direction and
    # roughly in size.  Percentile bootstrap on a rate near 0.15 with 30 clusters
    # is skewed, so this is a loose band, not an equality.
    de_a, de_b = se_clust / se_naive, wc / wn
    if de_b < 1.0:
        fail("bootstrap design effect %.3f < 1 -- bootstrap disagrees with analytic"
             % de_b)
    elif not (0.6 * de_a <= de_b <= 1.6 * de_a):
        loud("bootstrap design effect %.3f is far from analytic %.3f -- worth a look"
             % (de_b, de_a))
    else:
        ok("bootstrap design effect %.3f is consistent with analytic %.3f" % (de_b, de_a))
    print()


# ------------------------------------------------------------------ CHECK 4

def check4(df):
    print("-" * 78)
    print("CHECK 4  naive row bootstrap vs closed-form Wilson, on the same counts")
    print("-" * 78)
    # positive_count rows carry the Wilson interval on the rate in ci_lo/ci_hi
    pc = df[df["metric"] == "positive_count"]
    n_bad = 0
    for _, r in pc.iterrows():
        k, n = int(r["value"]), int(r["n"])
        z = 1.959963985
        p = k / n
        d = 1 + z * z / n
        c = (p + z * z / (2 * n)) / d
        h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
        lo, hi = max(0.0, c - h), min(1.0, c + h)
        if abs(lo - float(r["ci_lo"])) > 1e-9 or abs(hi - float(r["ci_hi"])) > 1e-9:
            n_bad += 1
            fail("Wilson interval mismatch for %s/%s" % (r["definition"], r["stage"]))
    if not n_bad:
        ok("all %d positive_count Wilson intervals re-derive exactly" % len(pc))

    # and the substitution itself: naive bootstrap width vs Wilson width on layman
    k, n = independent_layman_rate()
    z = 1.959963985
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    wilson_w = 2 * h
    row = pick(df, "layman_rate", "retrieved@15", "raw_15", "none")
    wn = w(row, "ci_lo", "ci_hi")
    print("  layman Wilson width %.4f vs naive bootstrap width %.4f (ratio %.3f)"
          % (wilson_w, wn, wn / wilson_w))
    if not (0.6 <= wn / wilson_w <= 1.4):
        loud("naive bootstrap and Wilson widths differ by more than 40%% -- the "
             "'naive = row bootstrap' substitution may be moving the number")
    else:
        ok("naive bootstrap agrees with Wilson; the substitution is sound")
    print()


# ------------------------------------------------------------------ mechanism

def cluster_structure():
    """NOT an assertion.  The per-query-set clustering structure that explains
    WHY clustering widens some intervals and narrows others.

    `unanimous%` is the share of situations whose variants ALL succeeded or ALL
    failed together.  High unanimity means the variants carry almost no extra
    information beyond the situation, so the effective sample size is closer to
    the number of situations than to the number of rows.

    `design_effect` is the analytic cluster-robust SE divided by the naive SE,
    for the retrieved@15 / raw_15 rate.  Above 1 means clustering WIDENS.
    Below 1 means the variants within a situation are NEGATIVELY correlated --
    which happens by construction in the contrastive sets, where the IPC-named
    and BNS-named phrasings of one situation are designed to come out
    differently.
    """
    print("-" * 78)
    print("STRUCTURE  why clustering widens some sets and narrows others")
    print("-" * 78)
    import experiments.exp05_robustness as e
    lab = e.build_frame()
    col = "lab_retrieved_raw_15"
    print("  %-24s %5s %9s %11s %14s"
          % ("query_set", "n", "clusters", "unanimous%", "design_effect"))
    for qs, sub in lab.groupby("query_set"):
        cm = sub.groupby("pair_id")[col].mean()
        p = sub[col].mean()
        if p in (0.0, 1.0) or len(cm) < 2:
            de = "NOT MEASURED"
        else:
            se_n = math.sqrt(p * (1 - p) / len(sub))
            se_c = cm.std(ddof=1) / math.sqrt(len(cm))
            de = "%.2f" % (se_c / se_n)
        unan = float(((cm == 0) | (cm == 1)).mean())
        print("  %-24s %5d %9d %10.1f%% %14s"
              % (qs, len(sub), sub["pair_id"].nunique(), 100 * unan, de))
    cm = lab.groupby("pair_id")[col].mean()
    print("  %-24s %5d %9d %10.1f%% %14s"
          % ("ALL", len(lab), len(cm), 100 * float(((cm == 0) | (cm == 1)).mean()), "-"))
    print()


def gap_mechanism(df):
    """NOT an assertion.  Measures WHY the paired gap narrows under clustering."""
    print("-" * 78)
    print("MECHANISM  the paired IPC-vs-BNS gap is a WITHIN-cluster difference")
    print("-" * 78)
    from experiments.metrics_lib import load_logs, load_stages, correctness_label

    scheme = {}
    for f in (ROOT / "eval").glob("*_queryset.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("query_id"):
                    scheme[r["query_id"]] = r.get("numbering_scheme")
    lg = load_logs()
    st = load_stages()
    lg["numbering_scheme"] = lg["query_id"].map(scheme)
    lab = lg[lg["expected_sections"].map(len) > 0].copy()
    pr = lab[lab["query_set"] == "paired_recodification"].copy()
    pr["y"] = [correctness_label({**r, "_stage": "raw_15"}, "retrieved@k", k=15, stages=st)
               for _, r in pr.iterrows()]
    piv = pr[pr["numbering_scheme"].isin(["IPC", "BNS"])].pivot_table(
        index="pair_id", columns="numbering_scheme", values="y", aggfunc="mean")
    piv = piv.dropna()
    print("  %d situations contribute BOTH an IPC and a BNS row" % len(piv))
    if len(piv) > 2 and piv["IPC"].std() > 0 and piv["BNS"].std() > 0:
        rho = float(np.corrcoef(piv["IPC"], piv["BNS"])[0, 1])
        print("  within-situation correlation between the IPC and BNS outcomes: %.3f" % rho)
        if rho > 0:
            print("  positive correlation -> the between-situation variance cancels in the")
            print("  difference, so the CLUSTERED interval on the gap is legitimately")
            print("  NARROWER.  That is pairing, not a clustering bug.")
    else:
        print("  correlation NOT MEASURED (an arm has zero variance)")
    row = pick(df, "paired_gap_ipc_minus_bns", "retrieved@15", "raw_15", "none")
    wn, wc = w(row, "ci_lo", "ci_hi"), w(row, "cluster_ci_lo", "cluster_ci_hi")
    print("  gap %.4f   naive width %.4f   clustered width %.4f   width_ratio %.3f"
          % (float(row["value"]), wn, wc, wn / wc))
    print()


# ------------------------------------------------------------------ main

def main():
    df = load_csv()
    print("=" * 78)
    print("check05 -- paired check on results/robustness.csv (%d rows)" % len(df))
    print("=" * 78)
    k, n = check1(df)
    check2(df)
    check3(df, k, n)
    check4(df)
    cluster_structure()
    gap_mechanism(df)

    print("=" * 78)
    if FAILURES:
        print("RESULT: %d ASSERTION FAILURE(S)" % len(FAILURES))
        for f in FAILURES:
            print("  FAIL: " + f)
    else:
        print("RESULT: all assertions held")
    if LOUD:
        print("LOUD WARNINGS: %d" % len(LOUD))
        for m in LOUD:
            print("  !! " + m)
    print("=" * 78)
    if FAILURES:
        raise AssertionError("check05 failed: " + " | ".join(FAILURES))


if __name__ == "__main__":
    main()
