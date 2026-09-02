"""Build docs/PROJECT_REPORT.md, .html and .pdf.

Supersedes docs/TECHNICAL_REPORT.md, which is left in place.

Reuses, rather than duplicating:
  - make_supervisor_brief : pick / Row / load / REGEN   (the sourcing rule)
  - make_technical_report : gather() and the 9 data figures
  - report_text           : the glossary and the markdown -> HTML renderer
  - figures/mermaid/*.mmd : the 8 architecture diagrams, rendered by mermaid-cli

The PDF is printed from the self-contained HTML by headless Chrome, so it
inherits the print stylesheet rather than being laid out a second time.

    ./venv/Scripts/python.exe experiments/make_project_report.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from experiments.make_supervisor_brief import REGEN, load, pick
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
     "Finding 6.4 shows this combination performs worse than one of its own "
     "inputs used alone."),
    ("M7_ingestion",
     "M7 — Ingestion, run once. PDFs become text, text becomes passages, "
     "passages become vectors, vectors go into the database."),
    ("M8a_sequence_in",
     "M8a — The same path in time order, first half: the question arrives, is "
     "triaged, routed, embedded, and searched against the database. Split in two "
     "so the labels stay legible at page width."),
    ("M8b_sequence_out",
     "M8b — Second half: retrieved passages become a cited answer and a PDF, "
     "which return to the user."),
]

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def extra_gather(g):
    """The two numbers behind the architecture change, sourced like all others."""
    g["rec_dated_baseline"] = pick(
        "retrieval_metrics.csv", metric="recall_at_k_baseline_rows", k="15.0",
        definition="retrieved@k", stage="raw_15",
        query_set="paired_dated_conflict")
    g["rec_dated_interv"] = pick(
        "retrieval_metrics.csv", metric="recall_at_k_both_rows", k="15.0",
        definition="retrieved@k", stage="raw_15",
        query_set="paired_dated_conflict")
    return g


def f10_intervention(g):
    """What the date resolver and statute mapper actually bought."""
    fig, ax = plt.subplots(figsize=(6.9, 2.9))
    items = [
        ("Before\n(router only)", g["rec_dated_baseline"], tr.CRED),
        ("After\n(+ date resolver\n+ statute mapper)", g["rec_dated_interv"],
         tr.CGREEN),
    ]
    ys = [1, 0]
    for yy, (lab, r, col) in zip(ys, items):
        lo, hi = float(r.r["ci_lo"]), float(r.r["ci_hi"])
        ax.barh(yy, r.v, height=0.45, color=col, edgecolor=tr.INK, lw=0.7)
        ax.errorbar(r.v, yy, xerr=[[r.v - lo], [hi - r.v]], fmt="none",
                    ecolor=tr.INK, capsize=3, lw=1.1)
        ax.text(r.v + 0.02, yy, f"{r.v * 100:.1f}%   (n={r.n})", va="center",
                fontsize=8.5)
    ax.set_yticks(ys)
    ax.set_yticklabels([i[0] for i in items], fontsize=8.5)
    ax.set_xlim(0, 1.0)
    ax.set_xlabel("share of questions where the correct section was retrieved")
    ax.xaxis.set_major_formatter(lambda v, p: f"{v * 100:.0f}%")
    ax.grid(axis="x", color=tr.GRID, lw=0.6)
    ax.set_axisbelow(True)
    ax.set_title("Effect of the architecture change, on questions where the named "
                 "code\nand the date of the conduct disagree   (95% Wilson CI)",
                 fontsize=9.5)
    tr.save(fig, "F10_intervention",
            "F10 — Adding a date resolver and a statute mapper more than doubled "
            "retrieval of the correct section on the hard case: where the question "
            "names one code but the conduct falls under the other. The two "
            "intervals do not overlap, so the gain is larger than sampling noise "
            "could explain.")


def to_pdf(html_path: Path, pdf_path: Path) -> bool:
    """Print the self-contained HTML to PDF with headless Chrome."""
    browser = next((c for c in CHROME_CANDIDATES if Path(c).exists()), None)
    if not browser:
        return False
    if pdf_path.exists():
        pdf_path.unlink()
    subprocess.run([browser, "--headless", "--disable-gpu", "--no-sandbox",
                    "--no-pdf-header-footer", f"--print-to-pdf={pdf_path}",
                    html_path.as_uri()],
                   capture_output=True, timeout=300)
    return pdf_path.exists()


def main() -> None:
    print("data figures...")
    g = extra_gather(tr.gather())
    tr.f1_pipeline(g); tr.f2_ipc_bns(g); tr.f3_inversion(g); tr.f4_self_naming(g)
    tr.f5_funnel(g); tr.f6_ablation(g); tr.f7_reliability(g)
    tr.f8_risk_coverage(g); tr.f9_ceiling(g); f10_intervention(g)

    print("architecture diagrams...")
    figs = list(tr.FIGS)
    for fid, cap in MERMAID:
        png = ROOT / "figures" / f"{fid}.png"
        if not png.exists():
            tr.DROPPED.append(f"{fid}: figures/{fid}.png absent — the Mermaid "
                              f"render did not produce it; diagram omitted")
            print(f"  MISSING {fid}")
            continue
        figs.append((fid, png.name, cap))
        print(f"  {fid}  {png.name}")

    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                         capture_output=True, text=True).stdout.strip()
    total = sum(len(load(f)) for f in REGEN)

    md = build_project(g, figs, sha, total, tr.DROPPED)
    (ROOT / "docs" / "PROJECT_REPORT.md").write_text(md, encoding="utf-8")
    html = ROOT / "docs" / "PROJECT_REPORT.html"
    html.write_text(build_html(md, figs, sha), encoding="utf-8")

    pdf = ROOT / "docs" / "PROJECT_REPORT.pdf"
    if to_pdf(html, pdf):
        import fitz
        print(f"\n  PDF: {pdf.name} — {fitz.open(pdf).page_count} pages, "
              f"{pdf.stat().st_size // 1024} KB")
    else:
        tr.DROPPED.append("PDF: no Chrome or Edge executable found; HTML only")

    print(f"\n{len(g)} figures sourced · {len(figs)} images · {total} result rows")
    print(f"DROPPED: {len(tr.DROPPED)}")
    for d in tr.DROPPED:
        print("  -", d)


if __name__ == "__main__":
    main()
