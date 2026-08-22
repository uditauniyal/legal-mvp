#!/usr/bin/env python3
"""Turn evaluation runs into the result tables.

WHAT THIS IS
    scripts/run_eval.py sends the queries and records what happened. This
    script reads those records and computes the numbers that go in the paper.
    It touches no network and no LLM, so it can be re-run any number of times
    on the same logs and must produce identical output.

WHY THE TWO FILES HAVE TO BE JOINED
    Each query produces two records in two different places:

        runs/eval_<stamp>_<sha>/eval_summary.jsonl   written by the RUNNER.
            Carries the GOLD -- expected_sections, expected_corpus, variant,
            messiness -- because only the runner knows what was asked.

        runs/<stamp>_<sha>/queries.jsonl             written by the SERVER.
            Carries what HAPPENED -- which chunks came back, from which
            corpus, what the answer cited, every confidence signal.

    Neither alone can answer "did it retrieve the right section?". They are
    joined on req_id.

WHY SECTION NUMBERS ARE PARSED OUT OF text_head
    The logged chunk records doc, page, corpus, score and the first 160
    characters of text -- but not section_number. Section-split chunks always
    begin "Section 141. ...", so the number is recoverable from the text.
    Stated here because it is a workaround: adding section_number to the log
    would be better and is a one-line change for the next run.

CONFIDENCE INTERVALS
    Every proportion is reported with a 95% Wilson interval. With ~33 queries
    per cell a bare fraction is close to meaningless -- 30/33 and 27/33 have
    heavily overlapping intervals, and reporting them as "91%" and "82%"
    implies a difference the data does not support.

USAGE
    python scripts/analyze_eval.py                 newest run of each set
    python scripts/analyze_eval.py --runs runs/eval_2026-08-23_0210_bfcc18d
    python scripts/analyze_eval.py --md docs/results/phase_g.md
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"

from core.citations import extract_provisions, same_provision  # noqa: E402

SECTION_HEAD = re.compile(r"Section\s+(\d+[A-Za-z]?)")


# ---------------------------------------------------------------- statistics

def wilson(k: int, n: int) -> tuple[float, float, float]:
    """Proportion with a 95% Wilson score interval.

    Wilson rather than the textbook normal interval because at the extremes
    the normal one is simply wrong: 33/33 gives +/- 0.00, claiming certainty
    from 33 observations. Wilson stays inside [0,1] and keeps a sane width
    when the count is at a boundary.
    """
    if n == 0:
        return 0.0, 0.0, 0.0
    z = 1.959963985
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, centre - half), min(1.0, centre + half)


def pct(k: int, n: int) -> str:
    p, lo, hi = wilson(k, n)
    if n == 0:
        return "     -      "
    return f"{100*p:5.1f}% [{100*lo:4.1f},{100*hi:5.1f}]"


def auroc(scores: list[float], labels: list[bool]) -> float | None:
    """Probability that a randomly chosen positive outranks a random negative.

    0.5 = the score carries no information. Computed by direct pairwise
    comparison (Mann-Whitney U); n is a few hundred, so the quadratic cost is
    irrelevant and the definition stays legible.
    """
    pos = [s for s, l in zip(scores, labels) if l]
    neg = [s for s, l in zip(scores, labels) if not l]
    if not pos or not neg:
        return None
    wins = sum((1.0 if p > n else 0.5 if p == n else 0.0) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


# ---------------------------------------------------------------- loading

def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def load_server_records() -> dict[str, dict]:
    """Every server-side record in runs/, keyed by req_id."""
    by_req: dict[str, dict] = {}
    for path in RUNS.rglob("queries.jsonl"):
        for rec in load_jsonl(path):
            if rec.get("req_id"):
                by_req[rec["req_id"]] = rec
    return by_req


def newest_runs() -> list[Path]:
    """Most recent eval_* directory per query-set category."""
    best: dict[str, Path] = {}
    for d in sorted(RUNS.glob("eval_*")):
        rows = load_jsonl(d / "eval_summary.jsonl")
        if not rows:
            continue
        cat = rows[0].get("category", "?")
        best[cat] = d          # sorted order means later wins
    return list(best.values())


# ---------------------------------------------------------------- retrieval

def chunk_refs(rec: dict) -> list[str]:
    """Provisions actually retrieved, as 'CORPUS number' strings."""
    out = []
    for c in (rec.get("retrieval", {}).get("chunks") or []):
        corpus, head = c.get("corpus"), c.get("text_head") or ""
        m = SECTION_HEAD.search(head)
        if corpus and m:
            out.append(f"{corpus} {m.group(1)}")
    return out


def retrieved_corpora(rec: dict) -> collections.Counter:
    return collections.Counter(
        c.get("corpus") for c in (rec.get("retrieval", {}).get("chunks") or []) if c.get("corpus")
    )


def gold_retrieved(gold: list[str], retrieved: list[str]) -> bool:
    """Is any gold provision among the retrieved chunks?

    Compared through same_provision(), so 'BNS 318(4)' matches a retrieved
    'BNS 318' -- the chunk carries the whole section including its
    sub-sections, and demanding the sub-section be echoed in the first 160
    characters would under-count real hits.
    """
    gp = [p for g in gold for p in extract_provisions(g.replace(" ", " Section "))]
    rp = [p for r in retrieved for p in extract_provisions(r.replace(" ", " Section "))]
    return any(same_provision(g, r, lenient=True) for g in gp for r in rp)


def cited_refs(rec: dict) -> list[str]:
    return list(rec.get("verifier", {}).get("cited") or [])


def gold_cited(gold: list[str], rec: dict) -> bool:
    gp = [p for g in gold for p in extract_provisions(g.replace(" ", " Section "))]
    cp = [p for c in cited_refs(rec) for p in extract_provisions(c)]
    return any(same_provision(g, c, lenient=True) for g in gp for c in cp)


# ---------------------------------------------------------------- reporting

class Report:
    def __init__(self):
        self.lines: list[str] = []

    def __call__(self, s: str = "") -> None:
        print(s)
        self.lines.append(s)

    def head(self, title: str) -> None:
        self("")
        self("=" * 96)
        self(f"  {title}")
        self("=" * 96)


def join(run_dirs: list[Path], server: dict[str, dict]) -> list[dict]:
    joined = []
    for d in run_dirs:
        for row in load_jsonl(d / "eval_summary.jsonl"):
            rec = server.get(row.get("req_id") or "")
            if rec:
                joined.append({"gold": row, "rec": rec, "run": d.name})
    return joined


def table_cross_statute(R: Report, rows: list[dict]) -> None:
    paired = [r for r in rows if r["gold"].get("category") == "paired_recodification"]
    if not paired:
        return
    R.head("E1 · CROSS-STATUTE RETRIEVAL — the paired IPC↔BNS set")
    R("")
    R("  Same offence, same wording. The only thing that changes across a pair is")
    R("  the numbering scheme. 'counterpart' = found the OTHER code's version of")
    R("  the same provision, which is the specific failure this paper names.")
    R("")
    R(f"  {'VARIANT':<16}{'N':>4}   {'GOLD RETRIEVED':^22}   {'COUNTERPART RETRIEVED':^22}   {'GOLD CITED':^22}")
    R("  " + "-" * 92)
    for variant in ("ipc_numbered", "bns_numbered", "neutral_topic"):
        sub = [r for r in paired if r["gold"].get("variant") == variant]
        if not sub:
            continue
        n = len(sub)
        hit = sum(gold_retrieved(r["gold"]["expected_sections"], chunk_refs(r["rec"])) for r in sub)
        cpt = sum(gold_retrieved(r["gold"].get("counterpart_sections") or [], chunk_refs(r["rec"]))
                  for r in sub)
        cit = sum(gold_cited(r["gold"]["expected_sections"], r["rec"]) for r in sub)
        R(f"  {variant:<16}{n:>4}   {pct(hit,n):^22}   {pct(cpt,n):^22}   {pct(cit,n):^22}")

    R("")
    R("  Corpus confusion — expected (rows) against the corpus supplying the most")
    R("  retrieved chunks (columns). Off-diagonal entries ARE the failure.")
    R("")
    corpora = ["IPC", "BNS", "CRPC", "CPA"]
    R(f"  {'EXPECTED':<10}" + "".join(f"{c:>8}" for c in corpora) + f"{'N':>8}")
    R("  " + "-" * 52)
    for exp in ("IPC", "BNS"):
        sub = [r for r in paired if r["gold"].get("expected_corpus") == exp]
        if not sub:
            continue
        got = collections.Counter()
        for r in sub:
            rc = retrieved_corpora(r["rec"])
            if rc:
                got[rc.most_common(1)[0][0]] += 1
        R(f"  {exp:<10}" + "".join(f"{got.get(c,0):>8}" for c in corpora) + f"{len(sub):>8}")


def table_date(R: Report, rows: list[dict]) -> None:
    lay = [r for r in rows if r["gold"].get("category") == "layman_situation"]
    if not lay:
        return
    R.head("E2 · THE DATE EXPERIMENT — does stating when it happened change anything?")
    R("")
    R("  ipc_era says 'in March 2023' (IPC governs). bns_era says 'last month'")
    R("  (BNS governs). no_date and vague resolve nothing, so BOTH eras count.")
    R("  CPA rows are CONTROLS: the Consumer Protection Act was untouched by the")
    R("  recodification, so its numbers must NOT move across the four conditions.")
    R("")
    R(f"  {'VARIANT':<10}{'N':>4}   {'GOLD RETRIEVED':^22}   {'GOLD CITED':^22}   {'CORPUS CORRECT':^22}")
    R("  " + "-" * 86)
    for variant in ("no_date", "ipc_era", "bns_era", "vague"):
        sub = [r for r in lay
               if r["gold"].get("variant") == variant
               and not r["gold"].get("control_unchanged_statute")
               and r["gold"].get("answerable_from_corpus")]
        if not sub:
            continue
        n = len(sub)
        hit = sum(gold_retrieved(r["gold"]["expected_sections"], chunk_refs(r["rec"])) for r in sub)
        cit = sum(gold_cited(r["gold"]["expected_sections"], r["rec"]) for r in sub)
        corr = 0
        for r in sub:
            want = set(r["gold"].get("expected_corpora") or [])
            rc = retrieved_corpora(r["rec"])
            if rc and rc.most_common(1)[0][0] in want:
                corr += 1
        R(f"  {variant:<10}{n:>4}   {pct(hit,n):^22}   {pct(cit,n):^22}   {pct(corr,n):^22}")

    ctrl = [r for r in lay if r["gold"].get("control_unchanged_statute")]
    if ctrl:
        R("")
        R("  CONTROLS (CPA — gold identical in all four conditions)")
        for variant in ("no_date", "ipc_era", "bns_era", "vague"):
            sub = [r for r in ctrl if r["gold"].get("variant") == variant]
            if not sub:
                continue
            hit = sum(gold_retrieved(r["gold"]["expected_sections"], chunk_refs(r["rec"])) for r in sub)
            R(f"    {variant:<10}{len(sub):>4}   gold retrieved {pct(hit,len(sub))}")


def table_citations(R: Report, rows: list[dict]) -> None:
    R.head("E3 · CITATION GROUNDING — does the answer cite what was retrieved?")
    R("")
    R("  ungrounded   cited, but not present in the passages the model was given.")
    R("               NOT the same as wrong: a provision can be correct law and")
    R("               still be ungrounded.")
    R("  out-of-corpus  the Act was never indexed, so retrieval cannot explain it.")
    R("  jaccard      overlap between the sources SHOWN and the provisions CITED.")
    R("               1.0 = the citation panel matches the prose.")
    R("")
    R(f"  {'QUERY SET':<26}{'N':>4}{'CITED':>8}{'UNGR':>8}{'OOC':>8}{'JACCARD':>9}"
      f"{'SUCC':>7}{'PRED':>7}")
    R("  " + "-" * 78)
    by_cat = collections.defaultdict(list)
    for r in rows:
        by_cat[r["gold"].get("category", "?")].append(r)
    for cat, sub in sorted(by_cat.items()):
        v = [r["rec"].get("verifier", {}) for r in sub]
        v = [x for x in v if x]
        if not v:
            continue
        def m(key):
            vals = [x.get(key, 0) or 0 for x in v]
            return sum(vals) / len(vals)
        R(f"  {cat:<26}{len(v):>4}{m('n_cited'):>8.1f}{m('ungrounded_rate'):>8.3f}"
          f"{m('out_of_corpus_rate'):>8.3f}{m('panel_prose_jaccard'):>9.3f}"
          f"{m('n_cited_successor'):>7.2f}{m('n_cited_predecessor'):>7.2f}")

    R("")
    R("  SUCC = corpus-vintage mismatch, cited the successor code (e.g. BNSS)")
    R("         while the index holds only the predecessor (CrPC). Per answer.")
    R("  PRED = the reverse direction.")


def table_confidence(R: Report, rows: list[dict]) -> None:
    R.head("E4 · DOES CONFIDENCE DETECT ANY OF THIS?")
    R("")
    R("  AUROC = probability the score ranks a GOOD answer above a BAD one.")
    R("  0.5 means the score carries no information at all. This is the")
    R("  experiment that decides whether the confidence system is worth keeping.")
    R("")
    usable = [r for r in rows if r["rec"].get("verifier")]
    if not usable:
        return

    def report(name: str, labels: list[bool], scores: list[float]) -> None:
        a = auroc(scores, labels)
        pos = sum(labels)
        if a is None:
            R(f"  {name:<44}  n/a  (all {pos}/{len(labels)} on one side)")
        else:
            R(f"  {name:<44}{a:6.3f}   positives {pos}/{len(labels)}")

    conf = [r["rec"]["confidence"]["composite"] for r in usable]
    report("composite confidence vs fully grounded",
           [(r["rec"]["verifier"].get("ungrounded_rate", 1) == 0) for r in usable], conf)
    report("composite confidence vs gold retrieved",
           [gold_retrieved(r["gold"].get("expected_sections") or [], chunk_refs(r["rec"]))
            for r in usable], conf)
    report("composite confidence vs gold cited",
           [gold_cited(r["gold"].get("expected_sections") or [], r["rec"]) for r in usable], conf)

    R("")
    R("  Same comparisons for each signal separately (the E6 ablation):")
    for sig in ("top_k_mean", "score_gap", "entity_coverage"):
        s = [r["rec"]["confidence"].get(sig, 0) for r in usable]
        report(f"  {sig} vs fully grounded",
               [(r["rec"]["verifier"].get("ungrounded_rate", 1) == 0) for r in usable], s)
    s = [r["rec"]["retrieval"].get("max_score", 0) for r in usable]
    report("  raw max similarity vs fully grounded",
           [(r["rec"]["verifier"].get("ungrounded_rate", 1) == 0) for r in usable], s)


def table_refusal(R: Report, rows: list[dict]) -> None:
    R.head("E5 · REFUSAL — does the system know what it does not have?")
    R("")
    reasons = collections.Counter(
        (r["rec"].get("confidence", {}).get("refusal_reason") or "not refused") for r in rows)
    R(f"  {'REASON':<28}{'N':>6}")
    R("  " + "-" * 34)
    for k, v in reasons.most_common():
        R(f"  {k:<28}{v:>6}")

    ans = [r for r in rows if r["gold"].get("answerable_from_corpus") is True]
    una = [r for r in rows if r["gold"].get("answerable_from_corpus") is False]
    R("")
    R("  The gate is only working if these two rows differ sharply.")
    R("")
    for label, sub in (("answerable from corpus", ans), ("NOT answerable (BNSS absent)", una)):
        if not sub:
            continue
        ref = sum(1 for r in sub if r["rec"].get("confidence", {}).get("refused"))
        R(f"  {label:<32}{len(sub):>4}   refused {pct(ref,len(sub))}")


def table_messiness(R: Report, rows: list[dict]) -> None:
    lay = [r for r in rows
           if r["gold"].get("category") == "layman_situation"
           and r["gold"].get("answerable_from_corpus")]
    if not lay:
        return
    R.head("E6 · MESSINESS — the access-to-justice claim, as a number")
    R("")
    R("  1 = fairly clear   2 = typical   3 = very fragmented / barely coherent")
    R("  If accuracy falls as messiness rises, the people least able to phrase a")
    R("  legal question precisely are the ones the system serves worst.")
    R("")
    R(f"  {'MESSINESS':<12}{'N':>4}   {'GOLD RETRIEVED':^22}   {'GOLD CITED':^22}{'CONF':>8}")
    R("  " + "-" * 74)
    for level in (1, 2, 3):
        sub = [r for r in lay if r["gold"].get("messiness") == level]
        if not sub:
            continue
        n = len(sub)
        hit = sum(gold_retrieved(r["gold"]["expected_sections"], chunk_refs(r["rec"])) for r in sub)
        cit = sum(gold_cited(r["gold"]["expected_sections"], r["rec"]) for r in sub)
        conf = sum(r["rec"]["confidence"]["composite"] for r in sub) / n
        R(f"  {level:<12}{n:>4}   {pct(hit,n):^22}   {pct(cit,n):^22}{conf:>8.3f}")


def table_routing(R: Report, rows: list[dict]) -> None:
    R.head("E7 · ROUTING — which rule fired, and did it help?")
    R("")
    paths = collections.Counter(r["rec"].get("router", {}).get("decision_path", "?") for r in rows)
    R(f"  {'DECISION PATH':<38}{'N':>5}   {'GOLD RETRIEVED':^22}")
    R("  " + "-" * 70)
    for path, n in paths.most_common():
        sub = [r for r in rows if r["rec"].get("router", {}).get("decision_path") == path]
        hit = sum(gold_retrieved(r["gold"].get("expected_sections") or [], chunk_refs(r["rec"]))
                  for r in sub)
        R(f"  {path:<38}{n:>5}   {pct(hit,len(sub)):^22}")

    fb = sum(1 for r in rows if r["rec"].get("retrieval", {}).get("filter_fallback_fired"))
    R("")
    R(f"  filter fallback fired (corpus filter matched nothing): {fb}/{len(rows)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="*", type=Path, help="run dirs; default = newest per set")
    ap.add_argument("--md", type=Path, help="also write the report to this file")
    args = ap.parse_args()

    server = load_server_records()
    run_dirs = args.runs or newest_runs()
    rows = join(run_dirs, server)

    R = Report()
    R.head("PHASE G RESULTS")
    R("")
    for d in run_dirs:
        R(f"  run   {d.name}")
    R(f"  server records available   {len(server)}")
    R(f"  joined rows                {len(rows)}")
    if not rows:
        R("")
        R("  NOTHING JOINED. The runner and server records share req_id; if this is")
        R("  zero, the server was writing to a different runs/ directory.")
        return
    errs = sum(1 for r in rows if r["gold"].get("error"))
    R(f"  rows with a transport error {errs}")

    table_cross_statute(R, rows)
    table_date(R, rows)
    table_citations(R, rows)
    table_confidence(R, rows)
    table_refusal(R, rows)
    table_messiness(R, rows)
    table_routing(R, rows)

    R("")
    R("  Every proportion carries a 95% Wilson interval. Cells with ~30 queries")
    R("  have intervals roughly +/-15 points wide: read the overlap, not the point.")

    if args.md:
        args.md.parent.mkdir(parents=True, exist_ok=True)
        args.md.write_text("```\n" + "\n".join(R.lines) + "\n```\n", encoding="utf-8")
        print(f"\n  written to {args.md}")


if __name__ == "__main__":
    main()
