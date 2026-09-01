"""check07 -- INDEPENDENT VERIFICATION OF exp07_hybrid.py.  Wave 3, Subagent 2.

WHY A SEPARATE SCRIPT
    exp07 leans on two things a reader cannot see: a third-party BM25
    implementation and a fusion rule written here for the first time. If
    either is wrong the headline is wrong in a way that looks entirely
    plausible. So each is re-derived by a route that shares no code with
    exp07, and the two answers are ASSERTED equal.

    A disagreement is a FINDING. Nothing here adjusts to match.

WHAT IS CHECKED

  C1  BM25 index size            exactly 1,899 documents, one per Qdrant point,
                                 and the corpus shares match the chance
                                 baseline printed by scripts/ablate_filter.py.

  C2  RRF on paper               a four-document toy whose fused order was
                                 worked out by hand before the code ran, plus
                                 a tie case, plus the arithmetic of the real
                                 P0002 example quoted in the explanation.

  C3  RRF one-arm identity       fusing a SINGLE list must return that list
                                 unchanged, and fusing a list with a copy of
                                 itself must also return it unchanged. This is
                                 "hybrid with one arm's weight removed
                                 reproduces that arm alone", and it is checked
                                 twice: on toy lists, and on the real
                                 filter-disabled dense results for all 33
                                 BNS-named queries.

  C4  BM25 re-implemented        Okapi BM25 written out from the formula in
                                 plain Python dicts -- no numpy, no rank_bm25 --
                                 with a SECOND tokeniser written by a different
                                 method (character scan, not regex findall).
                                 It must reproduce exp07's headline BM25
                                 numbers exactly: BNS-named 32/33 dominant,
                                 IPC-named 0/33 dominant.

  C5  Headline provenance        the dense headline this experiment reproduces
                                 must equal the published ablate_filter values
                                 (IPC 32/33, BNS 17/33 dominant; 30/33 and
                                 14/33 top-1).

ZERO API CALLS if experiments/exp07_hybrid.py has been run once -- the query
embeddings come from its cache. READ-ONLY on Qdrant.

Run:  ./venv/Scripts/python.exe experiments/check07_hybrid_check.py
"""
from __future__ import annotations

import collections
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import experiments.exp07_hybrid as E                                # noqa: E402
from experiments.metrics_lib import load_queryset                   # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print("  [%s] %s%s" % ("PASS" if ok else "FAIL", name,
                           ("  -- " + detail) if detail else ""))
    if not ok:
        FAILURES.append("%s: %s" % (name, detail))


# ====================================================== an INDEPENDENT tokeniser
#
# Same rule as exp07's, implemented by a different method: a left-to-right
# character scan with an explicit state machine, rather than a regex findall.
# Two implementations of one rule that disagree on real statute text mean the
# rule is not actually well defined.

_FIX = E._UNICODE_FIX


def tokenise2(text: str) -> list[str]:
    if not text:
        return []
    s = str(text).translate(_FIX).lower()
    out: list[str] = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c.isdigit():
            j = i
            while j < n and s[j].isdigit():
                j += 1
            digits = s[i:j]
            k = j
            while k < n and s[k].isalpha() and (k - j) < 2:
                k += 1
            letters = s[j:k]
            # a longer letter run means this was never a section number
            if k < n and s[k].isalpha():
                while k < n and s[k].isalpha():
                    k += 1
                out.append(digits)
                out.append(s[j:k])
                i = k
                continue
            groups: list[str] = []
            m = k
            while m < n and s[m] == "(":
                p = s.find(")", m)
                if p == -1:
                    break
                body = s[m + 1:p]
                if not body or not all(ch.isalnum() for ch in body):
                    break
                groups.append("(" + body + ")")
                m = p + 1
            base = digits + letters
            full = base + "".join(groups)
            out.append(full)
            for t in range(len(groups) - 1, -1, -1):
                cand = base + "".join(groups[:t])
                if cand != full:
                    out.append(cand)
            if letters and digits != base:
                out.append(digits)
            i = m
        elif c.isalpha():
            j = i
            while j < n and s[j].isalpha():
                j += 1
            out.append(s[i:j])
            i = j
        else:
            i += 1
    return out


# ====================================================== an INDEPENDENT BM25
#
# Okapi BM25, written out from the formula rather than called from a library.
#
#     idf(q)   = log(N - n(q) + 0.5) - log(n(q) + 0.5)
#                floored at eps * mean(idf) when negative, eps = 0.25
#     score(d) = SUM over query terms of
#                    idf(q) * f(q,d)*(k1+1)
#                             ------------------------------------
#                             f(q,d) + k1*(1 - b + b*|d|/avgdl)
#
#     k1 = 1.5, b = 0.75 -- the values rank_bm25 uses by default, stated here
#     so the comparison is of implementations and not of parameters.

class PlainBM25:
    def __init__(self, docs_tokens: list[list[str]], k1=1.5, b=0.75, eps=0.25):
        self.k1, self.b = k1, b
        self.N = len(docs_tokens)
        self.freqs = [collections.Counter(d) for d in docs_tokens]
        self.lens = [len(d) for d in docs_tokens]
        self.avgdl = sum(self.lens) / self.N
        nd: dict[str, int] = collections.Counter()
        for f in self.freqs:
            for w in f:
                nd[w] += 1
        self.idf, neg = {}, []
        for w, c in nd.items():
            v = math.log(self.N - c + 0.5) - math.log(c + 0.5)
            self.idf[w] = v
            if v < 0:
                neg.append(w)
        floor = eps * (sum(self.idf.values()) / len(self.idf))
        for w in neg:
            self.idf[w] = floor

    def scores(self, query_tokens: list[str]) -> list[float]:
        out = [0.0] * self.N
        for q in query_tokens:
            idf = self.idf.get(q)
            if idf is None:
                continue
            for i in range(self.N):
                f = self.freqs[i].get(q, 0)
                if f:
                    denom = f + self.k1 * (1 - self.b + self.b * self.lens[i] / self.avgdl)
                    out[i] += idf * (f * (self.k1 + 1) / denom)
        return out

    def topn(self, query: str, n: int) -> list[int]:
        s = self.scores(tokenise2(query))
        return sorted(range(self.N), key=lambda i: (-s[i], i))[:n]


# ====================================================== checks

def main() -> None:
    print("check07 -- independent verification of exp07_hybrid.py\n")

    # ---------------------------------------------------------------- C2, C3
    print("C2  Reciprocal Rank Fusion, worked out on paper first")
    #   list A (dense) = [d1, d2, d3];  list B (bm25) = [d3, d1, d4];  k = 60
    #     d1 = 1/61 + 1/62 = 0.0163934426 + 0.0161290323 = 0.0325224749
    #     d3 = 1/63 + 1/61 = 0.0158730159 + 0.0163934426 = 0.0322664585
    #     d2 = 1/62                                      = 0.0161290323
    #     d4 = 1/63                                      = 0.0158730159
    #   so the fused order must be d1, d3, d2, d4.
    A, B = ["d1", "d2", "d3"], ["d3", "d1", "d4"]
    hand = ["d1", "d3", "d2", "d4"]
    got = E.rrf_fuse([A, B], 60)
    check("toy fusion matches the hand-computed order", got == hand,
          "hand %s vs code %s" % (hand, got))

    hand_scores = {"d1": 1/61 + 1/62, "d3": 1/63 + 1/61,
                   "d2": 1/62, "d4": 1/63}
    scored = collections.defaultdict(float)
    for lst in (A, B):
        for r, d in enumerate(lst, 1):
            scored[d] += 1.0 / (60 + r)
    check("toy fusion scores match the hand arithmetic",
          all(abs(scored[d] - hand_scores[d]) < 1e-12 for d in hand_scores))

    #   tie case: A = [7, 8], B = [8, 7] gives both documents 1/61 + 1/62.
    #   Both reach best-rank 1, so the tie falls through to document id: [7, 8].
    check("ties break deterministically by best rank then id",
          E.rrf_fuse([[7, 8], [8, 7]], 60) == [7, 8])

    #   the real P0002 arithmetic quoted in results/_explain_w3_s2.md
    #   BNS 190: dense rank 3, bm25 rank 1  -> 1/63 + 1/61 = 0.032266458
    #   IPC 149: dense rank 2, bm25 rank 2  -> 1/62 + 1/62 = 0.032258065
    bns190 = 1/63 + 1/61
    ipc149 = 1/62 + 1/62
    check("the P0002 margin quoted in the write-up is arithmetically right",
          abs(bns190 - 0.032266458) < 1e-8 and abs(ipc149 - 0.032258065) < 1e-8
          and bns190 > ipc149,
          "BNS190 %.9f > IPC149 %.9f by %.9f" % (bns190, ipc149, bns190 - ipc149))

    print("\nC3  fusing one arm alone must reproduce that arm")
    one = [5, 3, 9, 1, 7]
    check("rrf_fuse of a single list is the identity",
          E.rrf_fuse([one], 60) == one)
    check("rrf_fuse of a list with a copy of itself is the identity",
          E.rrf_fuse([one, one], 60) == one)

    # ---------------------------------------------------------------- C1
    print("\nC1  the BM25 index")
    docs = E.load_corpus()
    bm25, toks = E.build_bm25(docs)
    check("BM25 index holds exactly 1899 documents",
          len(toks) == 1899 and len(docs) == 1899,
          "docs=%d tokenised=%d" % (len(docs), len(toks)))
    check("rank_bm25 agrees on its own corpus size",
          bm25.corpus_size == 1899, "corpus_size=%d" % bm25.corpus_size)
    shares = E.corpus_shares(docs)
    want = {"CRPC": 0.391, "IPC": 0.313, "BNS": 0.223, "CPA": 0.073}
    check("corpus shares match the ablate_filter.py chance baseline",
          all(abs(shares[c] - v) < 0.001 for c, v in want.items()),
          " ".join("%s %.3f" % (c, shares[c]) for c in want))

    # ---------------------------------------------------------------- C4a
    print("\nC4  a second tokeniser and a second BM25")
    sample = [(d.get("text") or "") for d in docs[::37]]
    disagree = [t for t in sample if E.tokenise(t) != tokenise2(t)]
    check("the regex tokeniser and the character-scan tokeniser agree on %d "
          "real chunks" % len(sample), not disagree,
          "%d disagreements, first: %r" % (len(disagree),
                                           disagree[0][:120] if disagree else ""))

    probes = ["Section 318(4).", "BNS 304B", "s. 498A(1)(b)", "Section 41A CrPC",
              "punishment under Section 302 IPC", "the Sanhita, 2023"]
    bad = [p for p in probes if E.tokenise(p) != tokenise2(p)]
    check("the two tokenisers agree on the six documented examples", not bad,
          str(bad))

    plain = PlainBM25([tokenise2(d.get("text") or "") for d in docs])

    # ---------------------------------------------------------------- C4b/C5
    print("\nC4/C5  the headline, re-derived")
    rows = [r for r in load_queryset(ROOT / "eval" / "paired_queryset.jsonl")
            .to_dict("records") if r["variant"] in ("ipc_numbered", "bns_numbered")]
    check("66 numbered paired queries", len(rows) == 66, "got %d" % len(rows))

    def dominant(ix: list[int]) -> str:
        c = collections.Counter(docs[j].get("corpus") for j in ix[:E.WINDOW])
        return c.most_common(1)[0][0] if c else ""

    lib = collections.Counter()
    ind = collections.Counter()
    for r in rows:
        want_c = r["expected_corpus"]
        lib[(r["variant"], dominant(E.bm25_topn(bm25, r["text"], E.DEPTH)) == want_c)] += 1
        ind[(r["variant"], dominant(plain.topn(r["text"], E.DEPTH)) == want_c)] += 1

    for variant, expect_k in (("bns_numbered", 32), ("ipc_numbered", 0)):
        k_lib, k_ind = lib[(variant, True)], ind[(variant, True)]
        check("BM25 %s dominant-corpus accuracy: library %d/33, independent "
              "re-implementation %d/33" % (variant, k_lib, k_ind),
              k_lib == k_ind == expect_k,
              "exp07 reported %d/33" % expect_k)

    # dense arm: from the exp07 cache, so this costs nothing after one run
    from clients.qdrant_client import qdrant, COLLECTION
    client = qdrant()
    id_to_ix = {d["_point_id"]: i for i, d in enumerate(docs)}
    vecs, charged = E.embed_queries([r["text"] for r in rows])
    if charged:
        print("      (embedded %d tokens -- exp07's cache was cold)" % charged)

    dense_dom = collections.Counter()
    dense_top1 = collections.Counter()
    fused_alone_agrees = True
    for r, v in zip(rows, vecs):
        d_ix = E.dense_topn(client, COLLECTION, v, E.DEPTH, id_to_ix)
        want_c = r["expected_corpus"]
        dense_dom[(r["variant"], dominant(d_ix) == want_c)] += 1
        dense_top1[(r["variant"],
                    (docs[d_ix[0]].get("corpus") if d_ix else None) == want_c)] += 1
        if E.rrf_fuse([d_ix], E.RRF_K) != d_ix:
            fused_alone_agrees = False

    check("on all 66 real dense result lists, fusing the dense arm alone "
          "returns it unchanged", fused_alone_agrees)

    for variant, want_dom, want_t1 in (("ipc_numbered", 32, 30),
                                       ("bns_numbered", 17, 14)):
        check("dense %s reproduces ablate_filter.py: dominant %d/33, top-1 %d/33"
              % (variant, dense_dom[(variant, True)], dense_top1[(variant, True)]),
              dense_dom[(variant, True)] == want_dom
              and dense_top1[(variant, True)] == want_t1,
              "published: dominant %d/33, top-1 %d/33" % (want_dom, want_t1))

    # ---------------------------------------------------------------- C6
    #
    # The gold-reachability ceiling is an INVARIANT, not a measurement: no
    # retriever can score a query correct when the gold provision is not in the
    # index under strict section identity. If any arm exceeds its set's
    # ceiling, either the ceiling or the recall is wrong.
    print("\nC6  no arm may exceed the gold-reachability ceiling")
    import pandas as pd                                              # noqa: E402
    from experiments.metrics_lib import normalise_section            # noqa: E402
    csv = ROOT / "results" / "hybrid_comparison.csv"
    if not csv.exists():
        check("results/hybrid_comparison.csv exists", False,
              "run exp07_hybrid.py first")
    else:
        d = pd.read_csv(csv)
        indexed = {normalise_section("%s %s" % (x.get("corpus"),
                                                x.get("section_number")))
                   for x in docs if x.get("section_number")}
        bns = [r for r in load_queryset(ROOT / "eval" / "paired_queryset.jsonl")
               .to_dict("records") if r["variant"] == "bns_numbered"]
        reach = sum(1 for r in bns if any(s in indexed
                                          for s in map(normalise_section,
                                                       r["expected_sections"])))
        check("BNS-named gold reachable in the index: 11 of 33",
              reach == 11, "got %d -- 22 gold labels name a subsection "
                           "('BNS 318(4)') the index records only as '318'"
              % reach)
        ceil = d[d.metric == "gold_reachable_ceiling"].set_index("query_set")["value"]
        rec = d[(d.metric == "recall_at_k") & (d.k == 15)]
        over = [(r.query_set, r.stage, r.value, ceil[r.query_set])
                for r in rec.itertuples()
                if r.query_set in ceil.index and r.value > ceil[r.query_set] + 1e-9]
        check("no arm's Recall@15 exceeds its set's ceiling", not over, str(over))

    print()
    if FAILURES:
        print("  %d CHECK(S) FAILED -- DO NOT USE results/hybrid_comparison.csv"
              % len(FAILURES))
        for f in FAILURES:
            print("    " + f)
        raise SystemExit(1)
    print("  all checks passed")


if __name__ == "__main__":
    main()
