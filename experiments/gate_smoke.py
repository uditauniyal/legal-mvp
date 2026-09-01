"""GATE smoke test -- three numbers before Wave 2 is allowed to start.

Per docs/PLAN.md section 5. Computes from existing logs only; zero API calls.
The corpus-filter ablation (number 1a) is run separately by
scripts/ablate_filter.py -- see results/ablation_rerun_2026-09-01.txt.

    ./venv/Scripts/python.exe experiments/gate_smoke.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from core.citations import extract_provisions
from experiments.metrics_lib import (
    DEFINITIONS, N_BOOT, SEED, STAGES, auroc, auroc_bootstrap_ci,
    correctness_label, load_logs, load_stages, normalise_section,
    paired_bootstrap_auroc_diff, same_section, wilson,
)

ROOT = Path(__file__).resolve().parents[1]


def numbering_scheme_map() -> dict[str, str]:
    """query_id -> numbering_scheme, from the query sets (read-only)."""
    out = {}
    for f in (ROOT / "eval").glob("*_queryset.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("query_id"):
                    out[r["query_id"]] = r.get("numbering_scheme")
    return out


def answer_texts() -> dict[str, str]:
    """req_id -> answer.answer_text, straight from the run logs (read-only).

    Needed because load_logs() carries verifier.cited, which was produced by
    the PRE-FIX citation parser. To ask whether Wave 1's S3 fix changes the
    'cited' correctness definition, the answers must be re-parsed.
    """
    out = {}
    for f in (ROOT / "runs").rglob("queries.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("req_id"):
                out[r["req_id"]] = ((r.get("answer") or {}).get("answer_text")) or ""
    return out


def reparsed_cited(text: str) -> list[str]:
    """Sections cited in an answer, under the POST-FIX parser."""
    out = []
    for p in extract_provisions(text):
        if p.kind == "section":
            out.append(f"{p.statute or ''} {p.number}".strip())
    return out


def main() -> None:
    df = load_logs()
    stages = load_stages()
    scheme = numbering_scheme_map()
    df["numbering_scheme"] = df["query_id"].map(scheme)

    labelled = df[df["expected_sections"].map(len) > 0].copy()
    print(f"rows: {len(df)} loaded ({df.attrs['rows_dropped']} dupes dropped), "
          f"{len(labelled)} with a gold label\n")

    # ---------------------------------------------------------------- 1b
    print("=" * 78)
    print("1b. GOLD-SECTION RECALL on the paired set, split by naming scheme")
    print("    CORPUS FILTER ON -- this is the deployed pipeline, and is a")
    print("    DIFFERENT question from the 97.0/51.5 ablation (filter OFF).")
    print("=" * 78)
    paired = labelled[labelled["query_set"] == "paired_recodification"]
    rows_1b = []
    for stage in STAGES:
        for sch in ("IPC", "BNS"):
            sub = paired[paired["numbering_scheme"] == sch]
            if not len(sub):
                continue
            labs = [correctness_label({**r, "_stage": stage}, "retrieved@k", k=15,
                                      stages=stages) for _, r in sub.iterrows()]
            k, n = sum(labs), len(labs)
            p, lo, hi = wilson(k, n)
            rows_1b.append((stage, sch, k, n, p, lo, hi))
            print(f"  {stage:<14} {sch}  {k:>3}/{n:<3}  "
                  f"{p*100:5.1f}% [{lo*100:.1f}, {hi*100:.1f}]")
    print()

    # ---------------------------------------------------------------- 2
    print("=" * 78)
    print("2. POSITIVE COUNTS under every correctness definition")
    print("=" * 78)
    texts = answer_texts()
    labelled["cited_new"] = labelled["req_id"].map(
        lambda r: reparsed_cited(texts.get(r, "")))

    counts = {}
    for stage in STAGES:
        labs = [correctness_label({**r, "_stage": stage}, "retrieved@k", k=15,
                                  stages=stages) for _, r in labelled.iterrows()]
        counts[f"retrieved@15 ({stage})"] = sum(labs)
    counts["cited (logged, PRE-fix parser)"] = sum(
        correctness_label(r, "cited") for _, r in labelled.iterrows())
    counts["cited (re-parsed, POST-fix parser)"] = sum(
        int(any(same_section(g, c) for g in r["expected_sections"]
                for c in r["cited_new"]))
        for _, r in labelled.iterrows())
    counts["grounded"] = sum(
        correctness_label(r, "grounded") for _, r in labelled.iterrows())

    n = len(labelled)
    for name, k in counts.items():
        p, lo, hi = wilson(k, n)
        print(f"  {name:<38} {k:>4}/{n}  {p*100:5.1f}% [{lo*100:.1f}, {hi*100:.1f}]")
    print()

    # ---------------------------------------------------------------- 3
    print("=" * 78)
    print("3. COMPOSITE vs RAW MAX SCORE -- paired bootstrap on the difference")
    print("=" * 78)
    rows_3 = []
    for defn, labs in [
        ("grounded", [correctness_label(r, "grounded") for _, r in labelled.iterrows()]),
        ("retrieved@15 (raw_15)",
         [correctness_label({**r, "_stage": "raw_15"}, "retrieved@k", k=15, stages=stages)
          for _, r in labelled.iterrows()]),
        ("cited (post-fix)",
         [int(any(same_section(g, c) for g in r["expected_sections"] for c in r["cited_new"]))
          for _, r in labelled.iterrows()]),
    ]:
        sub = labelled.copy()
        sub["lab"] = labs
        ok = sub[sub["composite"].notna() & sub["max_score"].notna()]
        y = ok["lab"].to_numpy()
        if len(set(y)) < 2:
            print(f"  {defn:<24} SKIPPED -- only one class present")
            continue
        a = ok["composite"].to_numpy()
        b = ok["max_score"].to_numpy()
        ca, calo, cahi = auroc_bootstrap_ci(a, y, n_boot=N_BOOT, seed=SEED)
        cb, cblo, cbhi = auroc_bootstrap_ci(b, y, n_boot=N_BOOT, seed=SEED)
        d = paired_bootstrap_auroc_diff(a, b, y, n_boot=N_BOOT, seed=SEED)
        rows_3.append((defn, len(y), int(y.sum()), ca, calo, cahi, cb, cblo, cbhi, d))
        print(f"  {defn}   n={len(y)}  positives={int(y.sum())}")
        print(f"    composite AUROC  {ca:.3f} [{calo:.3f}, {cahi:.3f}]")
        print(f"    max_score AUROC  {cb:.3f} [{cblo:.3f}, {cbhi:.3f}]")
        print(f"    paired diff (composite - max_score)  {d['diff']:+.3f} "
              f"[{d['ci_lo']:+.3f}, {d['ci_hi']:+.3f}]  p={d['p_two_sided']:.4f}")
        verdict = ("WORSE (interval excludes 0)" if d["ci_hi"] < 0 else
                   "BETTER (interval excludes 0)" if d["ci_lo"] > 0 else
                   "NO BETTER THAN -- interval contains 0, 'worse' is NOT supported")
        print(f"    supported claim: {verdict}\n")

    out = ROOT / "results" / "gate_smoke.json"
    out.write_text(json.dumps({
        "rows_1b": rows_1b, "counts_2": counts,
        "rows_3": [[*r[:9], r[9]] for r in rows_3],
        "n_labelled": n, "seed": SEED, "n_boot": N_BOOT,
    }, indent=2, default=str), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
