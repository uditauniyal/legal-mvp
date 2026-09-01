"""ONE implementation of every metric in this project.

WHY THIS FILE EXISTS
    Later waves run five subagents concurrently. If each writes its own AUROC,
    they will disagree in the third decimal and the paper's tables will
    silently contradict each other. Everything imports from here. If a
    function is missing, STOP and report -- do not write a local version.

WHY THERE IS NO scikit-learn
    It is not installed, and installing into this venv previously upgraded
    starlette and broke fastapi. Every function the plan specifies is
    implementable on numpy and scipy, which are present. AUROC is a rank
    statistic; Platt scaling is a two-parameter logistic fit that
    scipy.optimize handles directly. No behaviour is lost.

THREE THINGS THAT ARE NOT OPTIONAL, and why

  1. DEDUPLICATION HAPPENS HERE, not in callers.
     runs/eval_*/eval_summary.jsonl holds 850 rows for 521 unique query_ids
     because killed-and-resumed runs append. Duplicates inflate both halves
     of every k/n proportion, and unevenly -- the repeats are whichever
     queries were mid-flight when a run died, which is a biased sample. One
     caller forgetting to dedupe is a wrong number nobody notices.

  2. "RETRIEVED" HAS THREE MEANINGS and every metric must say which.
        raw_15       what Qdrant returned, in score order
        reranked_15  the same 15, reordered by entity match
        filtered_n   what survived max(top-0.15, 0.35) and reached the model
     The published 7.5% and 15.0% layman figures are the SAME measurement at
     filtered_n and raw_15. Reporting either without its stage is how that
     confusion happened.

  3. SECTION IDENTITY IS CANONICALISED ONCE.
     Comparing "IPC Section 302" against "Section 302" and calling them
     different made a headline metric return 0.0 for its entire existence
     (defect E2). normalise_section() is the only comparison rule.

SEEDS ARE FIXED. Same input, same output, every run.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20260901
N_BOOT = 10000

STAGES = ("raw_15", "reranked_15", "filtered_n")
DEFINITIONS = ("retrieved@k", "cited", "grounded")

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------- identity

_SEC_RE = re.compile(
    r"^\s*(?:(?P<statute>[A-Za-z]{2,12})\s+)?"
    r"(?:sec(?:tion)?s?\.?|s\.)?\s*"
    r"(?P<num>\d+\s*[A-Za-z]{0,2})"
    r"\s*(?P<sub>\(\s*[0-9a-zA-Z]+\s*\))?",
    re.IGNORECASE,
)

_KNOWN_STATUTES = {"IPC", "BNS", "CRPC", "BNSS", "CPA", "IEA", "BSA",
                   "NI", "CPC", "HMA", "IT", "LSA", "CONSTITUTION"}

# Canonical output shape: an optional known statute, one colon, then a
# non-empty remainder containing no further colon.
_CANON_RE = re.compile(
    r"^(?:" + "|".join(sorted(_KNOWN_STATUTES, key=len, reverse=True)) + r")?:[^:]+$")


def normalise_section(s: str) -> str:
    """Canonical form of a statutory reference.

    Returns ``"<STATUTE>:<NUMBER>"``, or ``":<NUMBER>"`` when no statute is
    attributable. Handles bare numbers, letter suffixes (304B), subsection
    forms (318(4)), and the statute prefix present or absent.

    >>> normalise_section("IPC Section 302")
    'IPC:302'
    >>> normalise_section("Section 302")
    ':302'
    >>> normalise_section("BNS 318(4)")
    'BNS:318(4)'
    """
    if s is None:
        return ""
    txt = str(s).strip()
    if not txt:
        return ""
    # IDEMPOTENCE. ranked_sections() returns strings ALREADY in canonical
    # form, and same_section() normalises its arguments again -- so this
    # function is routinely called on its own output and MUST be a no-op
    # there. The original fallback satisfied this only by accident; when the
    # fallback was corrected on 1 Sept the accident stopped holding and
    # "BNS:190" became "BNS::190", silently zeroing every retrieval metric.
    # Pinned by test_idempotent_on_its_own_output.
    if _CANON_RE.match(txt):
        return txt

    m = _SEC_RE.match(txt)
    if not m:
        # Not a Section reference at all. Constitution Articles, CPC Orders
        # and CPC Rules land here -- 28 distinct such strings appear in the
        # real logs, "CONSTITUTION Article 226" 29 times among them.
        #
        # They must still satisfy the "<STATUTE>:<REST>" contract, because
        # same_section() splits on that colon and crashed without it.
        #
        # They must ALSO keep the kind word. Article 226 of the Constitution
        # (writ jurisdiction of the High Courts) is not Section 226 of
        # anything, and the Constitution is not in this corpus at all -- so
        # collapsing the kind would manufacture matches among exactly the
        # out-of-corpus citations this project counts.
        squashed = re.sub(r"\s+", "", txt).upper()
        for st in sorted(_KNOWN_STATUTES, key=len, reverse=True):
            if squashed.startswith(st):
                return f"{st}:{squashed[len(st):]}"
        return f":{squashed}"
    statute = (m.group("statute") or "").upper()
    if statute and statute not in _KNOWN_STATUTES:
        statute = ""                      # "Section", "Sec", stray words
    num = re.sub(r"\s+", "", m.group("num") or "").upper()
    sub = re.sub(r"\s+", "", m.group("sub") or "")
    return f"{statute}:{num}{sub}"


def same_section(a: str, b: str, lenient: bool = False) -> bool:
    """Do two references point at the same provision?

    An unattributed reference matches on number alone -- statute text never
    names its own statute, so a retrieved chunk legitimately has no prefix.
    `lenient` additionally lets a sub-section match its parent (318(4) ~ 318);
    it OVER-counts (498A collapses onto 498, a different offence) so strict is
    the default and lenient must be labelled wherever reported.
    """
    na, nb = normalise_section(a), normalise_section(b)
    if not na or not nb:
        return False
    sa, va = na.split(":", 1)
    sb, vb = nb.split(":", 1)
    if sa and sb and sa != sb:
        return False
    if va == vb:
        return True
    if not lenient:
        return False
    base = lambda v: re.match(r"\d+[A-Za-z]?", v).group(0) if re.match(r"\d+", v) else v
    return base(va) == base(vb)


# ---------------------------------------------------------------- loading

def _read_jsonl(path: Path) -> list[dict]:
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def load_logs(path: str | Path | None = None) -> pd.DataFrame:
    """Server-side run records, joined to gold, DEDUPLICATED.

    Deduplicates on (query_id, intervention) keeping the last occurrence,
    because baseline and intervention are two conditions rather than repeats.
    Verified on this data: 206 of 228 same-condition repeats are
    byte-identical, n_citations never differs, and confidence differs by at
    most 0.0005 -- so "last wins" discards nothing meaningful.
    """
    srv: dict[str, dict] = {}
    for f in (ROOT / "runs").rglob("queries.jsonl"):
        for r in _read_jsonl(f):
            if r.get("req_id"):
                srv[r["req_id"]] = r

    gold: dict[str, dict] = {}
    for f in (ROOT / "runs").glob("eval_*/eval_summary.jsonl"):
        for r in _read_jsonl(f):
            if r.get("req_id"):
                gold[r["req_id"]] = r

    rows = []
    for rid, rec in srv.items():
        g = gold.get(rid, {})
        conf = rec.get("confidence") or {}
        ret = rec.get("retrieval") or {}
        ver = rec.get("verifier") or {}
        rows.append({
            "req_id": rid,
            "query_id": rec.get("query_id"),
            "intervention": g.get("intervention") or (rec.get("date") or {}).get("mode") or "baseline",
            "query_set": g.get("category"),
            "pair_id": g.get("pair_id"),
            "variant": g.get("variant"),
            "messiness": g.get("messiness"),
            "expected_sections": g.get("expected_sections") or [],
            "expected_corpus": g.get("expected_corpus"),
            "answerable": g.get("answerable_from_corpus"),
            "top_k_mean": conf.get("top_k_mean"),
            "score_gap": conf.get("score_gap"),
            "entity_coverage": conf.get("entity_coverage"),
            "entity_default_used": conf.get("entity_coverage_default_used"),
            "composite": conf.get("composite"),
            "max_score": ret.get("max_score"),
            "scores_raw": ret.get("scores_raw") or [],
            "filter_applied": ret.get("filter_applied"),
            "decision_path": (rec.get("router") or {}).get("decision_path"),
            "n_retrieved": ret.get("n_retrieved"),
            "n_after_filter": ret.get("n_after_filter"),
            "refused": conf.get("refused"),
            "cited": ver.get("cited") or [],
            "grounded": ver.get("grounded") or [],
            "ungrounded_rate": ver.get("ungrounded_rate"),
            "prompt_tokens": (rec.get("answer") or {}).get("prompt_tokens"),
            "completion_tokens": (rec.get("answer") or {}).get("completion_tokens"),
        })

    df = pd.DataFrame(rows)
    before = len(df)
    df = df.drop_duplicates(subset=["query_id", "intervention"], keep="last").reset_index(drop=True)
    df.attrs["rows_before_dedupe"] = before
    df.attrs["rows_dropped"] = before - len(df)
    return df


def load_stages(path: str | Path | None = None) -> dict[str, dict]:
    """experiments/stages.jsonl -> {req_id: {stage: [chunk, ...]}}.

    Each chunk carries the AUTHORITATIVE section_number read from the Qdrant
    payload, which the original run logs never stored.
    """
    p = Path(path) if path else ROOT / "experiments" / "stages.jsonl"
    out = {}
    for r in _read_jsonl(p):
        out[r["req_id"]] = {s: r.get(s, []) for s in STAGES}
    return out


def load_queryset(path: str | Path) -> pd.DataFrame:
    """A query set, deduplicated on query_id."""
    df = pd.DataFrame(_read_jsonl(Path(path)))
    if "query_id" in df:
        df = df.drop_duplicates(subset=["query_id"], keep="last").reset_index(drop=True)
    return df


def ranked_sections(chunks: list[dict]) -> list[str]:
    """Chunks -> canonical section ids, best-first, chunks without a section
    number dropped. Those are preamble, split continuations or demoted
    footnotes -- not sections, so they can never be the gold answer."""
    out = []
    for c in chunks:
        sn, corpus = c.get("section_number"), c.get("corpus")
        if sn:
            out.append(normalise_section(f"{corpus} {sn}"))
    return out


# ---------------------------------------------------------------- correctness

def correctness_label(row, definition: str, k: int = 10,
                      stages: dict | None = None) -> int:
    """ONE switch, not three implementations.

    retrieved@k  the gold section is among the top k retrieved (needs `stages`)
    cited        the gold section appears in the answer's citations
    grounded     every citation was supported -- the strict one, ~27 positives
    """
    if definition not in DEFINITIONS:
        raise ValueError(f"definition must be one of {DEFINITIONS}, got {definition!r}")
    gold = row.get("expected_sections") or []
    if not len(gold):
        return 0

    if definition == "grounded":
        ur = row.get("ungrounded_rate")
        return int(ur is not None and float(ur) == 0.0)

    if definition == "cited":
        cited = row.get("cited") or []
        return int(any(same_section(g, c) for g in gold for c in cited))

    if stages is None:
        raise ValueError("retrieved@k needs the `stages` mapping from load_stages()")
    st = stages.get(row.get("req_id"))
    if not st:
        return 0
    ranked = ranked_sections(st.get(row.get("_stage", "filtered_n"), []))[:k]
    return int(any(same_section(g, r) for g in gold for r in ranked))


# ---------------------------------------------------------------- retrieval

def recall_at_k(ranked: list[str], gold, k: int) -> float:
    """Fraction of gold sections appearing in the top k. Single binary gold
    here, so this is 1.0 or 0.0."""
    gold = [gold] if isinstance(gold, str) else list(gold or [])
    if not gold:
        return 0.0
    top = list(ranked)[:k]
    hits = sum(1 for g in gold if any(same_section(g, r) for r in top))
    return hits / len(gold)


def precision_at_k(ranked: list[str], gold, k: int) -> float:
    """Fraction of the top k that are gold. With one gold this equals
    recall_at_k / k exactly -- reported for completeness, not information."""
    if k <= 0:
        return 0.0
    gold = [gold] if isinstance(gold, str) else list(gold or [])
    top = list(ranked)[:k]
    hits = sum(1 for r in top if any(same_section(g, r) for g in gold))
    return hits / k


def reciprocal_rank(ranked: list[str], gold) -> float:
    """1 / rank of the first gold hit. 0.0 if gold never appears."""
    gold = [gold] if isinstance(gold, str) else list(gold or [])
    for i, r in enumerate(ranked, 1):
        if any(same_section(g, r) for g in gold):
            return 1.0 / i
    return 0.0


def ndcg_at_k(ranked: list[str], gold, k: int) -> float:
    """Binary relevance, single gold, so IDCG = 1.0 and this is a monotone
    function of reciprocal rank. Reported because the plan asks for it."""
    gold = [gold] if isinstance(gold, str) else list(gold or [])
    for i, r in enumerate(list(ranked)[:k], 1):
        if any(same_section(g, r) for g in gold):
            return 1.0 / np.log2(i + 1)
    return 0.0


# ---------------------------------------------------------------- discrimination

def auroc(scores, labels) -> float:
    """Probability a random positive outranks a random negative.

    0.5 = the score carries no information. Computed as the Mann-Whitney U
    statistic with average ranks, so ties count as 0.5 -- equivalent to the
    area under the ROC curve, and exact rather than trapezoidal.
    """
    s = np.asarray(scores, dtype=float)
    y = np.asarray(labels, dtype=int)
    pos, neg = int(y.sum()), int((1 - y).sum())
    if pos == 0 or neg == 0:
        return float("nan")
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s), dtype=float)
    ranks[order] = np.arange(1, len(s) + 1, dtype=float)
    # average ranks within tied score groups
    ss = s[order]
    i = 0
    while i < len(ss):
        j = i
        while j + 1 < len(ss) and ss[j + 1] == ss[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + j + 2) / 2.0
        i = j + 1
    return float((ranks[y == 1].sum() - pos * (pos + 1) / 2.0) / (pos * neg))


def _boot_indices(n: int, rng, cluster_ids=None):
    """One bootstrap resample. Resamples CLUSTERS when given, because two
    phrasings of one situation are not independent observations."""
    if cluster_ids is None:
        return rng.integers(0, n, n)
    ids = np.asarray(cluster_ids)
    uniq = np.unique(ids)
    picked = rng.choice(uniq, size=len(uniq), replace=True)
    idx = np.concatenate([np.flatnonzero(ids == c) for c in picked])
    return idx


def auroc_bootstrap_ci(scores, labels, n_boot: int = N_BOOT, seed: int = SEED,
                       cluster_ids=None):
    """(point, lo, hi) with a 95% percentile bootstrap interval."""
    s, y = np.asarray(scores, float), np.asarray(labels, int)
    point = auroc(s, y)
    rng = np.random.default_rng(seed)
    vals = []
    n = len(s)
    for _ in range(n_boot):
        idx = _boot_indices(n, rng, cluster_ids)
        v = auroc(s[idx], y[idx])
        if not np.isnan(v):
            vals.append(v)
    if not vals:
        return point, float("nan"), float("nan")
    return point, float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def paired_bootstrap_auroc_diff(scores_a, scores_b, labels, n_boot: int = N_BOOT,
                                seed: int = SEED, cluster_ids=None) -> dict:
    """Difference in AUROC between two scores measured on THE SAME queries.

    Paired, because comparing two independent confidence intervals by eye is
    a different and weaker test -- two intervals can overlap while the paired
    difference is clearly non-zero.

    Returns {"diff", "ci_lo", "ci_hi", "p_two_sided"} where diff = A - B.
    """
    a, b, y = np.asarray(scores_a, float), np.asarray(scores_b, float), np.asarray(labels, int)
    point = auroc(a, y) - auroc(b, y)
    rng = np.random.default_rng(seed)
    diffs = []
    n = len(y)
    for _ in range(n_boot):
        idx = _boot_indices(n, rng, cluster_ids)
        d = auroc(a[idx], y[idx]) - auroc(b[idx], y[idx])
        if not np.isnan(d):
            diffs.append(d)
    if not diffs:
        return {"diff": point, "ci_lo": float("nan"), "ci_hi": float("nan"),
                "p_two_sided": float("nan")}
    d = np.asarray(diffs)
    p = 2.0 * min((d <= 0).mean(), (d >= 0).mean())
    return {"diff": float(point), "ci_lo": float(np.percentile(d, 2.5)),
            "ci_hi": float(np.percentile(d, 97.5)), "p_two_sided": float(min(1.0, p))}


# ---------------------------------------------------------------- calibration

def reliability_bins(scores, labels, n_bins: int = 10,
                     strategy: str = "quantile") -> pd.DataFrame:
    """Predicted confidence against observed accuracy, per bin.

    QUANTILE (equal-mass) bins are the default deliberately: this project's
    confidence values cluster in roughly 0.35-0.75, so equal-width bins leave
    most bins empty and one bin holding almost everything.
    """
    s, y = np.asarray(scores, float), np.asarray(labels, int)
    if strategy == "quantile":
        edges = np.unique(np.quantile(s, np.linspace(0, 1, n_bins + 1)))
    elif strategy == "uniform":
        edges = np.linspace(s.min(), s.max(), n_bins + 1)
    else:
        raise ValueError("strategy must be 'quantile' or 'uniform'")
    idx = np.clip(np.digitize(s, edges[1:-1], right=True), 0, len(edges) - 2)
    rows = []
    for b in range(len(edges) - 1):
        m = idx == b
        if not m.any():
            continue
        rows.append({"bin": b, "lo": edges[b], "hi": edges[b + 1], "n": int(m.sum()),
                     "mean_score": float(s[m].mean()), "accuracy": float(y[m].mean()),
                     "gap": float(s[m].mean() - y[m].mean())})
    return pd.DataFrame(rows)


def ece(scores, labels, n_bins: int = 10, strategy: str = "quantile") -> float:
    """Expected Calibration Error: the average gap between stated confidence
    and observed accuracy, weighted by how many queries fall in each bin."""
    b = reliability_bins(scores, labels, n_bins, strategy)
    if b.empty:
        return float("nan")
    return float((b["n"] / b["n"].sum() * b["gap"].abs()).sum())


def brier(scores, labels) -> float:
    """Mean squared error between score and outcome. Lower is better."""
    s, y = np.asarray(scores, float), np.asarray(labels, float)
    return float(np.mean((s - y) ** 2))


def platt_scale(train_scores, train_labels, test_scores) -> np.ndarray:
    """Fit a one-feature logistic curve on train, apply to test.

    Turns an arbitrary score into something that behaves like a probability.
    Two parameters (slope, intercept) fitted by scipy; no scikit-learn needed.
    """
    from scipy.optimize import minimize
    x = np.asarray(train_scores, float)
    y = np.asarray(train_labels, float)

    def nll(p):
        z = np.clip(p[0] * x + p[1], -30, 30)
        return float(np.sum(np.log1p(np.exp(z)) - y * z))

    res = minimize(nll, x0=np.array([1.0, 0.0]), method="BFGS")
    a, b = res.x
    z = np.clip(a * np.asarray(test_scores, float) + b, -30, 30)
    return 1.0 / (1.0 + np.exp(-z))


# ---------------------------------------------------------------- selective prediction

def risk_coverage_curve(scores, labels) -> pd.DataFrame:
    """If you answer only the most-confident queries, how wrong are you?

    coverage = fraction answered; risk = error rate among those answered.
    """
    s, y = np.asarray(scores, float), np.asarray(labels, int)
    order = np.argsort(-s, kind="mergesort")
    err = (1 - y)[order]
    n = len(s)
    cum = np.cumsum(err)
    k = np.arange(1, n + 1)
    return pd.DataFrame({"coverage": k / n, "risk": cum / k, "threshold": s[order]})


def aurc(scores, labels) -> float:
    """Area under the risk-coverage curve. Lower is better."""
    c = risk_coverage_curve(scores, labels)
    return float(np.trapezoid(c["risk"].values, c["coverage"].values))


def coverage_at_risk(scores, labels, max_risk: float = 0.10) -> float:
    """The largest fraction answerable while keeping the error rate at or
    below max_risk. 0.0 if no threshold achieves it."""
    c = risk_coverage_curve(scores, labels)
    ok = c[c["risk"] <= max_risk]
    return float(ok["coverage"].max()) if len(ok) else 0.0


# ---------------------------------------------------------------- clustering

def cluster_bootstrap(df: pd.DataFrame, stat_fn, cluster_col: str,
                      n_boot: int = N_BOOT, seed: int = SEED):
    """(point, lo, hi) resampling CLUSTERS, not rows.

    The paired set is 33 situations x 3 phrasings; the dated set 30 x 4.
    Phrasings of one situation are not independent, and a naive row bootstrap
    reports an interval narrower than the data supports.
    """
    point = float(stat_fn(df))
    ids = df[cluster_col].values
    uniq = np.unique(ids)
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n_boot):
        picked = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([np.flatnonzero(ids == c) for c in picked])
        try:
            v = stat_fn(df.iloc[idx])
        except Exception:
            continue
        if v is not None and not (isinstance(v, float) and np.isnan(v)):
            vals.append(float(v))
    if not vals:
        return point, float("nan"), float("nan")
    return point, float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def wilson(k: int, n: int):
    """Proportion with a 95% Wilson interval. Wilson rather than the normal
    interval because at 33/33 the normal one gives +/-0.00, claiming certainty
    from 33 observations."""
    if n == 0:
        return 0.0, 0.0, 0.0
    z = 1.959963985
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return float(p), float(max(0.0, c - h)), float(min(1.0, c + h))
