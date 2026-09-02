"""Build docs/PROJECT_REPORT.md and a self-contained docs/PROJECT_REPORT.html.

Supersedes docs/TECHNICAL_REPORT.md, which is left in place.

Reuses, rather than duplicating:
  - make_supervisor_brief : pick / Row / load / REGEN   (the sourcing rule)
  - make_technical_report : gather() and the 9 data figures
  - report_text           : the glossary and the markdown -> HTML renderer
  - figures/mermaid/*.mmd : the 8 architecture diagrams, rendered by mermaid-cli

    ./venv/Scripts/python.exe experiments/make_project_report.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from experiments.make_supervisor_brief import REGEN, load
import experiments.make_technical_report as tr
from experiments.report_text import build_html
from experiments.project_text import build as build_project

# Architecture diagrams, rendered from README Part 1 Mermaid sources.
# Every one was factually corrected first: GPT-4o-mini -> gemini via OpenRouter,
# the three never-ingested corpus filters marked NOT INGESTED, and the refusal
# gate marked as never having fired. See README section 2.7.
MERMAID = [
    ("M1_high_level",
     "M1 — The whole system. A question enters at the left and a cited answer "
     "with a PDF leaves at the right. Pink boxes use a language model; blue "
     "boxes are fixed rules or database search."),
    ("M2_intake_agent",
     "M2 — The intake stage. It reads the question and extracts structure: what "
     "kind of legal problem this is, and which facts are missing."),
    ("M3_router_agent",
     "M3 — The routing stage, which decides which law book to search by matching "
     "words against a fixed table. Three branches point at books that were never "
     "ingested and therefore match nothing; the search then silently falls back "
     "to searching everything."),
    ("M4_retrieval_pipeline",
     "M4 — The seven retrieval steps. Every headline finding in this report is "
     "measured here. Note steps 4 and 5: reranking reorders the fifteen results, "
     "and the adaptive filter discards the weakest, which is why a recall figure "
     "must always name which of the three stages produced it."),
    ("M5_answer_agent",
     "M5 — The answer stage. The refusal gate is real code, but it has never "
     "triggered in 859 recorded queries, so in practice every question is "
     "answered."),
    ("M6_confidence",
     "M6 — How confidence is computed: three signals combined by fixed weights. "
     "Finding 5.4 shows this combination performs worse than one of its own "
     "inputs used alone."),
    ("M7_ingestion",
     "M7 — Ingestion, run once. PDFs become text, text becomes passages, "
     "passages become vectors, vectors go into the database."),
    ("M8_sequence",
     "M8 — The same path in time order, showing which component talks to which "
     "and in what sequence."),
]


def main() -> None:
    print("data figures...")
    g = tr.gather()
    tr.f1_pipeline(g); tr.f2_ipc_bns(g); tr.f3_inversion(g); tr.f4_self_naming(g)
    tr.f5_funnel(g); tr.f6_ablation(g); tr.f7_reliability(g)
    tr.f8_risk_coverage(g); tr.f9_ceiling(g)

    print("architecture diagrams...")
    figs = list(tr.FIGS)
    for fid, cap in MERMAID:
        png = ROOT / "figures" / f"{fid}.png"
        if not png.exists():
            tr.DROPPED.append(f"{fid}: figures/{fid}.png absent — Mermaid render "
                              f"did not produce it; diagram omitted")
            print(f"  MISSING {fid}")
            continue
        figs.append((fid, png.name, cap))
        print(f"  {fid}  {png.name}")

    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                         capture_output=True, text=True).stdout.strip()
    total = sum(len(load(f)) for f in REGEN)

    md = build_project(g, figs, sha, total, tr.DROPPED)
    (ROOT / "docs" / "PROJECT_REPORT.md").write_text(md, encoding="utf-8")
    (ROOT / "docs" / "PROJECT_REPORT.html").write_text(
        build_html(md, figs, sha), encoding="utf-8")

    print(f"\n{len(g)} figures sourced · {len(figs)} images · {total} result rows")
    print(f"DROPPED: {len(tr.DROPPED)}")
    for d in tr.DROPPED:
        print("  -", d)


if __name__ == "__main__":
    main()
