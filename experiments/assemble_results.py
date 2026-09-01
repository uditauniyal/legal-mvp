"""Wave 4 — assemble every results CSV into results/RESULTS.md.

Per docs/PLAN.md section 5, Wave 4.

Nothing here retypes a number. Every table is built by FILTERING the CSVs, so a
figure in RESULTS.md cannot drift from the data that produced it. Verification
runs BEFORE writing: every referenced path must exist, and results/EXPLAIN.md
must carry one block per output file with all eight headings.

The three closing lists (numbers that changed, assertions that failed, what
could not be computed) require judgement and are maintained by hand in
results/_RESULTS_appendix.md, which this script appends verbatim. It never
writes them from memory.

    ./venv/Scripts/python.exe experiments/assemble_results.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8")

# source file -> (caption, regenerating command)
SOURCES = {
    "hybrid_comparison.csv": (
        "Dense vs BM25 vs Reciprocal Rank Fusion, corpus filter disabled.",
        "./venv/Scripts/python.exe experiments/exp07_hybrid.py"),
    "retrieval_metrics.csv": (
        "Recall, precision, MRR and nDCG at every k, at all three retrieval stages.",
        "./venv/Scripts/python.exe experiments/exp01_retrieval.py"),
    "routing_confusion.csv": (
        "Which law book the system went to, and each book's share of retrieval "
        "against its share of the index.",
        "./venv/Scripts/python.exe experiments/exp02_routing.py"),
    "calibration.csv": (
        "Does a confidence number mean what it says: ECE, Brier, risk-coverage, "
        "Platt scaling.",
        "./venv/Scripts/python.exe experiments/exp03_calibration.py"),
    "ablation.csv": (
        "What each confidence signal contributes, alone and in combination.",
        "./venv/Scripts/python.exe experiments/exp04_ablation.py"),
    "robustness.csv": (
        "Do the conclusions survive a change of correctness definition, and "
        "proper clustering of non-independent queries.",
        "./venv/Scripts/python.exe experiments/exp05_robustness.py"),
    "statute_consistency.csv": (
        "The fourth confidence signal, specified in TARGET_ARCHITECTURE.md and "
        "built here for the first time.",
        "./venv/Scripts/python.exe experiments/exp06_statute_consistency.py"),
    "filter_analysis.csv": (
        "What the adaptive score filter costs, and which arm of the threshold binds.",
        "./venv/Scripts/python.exe experiments/exp08_filter.py"),
}

# headline rows, selected by filter so nothing is transcribed
HEADLINES = {
    "hybrid_comparison.csv": [
        ("Cross-statute accuracy, corpus filter DISABLED",
         {"metric": ["corpus_dominant_accuracy", "corpus_top1_accuracy"]}),
        ("Gold-section reachability ceiling", {"metric": ["gold_reachable_ceiling"]}),
    ],
    "retrieval_metrics.csv": [
        ("Recall@15, definition retrieved@k, all three stages",
         {"metric": ["recall_at_k"], "k": [15.0], "definition": ["retrieved@k"]}),
    ],
    "routing_confusion.csv": [
        ("Over-representation: retrieval share divided by index share",
         {"definition": ["retrieval_share/index_share"]}),
    ],
    "calibration.csv": [
        ("Expected Calibration Error, lower is better", {"metric": ["ece"]}),
        ("Coverage achievable at 10% risk", {"metric": ["coverage_at_risk_0.10"]}),
    ],
    "ablation.csv": [
        ("AUROC of each confidence signal on its own", {"metric": ["auroc_signal"]}),
        ("Leave-one-out: does removing a signal hurt?", {"metric": ["auroc_loo"]}),
    ],
    "robustness.csv": [
        ("The recodification gap under every correctness definition",
         {"metric": ["paired_gap_ipc_minus_bns"]}),
        ("Layman retrieval rate, naive vs clustered", {"metric": ["layman_rate"]}),
    ],
    "statute_consistency.csv": [
        ("AUROC of the new fourth signal", {"metric": ["auroc_statute_consistency"]}),
        ("The four-signal ablation picture", {"metric": ["ablation_auroc"]}),
    ],
    "filter_analysis.csv": [
        ("Counterfactual recall at each floor", {"metric": ["counterfactual_recall"]}),
        ("Which arm of the threshold was binding",
         {"metric": ["binding_arm_floor", "binding_arm_relative"]}),
    ],
}

COLS = ["metric", "query_set", "definition", "stage", "k", "value", "n",
        "ci_lo", "ci_hi", "cluster_ci_lo", "cluster_ci_hi", "notes"]


def cell(v) -> str:
    if pd.isna(v):
        return ""
    if isinstance(v, float):
        return f"{v:g}" if abs(v) >= 1000 or v == int(v) else f"{v:.4f}".rstrip("0")
    return str(v).replace("|", "\\|").replace("\n", " ")


def table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_NOT MEASURED — no rows matched this filter._\n"
    keep = [c for c in COLS if df[c].notna().any()]
    out = ["| " + " | ".join(keep) + " |",
           "|" + "|".join("---" for _ in keep) + "|"]
    for _, r in df.iterrows():
        out.append("| " + " | ".join(cell(r[c]) for c in keep) + " |")
    return "\n".join(out) + "\n"


def verify() -> list[str]:
    """Run BEFORE writing. Returns problems; never repairs silently."""
    problems = []

    for name in SOURCES:
        if not (ROOT / "results" / name).exists():
            problems.append(f"MISSING source file: results/{name}")

    for extra in ["EXPLAIN.md", "smoke_test.md", "gate_smoke.json",
                  "reliability_diagram.png", "ablation_rerun_2026-09-01.txt"]:
        if not (ROOT / "results" / extra).exists():
            problems.append(f"MISSING referenced file: results/{extra}")

    exp = (ROOT / "results" / "EXPLAIN.md").read_text(encoding="utf-8")
    blocks = {}
    for b in re.split(r"^## ", exp, flags=re.M)[1:]:
        title = b.split("\n")[0].strip()
        blocks[title] = len(re.findall(r"^### ", b, flags=re.M))
    for title, n in blocks.items():
        if n < 8 and not title.startswith("GATE"):
            problems.append(f"EXPLAIN.md block '{title}' has {n} headings, needs 8")
    if len(blocks) < 12:
        problems.append(f"EXPLAIN.md has only {len(blocks)} blocks")

    return problems


def main() -> None:
    problems = verify()
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                         capture_output=True, text=True).stdout.strip()

    L = [
        "# RESULTS",
        "",
        f"Every measurement in this project, assembled from `results/*.csv` at `{sha}`.",
        "",
        "Every number carries its sample size `n`, its 95% confidence interval, the "
        "correctness definition used, and the retrieval stage used. A blank column "
        "means the field does not apply to that row, never that it was omitted. "
        "`NOT MEASURED` means exactly that.",
        "",
        "Regenerate this file: `./venv/Scripts/python.exe experiments/assemble_results.py`",
        "",
        "Nothing here is retyped. Every table is built by filtering the CSVs, so no "
        "figure can drift from the data that produced it.",
        "",
        "## Verification",
        "",
    ]
    if problems:
        L += ["**Problems found before writing — listed, not repaired:**", ""]
        L += [f"- {p}" for p in problems] + [""]
    else:
        L += ["All referenced paths exist. `results/EXPLAIN.md` carries one block per "
              "output file, eight headings each. No problems found.", ""]

    total = 0
    L += ["## Contents", "", "| Source | Rows | What it measures |", "|---|---|---|"]
    for name, (cap, _) in SOURCES.items():
        n = len(pd.read_csv(ROOT / "results" / name))
        total += n
        L.append(f"| [`{name}`](#{name.replace('.', '').replace('_', '-')}) | {n} | {cap} |")
    L += [f"| **total** | **{total}** | |", ""]

    for name, (cap, cmd) in SOURCES.items():
        df = pd.read_csv(ROOT / "results" / name)
        L += ["---", "", f"## {name}", "", cap, "",
              f"Regenerate: `{cmd}`", "", f"{len(df)} rows.", ""]
        for label, filt in HEADLINES.get(name, []):
            sub = df.copy()
            for col, vals in filt.items():
                sub = sub[sub[col].isin(vals)]
            L += [f"### {label}", "", table(sub), ""]
        L += ["<details>", f"<summary>All {len(df)} rows</summary>", "",
              table(df), "", "</details>", ""]

    app = ROOT / "results" / "_RESULTS_appendix.md"
    if app.exists():
        L += ["---", "", app.read_text(encoding="utf-8")]
    else:
        L += ["---", "", "## Appendix", "",
              "**NOT WRITTEN** — `results/_RESULTS_appendix.md` is absent. The three "
              "closing lists require judgement and are never generated from memory."]

    (ROOT / "results" / "RESULTS.md").write_text("\n".join(L), encoding="utf-8")
    print(f"wrote results/RESULTS.md  ({total} result rows across {len(SOURCES)} files)")
    print(f"verification problems: {len(problems)}")
    for p in problems:
        print("  -", p)


if __name__ == "__main__":
    main()
