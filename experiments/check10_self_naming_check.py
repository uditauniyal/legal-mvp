"""Paired check for exp10_self_naming.py.

Re-derives the headline document-frequency counts by an INDEPENDENT route and
asserts agreement. Deliberately does not import exp10's tokeniser: it uses a
different splitting strategy, so a bug in one would not be reproduced by the
other.

Also asserts that the numbers reproduce the PROSE figures Wave 3 recorded in
results/EXPLAIN.md, which is the whole point of this experiment -- those figures
had no machine-readable source until now.

    ./venv/Scripts/python.exe experiments/check10_self_naming_check.py
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

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "results" / "self_naming.csv"

# Wave 3's prose claims, from results/EXPLAIN.md. These had no CSV source.
PROSE = {
    "sanhita_df": 30,
    "sanhita_all_bns": True,
    "sanhita_idf": 4.12,
    "penal_crpc": 82,
    "penal_ipc": 23,
    "penal_idf": 2.79,
}

fails: list[str] = []


def check(name: str, ok: bool, detail: str) -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    if not ok:
        fails.append(name)


def main() -> None:
    from qdrant_client import QdrantClient
    c = QdrantClient(url="http://127.0.0.1:6333")
    chunks, off = [], None
    while True:
        pts, off = c.scroll("legal_mvp", limit=500, offset=off,
                            with_payload=True, with_vectors=False)
        chunks += [(p.payload.get("corpus"), p.payload.get("text") or "")
                   for p in pts]
        if off is None:
            break
    N = len(chunks)

    # INDEPENDENT tokeniser: split on non-alphanumerics, keep it dead simple.
    def alt_tokens(t: str) -> set[str]:
        return {w for w in re.split(r"[^a-z0-9]+", t.lower()) if w}

    df_all: Counter = Counter()
    df_corpus: dict[str, Counter] = defaultdict(Counter)
    totals: Counter = Counter()
    for corpus, text in chunks:
        totals[corpus] += 1
        for w in alt_tokens(text):
            df_all[w] += 1
            df_corpus[corpus][w] += 1

    d = pd.read_csv(CSV)

    def val(metric, defn, qs=None):
        s = d[(d.metric == metric) & (d.definition.astype(str) == defn)]
        if qs:
            s = s[s.query_set == qs]
        assert len(s) == 1, f"{metric}/{defn}/{qs} -> {len(s)} rows"
        return float(s.iloc[0]["value"])

    print("=" * 74)
    print("CHECK 1 — index size")
    print("=" * 74)
    check("chunk count", N == 1899, f"{N} chunks (expected 1899)")
    check("corpus split", dict(totals) == {"CRPC": 742, "IPC": 595,
                                           "BNS": 424, "CPA": 138},
          str(dict(totals)))

    print("\n" + "=" * 74)
    print("CHECK 2 — df agrees between two independent tokenisers")
    print("=" * 74)
    for term in ("sanhita", "penal", "code", "criminal", "procedure",
                 "consumer", "indian", "evidence", "bharatiya"):
        got = int(val("document_frequency", term, "ALL"))
        alt = df_all.get(term, 0)
        check(f"df({term})", got == alt, f"exp10={got}  independent={alt}")

    print("\n" + "=" * 74)
    print("CHECK 3 — per-corpus df sums to total df")
    print("=" * 74)
    for term in ("sanhita", "penal", "code", "consumer"):
        tot = int(val("document_frequency", term, "ALL"))
        parts = sum(int(val("document_frequency_in_corpus", term, cc))
                    for cc in ("IPC", "BNS", "CRPC", "CPA"))
        check(f"sum({term})", tot == parts, f"total={tot}  parts={parts}")

    print("\n" + "=" * 74)
    print("CHECK 4 — idf recomputed by hand")
    print("=" * 74)
    for term in ("sanhita", "penal"):
        df = df_all[term]
        hand = math.log((N - df + 0.5) / (df + 0.5))
        got = val("idf_okapi", term, "ALL")
        check(f"idf({term})", abs(hand - got) < 1e-4,
              f"exp10={got:.4f}  hand={hand:.4f}")

    print("\n" + "=" * 74)
    print("CHECK 5 — does this reproduce Wave 3's PROSE claims?")
    print("        (they had no machine-readable source until now)")
    print("=" * 74)
    check("sanhita df == 30", df_all["sanhita"] == PROSE["sanhita_df"],
          f"{df_all['sanhita']} vs prose {PROSE['sanhita_df']}")
    check("sanhita is 100% BNS",
          df_corpus["BNS"]["sanhita"] == df_all["sanhita"],
          f"{df_corpus['BNS']['sanhita']} of {df_all['sanhita']} in BNS")
    check("sanhita idf ~ 4.12",
          abs(val("idf_okapi", "sanhita", "ALL") - PROSE["sanhita_idf"]) < 0.01,
          f"{val('idf_okapi', 'sanhita', 'ALL'):.4f} vs prose 4.12")
    check("penal in CRPC == 82", df_corpus["CRPC"]["penal"] == PROSE["penal_crpc"],
          f"{df_corpus['CRPC']['penal']} vs prose {PROSE['penal_crpc']}")
    check("penal in IPC == 23", df_corpus["IPC"]["penal"] == PROSE["penal_ipc"],
          f"{df_corpus['IPC']['penal']} vs prose {PROSE['penal_ipc']}")
    check("penal idf ~ 2.79",
          abs(val("idf_okapi", "penal", "ALL") - PROSE["penal_idf"]) < 0.01,
          f"{val('idf_okapi', 'penal', 'ALL'):.4f} vs prose 2.79")

    print("\n" + "=" * 74)
    print("CHECK 6 — the asymmetry, stated as an inequality")
    print("=" * 74)
    ipc_rate = df_corpus["IPC"]["penal"] / totals["IPC"]
    crpc_rate = df_corpus["CRPC"]["penal"] / totals["CRPC"]
    check("'penal' is commoner in CrPC than in the IPC itself",
          crpc_rate > ipc_rate,
          f"CrPC {crpc_rate:.3%} > IPC {ipc_rate:.3%}")
    check("'sanhita' is a perfect BNS discriminator, 'penal' is not for IPC",
          df_corpus["BNS"]["sanhita"] / df_all["sanhita"] == 1.0
          and df_corpus["IPC"]["penal"] / df_all["penal"] < 0.5,
          f"sanhita->BNS 100%, penal->IPC "
          f"{df_corpus['IPC']['penal'] / df_all['penal']:.1%}")

    print("\n" + "=" * 74)
    if fails:
        print(f"{len(fails)} CHECK(S) FAILED: {fails}")
        sys.exit(1)
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
