"""Statutory self-naming: does a statute name itself in its own text?

THE GAP THIS CLOSES. Wave 3 found that exact-word (BM25) search INVERTS the
cross-statute failure -- it finds BNS-named queries almost perfectly and
IPC-named queries not at all -- and attributed this to asymmetric statutory
self-naming: the 2023 BNS names itself in its operative text, the 1860 IPC does
not, so "Indian Penal Code" occurs mainly as cross-references inside the
procedure code. That mechanism existed only as PROSE in results/EXPLAIN.md and
in no machine-readable results file, so the paper could not cite it.

This is the one piece of NEW analysis authorised after Wave 4.

DEFINITIONS, because the whole result rests on them.

  document frequency (df)  in how many of the 1,899 indexed chunks does this
                           word appear at least once?

  inverse document frequency (idf)  how INFORMATIVE that word is. A word in 30
                           chunks is a strong clue; a word in 1,500 chunks says
                           almost nothing. Okapi BM25 form, which is what
                           rank_bm25 uses and therefore what Wave 3 reported:

                               idf = ln( (N - df + 0.5) / (df + 0.5) ),  N=1899

                           Sanity check against the existing prose figure:
                           "sanhita" in 30 chunks gives ln(1869.5/30.5) = 4.1156
                           -> 4.12, matching Wave 3 exactly. Plain ln(N/df)
                           would give 4.15 and silently contradict it.

  concentration            of all chunks containing this word, the largest share
                           belonging to a single statute. 1.00 means the word
                           appears in one statute and nowhere else.

  self-naming rate         of one statute's own chunks, the fraction containing
                           that statute's own distinctive name.

READ-ONLY. Qdrant is scrolled, never written.

    ./venv/Scripts/python.exe experiments/exp10_self_naming.py
"""
from __future__ import annotations

import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from experiments.metrics_lib import wilson

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "self_naming.csv"
COLLECTION = "legal_mvp"

# Same token shape as experiments/exp07_hybrid.py, so df counts are comparable
# with the BM25 arm rather than being a second, private tokenisation.
TOKEN_RE = re.compile(r"\d+[a-z]{0,2}(?:\([0-9a-z]+\))*|[a-z]+")

# Terms named in the task, plus every content word from the four statute titles.
TERMS = ["sanhita", "nyaya", "penal", "code", "adhiniyam", "bharatiya",
         "nagarik", "suraksha", "criminal", "procedure", "consumer",
         "protection", "indian", "sakshya", "evidence", "act"]

# Each statute's own title words, and the single most distinctive of them.
TITLE_TOKENS = {
    "IPC":  ["indian", "penal", "code"],
    "BNS":  ["bharatiya", "nyaya", "sanhita"],
    "CRPC": ["code", "criminal", "procedure"],
    "CPA":  ["consumer", "protection", "act"],
}
DISTINCTIVE = {"IPC": "penal", "BNS": "sanhita", "CRPC": "procedure",
               "CPA": "consumer"}


def tokenise(text: str) -> set[str]:
    return set(TOKEN_RE.findall(text.lower()))


def tokenise_alt(text: str) -> set[str]:
    """Independent route for the paired check: split on non-letters."""
    return {t for t in re.split(r"[^a-z0-9()]+", text.lower()) if t}


def load_chunks() -> list[tuple[str, str]]:
    from qdrant_client import QdrantClient
    c = QdrantClient(url="http://127.0.0.1:6333")
    out, off = [], None
    while True:
        pts, off = c.scroll(COLLECTION, limit=500, offset=off,
                            with_payload=True, with_vectors=False)
        for p in pts:
            out.append((p.payload.get("corpus"), p.payload.get("text") or ""))
        if off is None:
            break
    return out


def okapi_idf(df: int, n: int) -> float:
    return math.log((n - df + 0.5) / (df + 0.5))


def main() -> None:
    chunks = load_chunks()
    N = len(chunks)
    print(f"loaded {N} chunks from Qdrant (read-only)")
    per_corpus_total = Counter(c for c, _ in chunks)
    for k, v in per_corpus_total.most_common():
        print(f"  {k:<6} {v}")
    print()

    toks = [(c, tokenise(t)) for c, t in chunks]

    # df overall and per corpus, for every token in the index
    df_all: Counter = Counter()
    df_corpus: dict[str, Counter] = defaultdict(Counter)
    for corpus, ts in toks:
        for t in ts:
            df_all[t] += 1
            df_corpus[corpus][t] += 1

    rows = []

    def add(metric, qs, defn, value, n, lo="", hi="", notes=""):
        rows.append(dict(metric=metric, query_set=qs, definition=defn,
                         stage="index", k="", value=value, n=n, ci_lo=lo,
                         ci_hi=hi, cluster_ci_lo="", cluster_ci_hi="",
                         notes=notes))

    # ---------------------------------------------------------------- terms
    print("=" * 96)
    print(f"{'term':<13}{'df':>6}{'idf':>8}   " +
          "".join(f"{c:>8}" for c in ("IPC", "BNS", "CRPC", "CPA")) +
          "   concentration")
    print("=" * 96)
    for term in TERMS:
        df = df_all.get(term, 0)
        if df == 0:
            add("document_frequency", "ALL", term, 0, N,
                notes=f"term={term!r}; ABSENT from the index")
            print(f"{term:<13}{0:>6}{'-':>8}   (absent)")
            continue
        idf = okapi_idf(df, N)
        shares = {c: df_corpus[c].get(term, 0) for c in per_corpus_total}
        top = max(shares, key=shares.get)
        conc = shares[top] / df
        p, lo, hi = wilson(df, N)
        add("document_frequency", "ALL", term, df, N, notes=f"term={term!r}")
        add("document_frequency_rate", "ALL", term, p, N, lo, hi,
            notes=f"term={term!r}; share of all {N} indexed chunks")
        add("idf_okapi", "ALL", term, round(idf, 4), N,
            notes=(f"term={term!r}; ln((N-df+0.5)/(df+0.5)) with N={N}, df={df}; "
                   f"the rank_bm25 BM25Okapi form"))
        add("concentration", "ALL", term, round(conc, 4), df,
            notes=f"term={term!r}; largest single-statute share; top={top}")
        for c, k in shares.items():
            pc, lc, hc = wilson(k, per_corpus_total[c])
            add("document_frequency_in_corpus", c, term, k, per_corpus_total[c],
                notes=f"term={term!r}; {k} of {per_corpus_total[c]} chunks in {c}")
            add("document_frequency_rate_in_corpus", c, term, pc,
                per_corpus_total[c], lc, hc, notes=f"term={term!r}")
        print(f"{term:<13}{df:>6}{idf:>8.3f}   " +
              "".join(f"{shares.get(c,0):>8}" for c in ("IPC", "BNS", "CRPC", "CPA")) +
              f"   {conc:.3f} ({top})")

    # ------------------------------------------------- self-naming rate
    print("\n" + "=" * 96)
    print("SELF-NAMING RATE — of a statute's own chunks, how many name it?")
    print("=" * 96)
    for corpus, tot in sorted(per_corpus_total.items()):
        dist = DISTINCTIVE[corpus]
        k = df_corpus[corpus].get(dist, 0)
        p, lo, hi = wilson(k, tot)
        add("self_naming_rate_distinctive", corpus, dist, p, tot, lo, hi,
            notes=(f"distinctive token {dist!r}; {k} of {tot} own chunks contain "
                   f"it; 95% Wilson"))
        anyk = sum(1 for c, ts in toks
                   if c == corpus and any(t in ts for t in TITLE_TOKENS[corpus]))
        pa, la, ha = wilson(anyk, tot)
        add("self_naming_rate_any_title_token", corpus,
            "|".join(TITLE_TOKENS[corpus]), pa, tot, la, ha,
            notes=(f"any of {TITLE_TOKENS[corpus]}; {anyk} of {tot} own chunks"))
        print(f"  {corpus:<6} distinctive {dist!r:<12} {k:>4}/{tot:<5} "
              f"{p*100:5.1f}% [{lo*100:.1f}, {hi*100:.1f}]   "
              f"any title token {anyk:>4}/{tot:<5} {pa*100:5.1f}%")

    # ------------------------------------------- cross-statute confusion
    print("\n" + "=" * 96)
    print("CROSS-STATUTE CONFUSION — where does 'penal' actually live?")
    print("=" * 96)
    pen = {c: df_corpus[c].get("penal", 0) for c in per_corpus_total}
    tot_pen = sum(pen.values())
    for c in ("IPC", "BNS", "CRPC", "CPA"):
        share = pen[c] / tot_pen if tot_pen else 0.0
        p, lo, hi = wilson(pen[c], per_corpus_total[c])
        add("penal_chunks_by_corpus", c, "penal", pen[c], per_corpus_total[c],
            notes=(f"{pen[c]} of {per_corpus_total[c]} chunks in {c} contain "
                   f"'penal'; {share:.1%} of all {tot_pen} chunks containing it"))
        add("penal_share_of_all_occurrences", c, "penal", round(share, 4), tot_pen,
            notes=f"of the {tot_pen} chunks containing 'penal', {pen[c]} are {c}")
        print(f"  {c:<6} {pen[c]:>4} of {per_corpus_total[c]:<5} own chunks   "
              f"= {p*100:5.1f}% [{lo*100:.1f}, {hi*100:.1f}]   "
              f"{share*100:5.1f}% of all 'penal' chunks")
    print(f"\n  The IPC is 595 chunks and contains 'penal' in {pen['IPC']}. "
          f"The CrPC is 742 chunks and contains it in {pen['CRPC']}.")

    # ------------------------------------------------------- discovery
    print("\n" + "=" * 96)
    print("OTHER SELF-NAMING TOKENS FOUND — concentration >= 0.95, df >= 20")
    print("=" * 96)
    found = []
    for t, df in df_all.items():
        if df < 20 or not t.isalpha() or len(t) < 4 or t in TERMS:
            continue
        shares = {c: df_corpus[c].get(t, 0) for c in per_corpus_total}
        top = max(shares, key=shares.get)
        conc = shares[top] / df
        if conc >= 0.95:
            found.append((conc, df, t, top))
    found.sort(key=lambda x: (-x[0], -x[1]))
    for conc, df, t, top in found[:20]:
        idf = okapi_idf(df, N)
        add("discovered_concentrated_token", top, t, round(conc, 4), df,
            notes=(f"token={t!r}; df={df}; idf={idf:.4f}; concentration={conc:.4f} "
                   f"in {top}; discovered by sweep, not pre-specified"))
        print(f"  {t:<20} df={df:<5} idf={idf:5.2f}  concentration={conc:.3f} "
              f"-> {top}")
    if not found:
        print("  none met the threshold")

    add("index_chunks", "ALL", "", N, N, notes="total indexed chunks scrolled")
    for c, v in per_corpus_total.items():
        add("index_chunks_in_corpus", c, "", v, N, notes=f"{c} share of the index")

    cols = ["metric", "query_set", "definition", "stage", "k", "value", "n",
            "ci_lo", "ci_hi", "cluster_ci_lo", "cluster_ci_hi", "notes"]
    pd.DataFrame(rows)[cols].to_csv(OUT, index=False)
    print(f"\nwrote {OUT}  ({len(rows)} rows)")


if __name__ == "__main__":
    main()
