"""exp07 -- BM25 AND HYBRID RETRIEVAL.  Wave 3, Subagent 2.

THE OBJECTION THIS EXPERIMENT EXISTS TO ANSWER
    The paper's central finding is that a query naming the Bharatiya Nyaya
    Sanhita (BNS, in force since 1 July 2024) retrieves text from the repealed
    Indian Penal Code (IPC) instead. `scripts/ablate_filter.py` measured it
    with the corpus filter switched off: IPC-named queries land in the IPC
    32/33 of the time, BNS-named queries land in the BNS 17/33.

    A reviewer will say: "You chose a DENSE retriever -- one that compares
    meaning-vectors and never looks at the literal words. An exact-word search
    would separate IPC 420 from BNS 318 trivially. Your failure is an artefact
    of your retriever, not a property of the recodification."

    That objection is answerable only by building the exact-word retriever and
    running it on the same 66 queries against the same 1,899 chunks. This
    script does that, and also fuses the two retrievers, because the reviewer's
    follow-up will be "and a hybrid would fix it".

WHAT IS COMPARED -- THREE CONFIGURATIONS, ONE SET OF CONDITIONS
    dense       Qdrant cosine search over text-embedding-3-small vectors
    bm25        rank_bm25.BM25Okapi over the SAME 1,899 chunks
    hybrid_rrf  Reciprocal Rank Fusion of the two, k=60
                (Cormack, Clarke & Buttcher, SIGIR 2009,
                 "Reciprocal Rank Fusion outperforms Condorcet and individual
                  rank learning methods")

    Each arm retrieves its top 50; the fusion runs over those two 50-lists;
    every metric is then read off the top 15 of the resulting ranking, so the
    numbers line up with the existing top-15 tables.

FIVE THINGS A READER MUST KNOW BEFORE USING THIS TABLE

  1. THE DENSE ARM HERE IS A FRESH SEARCH, NOT THE RECORDED ONE.
     The recorded runs in runs/ embedded `plan.rewritten_query` (the query with
     LLM-extracted legal issues and entities prefixed) and applied whatever
     corpus filter the Router chose. Neither is available to BM25, and neither
     is what `scripts/ablate_filter.py` did. So the dense arm is re-run here on
     the RAW query text with NO corpus filter -- identical conditions to the
     other two arms and to ablate_filter.py. Every such row says so in `notes`.
     Recorded raw_15 recall is ALSO emitted, under the metric name
     `recall_at_k_recorded_raw15`, so the size of that difference is visible
     rather than hidden.

  2. THE CORPUS FILTER IS DISABLED IN ALL THREE ARMS.
     With it on, an IPC-named query cannot return a BNS chunk and the headline
     measures a keyword lookup, not retrieval (the reason ablate_filter.py was
     written). BM25 has no filter concept at all, so "filter off" is the only
     condition under which the three arms are comparable.

  3. paired_dated_conflict IS 99 QUERIES HERE, NOT 197 ROWS.
     The 197 logged rows are 99 queries under intervention='baseline' plus 98
     of the SAME queries under intervention='both'. Reading app.py, that
     intervention acts ONLY by rewriting `plan.target_corpora` -- i.e. by
     changing the corpus FILTER. With the filter disabled the two conditions
     are the same retrieval, so there is exactly one result per query and the
     0.293 / 0.694 split has no counterpart in this table. This is why pooled
     n here is 518 unique queries and not 617 rows.

  4. RANK CONVENTION -- BOTH ARE REPORTED, exactly as in exp01.
     metrics_lib.ranked_sections() DROPS chunks carrying no section_number
     (406 of the 1,899 chunks have none: preamble, split continuations,
     demoted footnotes). Dropping them COMPRESSES rank positions and is
     OPTIMISTIC for k<15.
        recall_at_k / mrr_at_k / ndcg_at_k              compressed convention
        *_positional                                    section-less chunks
                                                        keep their slot
     Both are computed inside a fixed window of the top 15 CHUNKS, so the
     top-50 depth is used only as fusion input and cannot smuggle extra
     candidates into a k<=15 measurement.

  5. GOLD IS NOT ALWAYS ONE SECTION.
     Binary recall (was ANY gold section found) is primary, because that is
     the definition every existing number was set under. The mean
     fraction-of-gold is also reported, as recall_at_k_fraction_of_gold.

TOKENISATION -- THE CRUX
    See TOKEN_RE and expand_numeric() below. A tokeniser that strips numerals
    turns "Section 318(4)" into "section" and destroys the only signal BM25
    has in this corpus. The rule and six worked examples are in
    results/_explain_w3_s2.md.

COST
    Embedding only, no generation. 518 short queries through
    text-embedding-3-small. Actual token count is printed and written into
    the CSV as `embedding_tokens_used`.

EVERY METRIC COMES FROM experiments/metrics_lib.py. Nothing is reimplemented.
READ-ONLY on Qdrant (scroll + search). Writes only results/hybrid_comparison.csv.

Run:  ./venv/Scripts/python.exe experiments/exp07_hybrid.py
"""
from __future__ import annotations

import collections
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from experiments.metrics_lib import (  # noqa: E402
    SEED, N_BOOT, load_logs, load_stages, load_queryset, ranked_sections,
    recall_at_k, reciprocal_rank, ndcg_at_k, wilson, cluster_bootstrap,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "hybrid_comparison.csv"

KS = [1, 3, 5, 10, 15]
DEPTH = 50          # per-arm retrieval depth, fusion input
WINDOW = 15         # evaluation window, in CHUNKS, for every arm
RRF_K = 60          # Cormack, Clarke & Buttcher, SIGIR 2009. NOT invented here.

STAGES3 = ["dense", "bm25", "hybrid_rrf"]
CORPORA = ["IPC", "BNS", "CRPC", "CPA"]

QUERYSETS = {
    "generated_retrieval":   ROOT / "eval" / "generated_queryset.jsonl",
    "paired_recodification": ROOT / "eval" / "paired_queryset.jsonl",
    "paired_dated_conflict": ROOT / "eval" / "paired_dated_queryset.jsonl",
    "layman_situation":      ROOT / "eval" / "layman_queryset.jsonl",
}

# Embedding cache lives OUTSIDE the repo. It is a pure speed optimisation:
# delete it and the script re-embeds and produces identical numbers.
CACHE = Path(tempfile.gettempdir()) / "exp07_query_embeddings.json"


# ============================================================== tokenisation
#
# THE RULE, in one regex and one expansion.
#
#   1. Lowercase. Normalise the corpus's stray unicode dashes/quotes to ASCII
#      so "peace—Any" does not fuse two words.
#   2. Scan for tokens matching, in order of preference:
#        a NUMERIC token   digits, then 0-2 letters, then any number of
#                          parenthesised subsection groups
#                          318 | 304b | 41a | 318(4) | 498a(1)(b)
#        an ALPHA token    a run of letters
#                          section | punishment | sanhita
#      Everything else (punctuation, whitespace, stray symbols) is a separator.
#   3. EXPAND each numeric token to its statutory ancestors:
#        318(4)     -> 318(4), 318
#        498a(1)(b) -> 498a(1)(b), 498a(1), 498a, 498
#        304b       -> 304b, 304
#        318        -> 318
#      The subsection number ALONE ("4") is deliberately NOT emitted.
#
# WHY EXPAND. Section headings in the corpus are written bare -- "Section 318."
# -- while queries and cross-references write "Section 318(4)". Without
# expansion those two never share a token and BM25 scores the correct chunk at
# zero on the only term that identifies it. Expansion is applied identically to
# documents and to queries, so the match is symmetric.
#
# WHY NOT EMIT THE BARE SUBSECTION DIGIT. "4" occurs in a large fraction of the
# 1,899 chunks, so its inverse document frequency is near zero and it can only
# add noise to the length normalisation. Dropping it costs no recall (the
# parent number "318" already localises the section) and keeps the query terms
# interpretable.

TOKEN_RE = re.compile(r"\d+[a-z]{0,2}(?:\([0-9a-z]+\))*|[a-z]+")
_NUMERIC_RE = re.compile(r"^(\d+)([a-z]{0,2})((?:\([0-9a-z]+\))*)$")
_UNICODE_FIX = str.maketrans({
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-",
    "―": "-", "‘": "'", "’": "'", "“": '"', "”": '"',
    " ": " ", "�": " ",
})


def expand_numeric(tok: str) -> list[str]:
    """A numeric token plus its statutory ancestors. Non-numeric -> itself."""
    m = _NUMERIC_RE.match(tok)
    if not m:
        return [tok]
    digits, letters, subs = m.group(1), m.group(2), m.group(3)
    out = [tok]
    groups = re.findall(r"\([0-9a-z]+\)", subs)
    for i in range(len(groups) - 1, -1, -1):
        cand = digits + letters + "".join(groups[:i])
        if cand not in out:
            out.append(cand)
    if letters and digits not in out:
        out.append(digits)
    return out


def tokenise(text: str) -> list[str]:
    """The one tokeniser. Applied to BOTH documents and queries."""
    if not text:
        return []
    low = str(text).translate(_UNICODE_FIX).lower()
    out: list[str] = []
    for tok in TOKEN_RE.findall(low):
        out.extend(expand_numeric(tok))
    return out


# ============================================================== corpus

def load_corpus() -> list[dict]:
    """READ-ONLY scroll of the whole Qdrant collection, in a fixed order.

    Sorted on chunk_id so the BM25 document ids are stable across runs and the
    index is reproducible without storing it.
    """
    from clients.qdrant_client import qdrant, COLLECTION
    client = qdrant()
    docs, offset = [], None
    while True:
        pts, offset = client.scroll(collection_name=COLLECTION, limit=500,
                                    offset=offset, with_payload=True,
                                    with_vectors=False)
        for p in pts:
            pl = dict(p.payload or {})
            pl["_point_id"] = str(p.id)
            docs.append(pl)
        if offset is None:
            break
    docs.sort(key=lambda d: (str(d.get("chunk_id") or ""), d["_point_id"]))
    return docs


def corpus_shares(docs: list[dict]) -> dict[str, float]:
    c = collections.Counter(d.get("corpus") for d in docs)
    total = sum(c.values()) or 1
    return {k: v / total for k, v in c.items() if k}


# ============================================================== retrieval arms

def build_bm25(docs: list[dict]):
    from rank_bm25 import BM25Okapi
    tokenised = [tokenise(d.get("text") or "") for d in docs]
    return BM25Okapi(tokenised), tokenised


def bm25_topn(bm25, query: str, n: int) -> list[int]:
    """Document indices, best first. Ties broken by index for determinism."""
    scores = np.asarray(bm25.get_scores(tokenise(query)), dtype=float)
    order = np.lexsort((np.arange(len(scores)), -scores))
    return [int(i) for i in order[:n]]


def embed_queries(texts: list[str]) -> tuple[list[list[float]], int]:
    """Embed, with an out-of-repo cache. Returns (vectors, tokens_charged)."""
    from clients.openai_client import embed_texts
    cache: dict[str, list[float]] = {}
    if CACHE.exists():
        try:
            cache = json.loads(CACHE.read_text(encoding="utf-8"))
        except Exception:
            cache = {}
    keys = [hashlib.sha256(t.encode("utf-8")).hexdigest() for t in texts]
    missing = [t for t, k in zip(texts, keys) if k not in cache]
    missing = list(dict.fromkeys(missing))
    tokens = 0
    if missing:
        print("  embedding %d uncached queries (%d already cached)"
              % (len(missing), len(texts) - len(missing)))
        for i in range(0, len(missing), 128):
            batch = missing[i:i + 128]
            vecs, meta = embed_texts(batch)
            tokens += int(getattr(meta, "prompt_tokens", 0) or 0)
            for t, v in zip(batch, vecs):
                cache[hashlib.sha256(t.encode("utf-8")).hexdigest()] = v
        try:
            CACHE.write_text(json.dumps(cache), encoding="utf-8")
        except Exception:
            pass
    else:
        print("  all %d query embeddings served from cache at %s"
              % (len(texts), CACHE))
    return [cache[k] for k in keys], tokens


def dense_topn(client, collection, vec, n: int, id_to_ix: dict) -> list[int]:
    """Filter DISABLED, deliberately. See note 2 in the module docstring."""
    hits = client.search(collection_name=collection, query_vector=vec,
                         limit=n, with_payload=False)
    return [id_to_ix[str(h.id)] for h in hits if str(h.id) in id_to_ix]


# ============================================================== fusion

def rrf_fuse(rankings: list[list[int]], k: int = RRF_K) -> list[int]:
    """Reciprocal Rank Fusion.

        score(d) = SUM over input lists of  1 / (k + rank_i(d)),   ranks 1-based

    A document absent from a list contributes nothing from that list -- it is
    not given a notional last place, because the lists are truncated at DEPTH
    and "absent" therefore means "not in the top 50", not "ranked last".

    k = 60 is the constant from Cormack, Clarke & Buttcher, SIGIR 2009. It
    damps the influence of the very top ranks so that one list cannot dictate
    the fusion on its own.

    Ties are broken by best rank achieved in any list, then by document id, so
    the output is a total order and is reproducible.
    """
    score: dict[int, float] = collections.defaultdict(float)
    best: dict[int, int] = {}
    for lst in rankings:
        for rank, doc in enumerate(lst, 1):
            score[doc] += 1.0 / (k + rank)
            if doc not in best or rank < best[doc]:
                best[doc] = rank
    return sorted(score, key=lambda d: (-score[d], best[d], d))


# ============================================================== metric helpers

def positional_sections(chunks: list[dict]) -> list[str]:
    """exp01's convention: every chunk keeps its slot; section-less -> "" ,
    which same_section() can never match."""
    return [ranked_sections([c])[0] if c.get("section_number") else ""
            for c in chunks]


def per_query_metrics(chunks: list[dict], gold: list[str]) -> dict:
    """Every metric for one query's ranked chunk list, inside the top-WINDOW."""
    win = chunks[:WINDOW]
    compressed = ranked_sections(win)
    positional = positional_sections(win)
    rec = {}
    for k in KS:
        rec["recall_at_k@%d" % k] = int(recall_at_k(compressed, gold, k) > 0.0)
        rec["recall_at_k_positional@%d" % k] = int(
            recall_at_k(positional, gold, k) > 0.0)
        rec["recall_at_k_fraction_of_gold@%d" % k] = recall_at_k(compressed, gold, k)
        rec["mrr_at_k@%d" % k] = reciprocal_rank(compressed[:k], gold)
        rec["mrr_at_k_positional@%d" % k] = reciprocal_rank(positional[:k], gold)
        rec["ndcg_at_k@%d" % k] = ndcg_at_k(compressed, gold, k)
        rec["ndcg_at_k_positional@%d" % k] = ndcg_at_k(positional, gold, k)
    return rec


METRICS = {
    "recall_at_k": ("share of QUERIES with >=1 gold section in the top k", True,
                    "compressed"),
    "recall_at_k_positional": ("share of QUERIES with >=1 gold section in the top k",
                               True, "positional"),
    "recall_at_k_fraction_of_gold": ("mean FRACTION of a query's gold sections "
                                     "found in the top k", False, "compressed"),
    "mrr_at_k": ("mean 1/(rank of first gold hit) within the top k; 0 if absent",
                 False, "compressed"),
    "mrr_at_k_positional": ("mean 1/(rank of first gold hit) within the top k; "
                            "0 if absent", False, "positional"),
    "ndcg_at_k": ("mean 1/log2(rank+1) of the first gold hit within the top k",
                  False, "compressed"),
    "ndcg_at_k_positional": ("mean 1/log2(rank+1) of the first gold hit within "
                             "the top k", False, "positional"),
}

_CONV = {
    "compressed": ("RANK CONVENTION: metrics_lib.ranked_sections() -- rank among "
                   "chunks that carry a section_number; section-less chunks "
                   "dropped, which compresses ranks and is OPTIMISTIC for k<15."),
    "positional": ("RANK CONVENTION: positional -- rank among chunks AS "
                   "RETRIEVED, section-less chunks keeping their slot as an "
                   "unmatchable empty string."),
}

STAGE_NOTES = {
    "dense": ("Qdrant cosine over text-embedding-3-small, top-%d, corpus filter "
              "DISABLED, RAW query text. PROVENANCE: FRESH SEARCH run by this "
              "script -- NOT the recorded runs/, which embedded the Router's "
              "rewritten_query and applied a corpus filter." % DEPTH),
    "bm25": ("rank_bm25.BM25Okapi (k1=1.5, b=0.75, epsilon=0.25 -- library "
             "defaults) over the same 1899 chunks, top-%d. PROVENANCE: FRESH, "
             "computed by this script." % DEPTH),
    "hybrid_rrf": ("Reciprocal Rank Fusion of the dense and bm25 top-%d lists, "
                   "k=%d (Cormack, Clarke & Buttcher, SIGIR 2009). PROVENANCE: "
                   "FRESH, computed by this script." % (DEPTH, RRF_K)),
}

_WINDOW_NOTE = ("Metrics are read off the top %d CHUNKS of each arm; the top-%d "
                "depth is fusion input only and cannot add candidates at k<=%d."
                % (WINDOW, DEPTH, WINDOW))


def _fmt(v):
    if v is None or v == "":
        return ""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    return "" if np.isnan(f) else round(f, 6)


def row(metric, query_set, definition, stage, k, value, n,
        ci_lo="", ci_hi="", cci_lo="", cci_hi="", notes=""):
    return {"metric": metric, "query_set": query_set, "definition": definition,
            "stage": stage, "k": k, "value": _fmt(value), "n": n,
            "ci_lo": _fmt(ci_lo), "ci_hi": _fmt(ci_hi),
            "cluster_ci_lo": _fmt(cci_lo), "cluster_ci_hi": _fmt(cci_hi),
            "notes": notes}


def harvest_bootstrap(d: pd.DataFrame, cols: list[str], cluster_col: str):
    """95% cluster-bootstrap intervals for many column means from ONE set of
    10,000 draws. Same device as exp01, same seed, same library function."""
    harvest: list[np.ndarray] = []
    vals = d[cols].to_numpy(dtype=float)
    frame = pd.DataFrame({"_i": np.arange(len(d)),
                          cluster_col: d[cluster_col].values})

    def stat_fn(x: pd.DataFrame) -> float:
        m = vals[x["_i"].values].mean(axis=0)
        harvest.append(m)
        return float(m[0])

    point0, lo0, hi0 = cluster_bootstrap(frame, stat_fn, cluster_col, N_BOOT, SEED)
    assert len(harvest) == N_BOOT + 1, (
        "harvest length %d != N_BOOT+1" % len(harvest))
    boot = np.vstack(harvest[1:])
    lo = np.percentile(boot, 2.5, axis=0)
    hi = np.percentile(boot, 97.5, axis=0)
    point = vals.mean(axis=0)
    assert (abs(point[0] - point0) < 1e-12 and abs(lo[0] - lo0) < 1e-12
            and abs(hi[0] - hi0) < 1e-12), "harvested interval != cluster_bootstrap's"
    return {c: (float(point[i]), float(lo[i]), float(hi[i]))
            for i, c in enumerate(cols)}


# ============================================================== main

def run_all_arms(queries: list[dict], docs: list[dict]):
    """{query_id: {stage: [chunk_payload, ...]}} plus the embedding token count."""
    from clients.qdrant_client import qdrant, COLLECTION
    client = qdrant()
    id_to_ix = {d["_point_id"]: i for i, d in enumerate(docs)}

    print("  building BM25 index over %d chunks ..." % len(docs))
    bm25, tokenised = build_bm25(docs)
    assert len(tokenised) == len(docs) == 1899, (
        "BM25 index holds %d documents, expected 1899" % len(tokenised))

    vecs, tokens = embed_queries([q["text"] for q in queries])

    out = {}
    for i, (q, vec) in enumerate(zip(queries, vecs)):
        d_ix = dense_topn(client, COLLECTION, vec, DEPTH, id_to_ix)
        b_ix = bm25_topn(bm25, q["text"], DEPTH)
        h_ix = rrf_fuse([d_ix, b_ix], RRF_K)
        out[q["query_id"]] = {
            "dense": [docs[j] for j in d_ix[:WINDOW]],
            "bm25": [docs[j] for j in b_ix[:WINDOW]],
            "hybrid_rrf": [docs[j] for j in h_ix[:WINDOW]],
        }
        if (i + 1) % 100 == 0:
            print("    %d/%d queries retrieved" % (i + 1, len(queries)))
    return out, tokens, bm25, tokenised


def main() -> None:
    print("exp07 -- BM25 and hybrid retrieval\n")

    docs = load_corpus()
    print("  corpus: %d chunks scrolled from Qdrant (READ-ONLY)" % len(docs))
    shares = corpus_shares(docs)
    print("  chance baseline: " +
          "  ".join("%s %.1f%%" % (c, 100 * shares.get(c, 0)) for c in CORPORA))

    queries: list[dict] = []
    for qs, path in QUERYSETS.items():
        df = load_queryset(path)
        for r in df.to_dict("records"):
            queries.append({
                "query_id": r["query_id"], "text": r["text"], "query_set": qs,
                "pair_id": r.get("pair_id"), "variant": r.get("variant"),
                "gold": list(r.get("expected_sections") or []),
                "expected_corpus": r.get("expected_corpus"),
            })
    print("  queries: %d unique across %d sets" % (len(queries), len(QUERYSETS)))

    results, embed_tokens, bm25, tokenised = run_all_arms(queries, docs)
    print("  embedding tokens charged this run: %d" % embed_tokens)

    # ---------------------------------------------------------------- frame
    rows = []
    for q in queries:
        if not q["gold"]:
            continue
        for stage in STAGES3:
            rec = {"query_id": q["query_id"], "query_set": q["query_set"],
                   "pair_id": q["pair_id"], "variant": q["variant"],
                   "stage": stage, "n_gold": len(q["gold"])}
            rec.update(per_query_metrics(results[q["query_id"]][stage], q["gold"]))
            rows.append(rec)
    df = pd.DataFrame(rows)
    df["_cluster"] = df["query_set"].astype(str) + "|" + df["pair_id"].astype(str)

    out: list[dict] = []

    # ================================================== (a) THE HEADLINE
    #
    # 66 numbered paired queries, corpus filter disabled -- the exact
    # conditions of scripts/ablate_filter.py, extended to three arms.
    numbered = [q for q in queries
                if q["query_set"] == "paired_recodification"
                and q["variant"] in ("ipc_numbered", "bns_numbered")]
    print("\n  HEADLINE set: %d numbered paired queries, filter DISABLED"
          % len(numbered))

    head_rows = []
    for q in numbered:
        want = q["expected_corpus"]
        for stage in STAGES3:
            chunks = results[q["query_id"]][stage][:WINDOW]
            seen = collections.Counter(c.get("corpus") for c in chunks)
            dom = seen.most_common(1)[0][0] if seen else None
            top1 = chunks[0].get("corpus") if chunks else None
            head_rows.append({"query_id": q["query_id"], "pair_id": q["pair_id"],
                              "variant": q["variant"], "want": want,
                              "stage": stage, "dominant": dom, "top1": top1,
                              "dom_correct": int(dom == want),
                              "top1_correct": int(top1 == want)})
    hd = pd.DataFrame(head_rows)

    HEAD_NOTE = (
        "HEADLINE. Reproduces the conditions of scripts/ablate_filter.py "
        "(66 numbered paired queries, corpus filter DISABLED, raw query text, "
        "top 15) for three retrieval configurations. ci_lo/ci_hi = Wilson. "
        "cluster_ci = cluster bootstrap on pair_id, %d resamples, seed %d."
        % (N_BOOT, SEED))

    for named, sub in (("ipc_named", hd[hd["variant"] == "ipc_numbered"]),
                       ("bns_named", hd[hd["variant"] == "bns_numbered"]),
                       ("both", hd)):
        qsname = "paired_numbered_%s" % named
        degen = (" Within this subgroup each pair_id appears exactly once, so "
                 "the cluster bootstrap degenerates to a naive row bootstrap "
                 "and the two intervals should be read as one."
                 if named != "both" else
                 " Each pair_id appears twice here (one IPC-named, one "
                 "BNS-named query), so the cluster bootstrap is meaningful.")
        for stage in STAGES3:
            s = sub[sub["stage"] == stage]
            for col, metric, defn, k in (
                    ("dom_correct", "corpus_dominant_accuracy",
                     "dominant_corpus_among_top15", 15),
                    ("top1_correct", "corpus_top1_accuracy",
                     "corpus_of_top1_chunk", 1)):
                kk, n = int(s[col].sum()), len(s)
                p, lo, hi = wilson(kk, n)
                _, clo, chi = cluster_bootstrap(
                    s[["pair_id", col]],
                    lambda x, _c=col: float(x[_c].mean()),
                    "pair_id", N_BOOT, SEED)
                out.append(row(metric, qsname, defn, stage, k, p, n,
                               lo, hi, clo, chi,
                               "%d/%d. %s %s%s" % (kk, n, HEAD_NOTE,
                                                   STAGE_NOTES[stage], degen)))
        # which corpus actually won, per arm -- the off-diagonal
        for stage in STAGES3:
            s = sub[sub["stage"] == stage]
            for c in CORPORA:
                out.append(row("dominant_corpus_count_%s" % c, qsname,
                               "dominant_corpus_among_top15", stage, 15,
                               int((s["dominant"] == c).sum()), len(s),
                               "", "", "", "",
                               "COUNT, not a rate: how many of these queries "
                               "had %s supply most of the top 15. The "
                               "off-diagonal of the ablate_filter matrix. %s"
                               % (c, STAGE_NOTES[stage])))
                out.append(row("top1_corpus_count_%s" % c, qsname,
                               "corpus_of_top1_chunk", stage, 1,
                               int((s["top1"] == c).sum()), len(s),
                               "", "", "", "",
                               "COUNT, not a rate: how many of these queries "
                               "had %s supply the single top-scoring chunk. %s"
                               % (c, STAGE_NOTES[stage])))

    for c in CORPORA:
        out.append(row("chance_baseline_corpus_share", "INDEX", "", "", "",
                       shares.get(c, 0.0), len(docs), "", "", "", "",
                       "%s's share of the %d indexed chunks. A corpus that "
                       "occupies more of the index wins more often for free; "
                       "this is the number each accuracy above must beat. "
                       "Applies to all three arms -- BM25 and dense draw from "
                       "the same index." % (c, len(docs))))

    # ================================================== (b) RETRIEVAL METRICS
    metric_cols = ["%s@%d" % (m, k) for m in METRICS for k in KS]
    groups = [(qs, df[df["query_set"] == qs], "pair_id") for qs in QUERYSETS]
    groups.append(("ALL", df, "_cluster"))

    for qs, dq, ccol in groups:
        if not len(dq):
            continue
        for stage in STAGES3:
            d = dq[dq["stage"] == stage]
            if not len(d):
                continue
            boot = harvest_bootstrap(d, metric_cols, ccol)
            n = len(d)
            for metric, (mnote, is_prop, conv) in METRICS.items():
                for k in KS:
                    point, blo, bhi = boot["%s@%d" % (metric, k)]
                    wlo = whi = ""
                    if is_prop:
                        kk = int(round(point * n))
                        _, wlo, whi = wilson(kk, n)
                        cin = ("ci_lo/ci_hi = Wilson (k=%d of n=%d queries)"
                               % (kk, n))
                    else:
                        cin = ("ci_lo/ci_hi EMPTY -- a mean, not a proportion "
                               "of queries, so Wilson does not apply")
                    out.append(row(
                        metric, qs, "retrieved@k", stage, k, point, n,
                        wlo, whi, blo, bhi,
                        "%s. %s %s %s. cluster_ci = cluster bootstrap on %s, "
                        "%d resamples, seed %d. %s"
                        % (mnote, _CONV[conv], _WINDOW_NOTE,
                           STAGE_NOTES[stage], ccol, N_BOOT, SEED,
                           "POOLED n=%d UNIQUE QUERIES, not the 617 logged "
                           "rows -- see notes 1 and 3 in exp07_hybrid.py."
                           % n if qs == "ALL" else "")))

    # ------------------------------------------------ paired set, split by variant
    #
    # The headline measures which CORPUS the top 15 came from. This measures
    # whether the gold SECTION was in it. They are different questions and on
    # the BNS-named queries they give very different answers, so both are
    # reported rather than one standing in for the other.
    for variant in ("ipc_numbered", "bns_numbered", "neutral_topic"):
        for stage in STAGES3:
            d = df[(df["query_set"] == "paired_recodification")
                   & (df["variant"] == variant) & (df["stage"] == stage)]
            if not len(d):
                continue
            kk, n = int(d["recall_at_k@15"].sum()), len(d)
            p, lo, hi = wilson(kk, n)
            out.append(row("recall_at_k", "paired_numbered_%s"
                           % variant.replace("_numbered", "_named"),
                           "retrieved@k", stage, 15, p, n, lo, hi, "", "",
                           "%d/%d. SPLIT OF paired_recodification BY VARIANT, "
                           "not an extra query set. Gold-SECTION recall, to be "
                           "read next to the corpus-level headline for the "
                           "same queries. Wilson interval; each pair_id occurs "
                           "once inside a variant so no cluster interval is "
                           "reported. %s %s"
                           % (kk, n, _CONV["compressed"], STAGE_NOTES[stage])))

    # ------------------------------------------------ the gold-reachability ceiling
    #
    # FOUND WHILE RUNNING THIS EXPERIMENT, and it bounds every Recall row above.
    # 22 of the 33 bns_numbered gold labels are SUBSECTION references --
    # "BNS 103(1)", "BNS 318(4)" -- while the index records only the bare
    # section number, "103", "318". metrics_lib.same_section() is STRICT by
    # default and its own docstring says lenient matching over-counts, so
    # "BNS:318(4)" and "BNS:318" are correctly held to be different provisions
    # and those queries CANNOT be scored correct by any retriever. The ceiling
    # is a property of the gold labels, not of retrieval, and it is identical
    # for all three arms. It is reported rather than repaired: editing the gold
    # would be patching data instead of fixing code.
    from experiments.metrics_lib import same_section as _same
    indexed = {normalise for normalise in
               {ranked_sections([d])[0] for d in docs if d.get("section_number")}}
    reach_all = reach_n = 0
    for qs in QUERYSETS:
        qq = [q for q in queries if q["query_set"] == qs and q["gold"]]
        ok = sum(1 for q in qq
                 if any(any(_same(g, a) for a in indexed) for g in q["gold"]))
        reach_all += ok
        reach_n += len(qq)
        p, lo, hi = wilson(ok, len(qq))
        out.append(row("gold_reachable_ceiling", qs, "retrieved@k", "", 15,
                       p, len(qq), lo, hi, "", "",
                       "%d/%d. HARD UPPER BOUND on every recall_at_k row for "
                       "this set, IDENTICAL for all three arms. The share of "
                       "queries whose gold section exists in the index at all "
                       "under metrics_lib.same_section (strict). The shortfall "
                       "is gold labels carrying a subsection the index does "
                       "not record -- 'BNS 318(4)' against an indexed "
                       "section_number of '318'. Reported, not repaired: "
                       "same_section's own docstring says lenient matching "
                       "over-counts (498A would collapse onto 498), and "
                       "editing the gold would be patching data instead of "
                       "fixing code." % (ok, len(qq))))
    for variant in ("ipc_numbered", "bns_numbered", "neutral_topic"):
        qq = [q for q in queries if q["query_set"] == "paired_recodification"
              and q["variant"] == variant and q["gold"]]
        ok = sum(1 for q in qq
                 if any(any(_same(g, a) for a in indexed) for g in q["gold"]))
        p, lo, hi = wilson(ok, len(qq))
        out.append(row("gold_reachable_ceiling", "paired_numbered_%s"
                       % variant.replace("_numbered", "_named"),
                       "retrieved@k", "", 15, p, len(qq), lo, hi, "", "",
                       "%d/%d. SPLIT OF paired_recodification BY VARIANT. This "
                       "is where the ceiling bites hardest: %d of the %d gold "
                       "labels for this variant name a subsection the index "
                       "does not record, so no retriever of any kind can score "
                       "them correct. Identical for all three arms."
                       % (ok, len(qq), len(qq) - ok, len(qq))))
    p, lo, hi = wilson(reach_all, reach_n)
    out.append(row("gold_reachable_ceiling", "ALL", "retrieved@k", "", 15,
                   p, reach_n, lo, hi, "", "",
                   "%d/%d pooled. See the per-set rows. Every recall_at_k "
                   "value in this file must be read against this ceiling, not "
                   "against 1.0." % (reach_all, reach_n)))

    # ------------------------------------------------ recorded dense, for contrast
    try:
        logs = load_logs()
        stages = load_stages()
        for qs in QUERYSETS:
            sub = logs[(logs["query_set"] == qs)]
            hits = tot = 0
            for r in sub.to_dict("records"):
                gold = r.get("expected_sections") or []
                st = stages.get(r["req_id"])
                if not len(gold) or st is None:
                    continue
                tot += 1
                hits += int(recall_at_k(ranked_sections(st.get("raw_15", [])),
                                        gold, 15) > 0.0)
            if tot:
                p, lo, hi = wilson(hits, tot)
                out.append(row("recall_at_k_recorded_raw15", qs, "retrieved@k",
                               "dense", 15, p, tot, lo, hi, "", "",
                               "%d/%d. NOT a row of the comparison above. This "
                               "is the RECORDED dense result from runs/ at "
                               "stage raw_15 -- rewritten_query, router corpus "
                               "filter ON, top 15 only, and with "
                               "paired_dated_conflict counted as 197 logged "
                               "rows rather than 99 unique queries. Emitted so "
                               "the gap between recorded and fresh conditions "
                               "is visible instead of hidden. Wilson interval."
                               % (hits, tot)))
    except Exception as exc:                       # pragma: no cover
        out.append(row("recall_at_k_recorded_raw15", "ALL", "", "dense", 15,
                       "", "", "", "", "", "",
                       "NOT MEASURED: reading the recorded runs failed (%s)"
                       % type(exc).__name__))

    # ------------------------------------------------ provenance
    out.append(row("embedding_tokens_used", "ALL", "", "dense", "",
                   embed_tokens, len(queries), "", "", "", "",
                   "prompt_tokens reported by the embeddings endpoint for the "
                   "queries embedded ON THIS RUN. 0 means every query was "
                   "served from the local cache at %s; delete it to force a "
                   "re-embed. Model text-embedding-3-small at $0.02 per "
                   "million tokens." % CACHE))
    out.append(row("bm25_index_documents", "INDEX", "", "bm25", "",
                   len(tokenised), len(docs), "", "", "", "",
                   "documents in the BM25 index; must equal the 1899 Qdrant "
                   "points"))
    out.append(row("bm25_vocabulary_size", "INDEX", "", "bm25", "",
                   len({t for d in tokenised for t in d}), len(docs),
                   "", "", "", "",
                   "distinct tokens after lowercasing, numeric-token "
                   "preservation and ancestor expansion"))
    out.append(row("bm25_mean_tokens_per_chunk", "INDEX", "", "bm25", "",
                   float(np.mean([len(d) for d in tokenised])), len(docs),
                   "", "", "", "",
                   "mean document length in tokens -- the quantity BM25's b "
                   "parameter normalises against"))
    out.append(row("chunks_without_section_number", "INDEX", "", "", "",
                   sum(1 for d in docs if not d.get("section_number")), len(docs),
                   "", "", "", "",
                   "chunks that ranked_sections() drops. This is why the "
                   "compressed and positional rank conventions differ below "
                   "k=15."))
    out.append(row("rrf_k_constant", "INDEX", "", "hybrid_rrf", "", RRF_K, "",
                   "", "", "", "",
                   "score(d) = SUM over lists of 1/(k + rank_i(d)). k=60 from "
                   "Cormack, Clarke & Buttcher, SIGIR 2009. Not tuned here; "
                   "tuning it on this data would be fitting the constant to "
                   "the result."))
    n_multi = int((df[df["stage"] == "dense"]["n_gold"] > 1).sum())
    out.append(row("gold_multi_section", "ALL", "", "", "", n_multi,
                   len(df[df["stage"] == "dense"]), "", "", "", "",
                   "queries carrying 2 or 3 gold sections, where binary "
                   "recall_at_k and recall_at_k_fraction_of_gold differ"))
    out.append(row("rows_analysed", "ALL", "", "", "",
                   len(df[df["stage"] == "dense"]), len(queries), "", "", "", "",
                   "unique gold-labelled queries. The 58-query legacy "
                   "eval/queryset.jsonl is excluded, matching exp01's four "
                   "reported sets. paired_dated_conflict contributes 99 unique "
                   "queries, not 197 logged rows: with the corpus filter "
                   "disabled the date/mapper intervention is a no-op, because "
                   "app.py applies it only by rewriting plan.target_corpora."))

    res = pd.DataFrame(out, columns=["metric", "query_set", "definition",
                                     "stage", "k", "value", "n", "ci_lo",
                                     "ci_hi", "cluster_ci_lo",
                                     "cluster_ci_hi", "notes"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(OUT, index=False)

    # ---------------------------------------------------------------- console
    print("\n  HEADLINE -- does naming the Act get you that Act's text?")
    print("  corpus filter DISABLED. chance: " +
          " ".join("%s %.1f%%" % (c, 100 * shares.get(c, 0)) for c in CORPORA))
    for label, defn, col in (("DOMINANT corpus among the top 15",
                              "dominant", "dom_correct"),
                             ("corpus of the single TOP-1 chunk",
                              "top1", "top1_correct")):
        print("\n  %s" % label)
        print("  %-12s %-12s %8s %8s %8s %8s   %-24s %s"
              % ("QUERY NAMES", "ARM", "IPC", "BNS", "CRPC", "CPA",
                 "CORRECT [95% Wilson]", "CHANCE"))
        print("  " + "-" * 104)
        for variant, want in (("ipc_numbered", "IPC"), ("bns_numbered", "BNS")):
            for stage in STAGES3:
                s = hd[(hd["variant"] == variant) & (hd["stage"] == stage)]
                cnt = collections.Counter(s[defn])
                kk, n = int(s[col].sum()), len(s)
                p, lo, hi = wilson(kk, n)
                print("  %-12s %-12s %8d %8d %8d %8d   %5.1f%% [%4.1f,%5.1f]"
                      "        %5.1f%%"
                      % (want, stage, cnt.get("IPC", 0), cnt.get("BNS", 0),
                         cnt.get("CRPC", 0), cnt.get("CPA", 0),
                         100 * p, 100 * lo, 100 * hi, 100 * shares.get(want, 0)))

    print("\n  Recall@15 (binary, compressed convention) [95%% Wilson]")
    print("  %-24s %5s %-24s %-24s %-24s"
          % ("query_set", "n", "dense", "bm25", "hybrid_rrf"))
    print("  " + "-" * 106)
    for qs, dq, _c in groups:
        cells = []
        for stage in STAGES3:
            d = dq[dq["stage"] == stage]
            p, lo, hi = wilson(int(d["recall_at_k@15"].sum()), len(d))
            cells.append("%.3f [%.3f, %.3f]" % (p, lo, hi))
        print("  %-24s %5d %-24s %-24s %-24s"
              % (qs, len(dq[dq["stage"] == "dense"]), *cells))

    print("\n  Recall@k, compressed convention")
    print("  %-24s %-11s %7s %7s %7s %7s %7s"
          % ("query_set", "arm", "k=1", "k=3", "k=5", "k=10", "k=15"))
    for qs, dq, _c in groups:
        for stage in STAGES3:
            d = dq[dq["stage"] == stage]
            print("  %-24s %-11s %7.3f %7.3f %7.3f %7.3f %7.3f"
                  % (qs, stage, *[d["recall_at_k@%d" % k].mean() for k in KS]))

    print("\n  MRR@15 / nDCG@15 (compressed convention)")
    print("  %-24s %-11s %9s %9s" % ("query_set", "arm", "MRR@15", "nDCG@15"))
    for qs, dq, _c in groups:
        for stage in STAGES3:
            d = dq[dq["stage"] == stage]
            print("  %-24s %-11s %9.4f %9.4f"
                  % (qs, stage, d["mrr_at_k@15"].mean(), d["ndcg_at_k@15"].mean()))

    print("\n  embedding tokens charged this run: %d "
          "($%.6f at $0.02/M ~= Rs %.4f at 88/USD)"
          % (embed_tokens, embed_tokens * 0.02e-6, embed_tokens * 0.02e-6 * 88))
    print("  wrote %s  (%d rows)" % (OUT, len(res)))


if __name__ == "__main__":
    main()
