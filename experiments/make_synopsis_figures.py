"""Two new figures for the department synopsis.

Fig 1 — the pipeline as it ACTUALLY executes: six unconditional stages plus two
        that run only when the intervention flag is set. Verified against app.py,
        including the fact that the date resolver runs AFTER the router.
Fig 2 — the two-correct-answers problem, which is the research question.

The other four synopsis figures are reused unchanged from figures/.

    ./venv/Scripts/python.exe experiments/make_synopsis_figures.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "figures"
FIG.mkdir(exist_ok=True)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LLM = "#fce4e4"       # stages that call a language model
RULE = "#e3ecf7"      # deterministic stages
COND = "#fff6d8"      # conditional stages (the treatment)
EDGE = "#4a4a4a"

plt.rcParams.update({"font.family": "serif", "font.size": 9,
                     "figure.dpi": 200, "savefig.bbox": "tight"})


def box(ax, x, y, w, h, lines, face, fs=8.4):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                                boxstyle="round,pad=0.01,rounding_size=0.02",
                                facecolor=face, edgecolor=EDGE, linewidth=1.0))
    n = len(lines)
    for i, ln in enumerate(lines):
        ax.text(x + w / 2, y + h - (h / (n + 1)) * (i + 1), ln,
                ha="center", va="center", fontsize=fs,
                fontweight="bold" if i == 0 else "normal")


def arrow(ax, x1, y1, x2, y2, dashed=False):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                 mutation_scale=11, color=EDGE, linewidth=1.0,
                                 linestyle="--" if dashed else "-",
                                 shrinkA=0, shrinkB=0))


def figure_1_pipeline():
    fig, ax = plt.subplots(figsize=(10.0, 5.2))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 60)
    ax.axis("off")

    w, h = 20.0, 9.5
    r1, r2, r3 = 41, 24, 7

    # ---- row 1: intake, router, then the optional treatment --------------
    box(ax, 1, r1, w, h, ["1  Intake", "language model", "gives CaseContext"], LLM)
    arrow(ax, 21, r1 + h / 2, 24, r1 + h / 2)
    box(ax, 24, r1, w, h, ["2  Router", "regex rules", "gives QueryPlan"], RULE)

    ax.add_patch(FancyBboxPatch((47.5, r1 - 3.0), 44.5, h + 5.8,
                                boxstyle="round,pad=0.01,rounding_size=0.02",
                                facecolor="none", edgecolor="#c9a227",
                                linewidth=1.3, linestyle="--"))
    ax.text(69.7, r1 + h + 3.9, "TREATMENT CONDITION  -  off by default",
            ha="center", fontsize=8.2, color="#8a6d00", fontweight="bold")
    arrow(ax, 44, r1 + h / 2, 49, r1 + h / 2, dashed=True)
    box(ax, 49, r1, w, h, ["2.5a  Date resolver", "regex rules",
                           "gives legal era"], COND)
    arrow(ax, 69, r1 + h / 2, 71, r1 + h / 2)
    box(ax, 71, r1, w, h, ["2.5b  Statute mapper", "lookup table",
                           "maps across codes"], COND)

    # ---- row 2: retrieval -------------------------------------------------
    arrow(ax, 81, r1, 81, r2 + h + 1.0)
    arrow(ax, 34, r1, 34, r2 + h + 1.0, dashed=True)
    box(ax, 24, r2, 67, h,
        ["3  Retrieval  -  Qdrant vector search, cosine similarity, top 15",
         "embed  |  search  |  fallback  |  entity rerank  |  adaptive filter  "
         "|  confidence score"], RULE)

    # ---- row 3 ------------------------------------------------------------
    # Retrieval feeds ANSWER, not the verifier. The verifier runs last, on the
    # answer's citations. Drawn down the left so the order is unambiguous.
    ax.add_patch(FancyArrowPatch((28, r2), (11, r3 + h),
                                 arrowstyle="-|>", mutation_scale=11,
                                 color=EDGE, linewidth=1.0,
                                 connectionstyle="angle,angleA=-90,angleB=180,rad=3",
                                 shrinkA=0, shrinkB=0))
    ax.text(20.0, r2 - 5.0, "retrieved passages", ha="center",
            fontsize=7.8, color=EDGE, style="italic")
    box(ax, 1, r3, w, h, ["4  Answer", "language model", "writes citations"], LLM)
    box(ax, 24, r3, w, h, ["5  Reporter", "fpdf2", "advisory PDF"], RULE)
    box(ax, 47, r3, w, h, ["6  Verifier", "regex rules", "audits citations"], RULE)
    box(ax, 70, r3, w, h, ["Run record", "85 fields", "written to disk"], RULE)
    arrow(ax, 21, r3 + h / 2, 24, r3 + h / 2)
    arrow(ax, 44, r3 + h / 2, 47, r3 + h / 2)
    arrow(ax, 67, r3 + h / 2, 70, r3 + h / 2)

    # ---- legend -----------------------------------------------------------
    for i, (c, lab) in enumerate([
            (LLM, "language model  (2 of 8 stages)"),
            (RULE, "deterministic rules / vector search"),
            (COND, "conditional - evaluated as a treatment")]):
        x = 1 + i * 33
        ax.add_patch(FancyBboxPatch((x, 0.4), 3.0, 3.0,
                                    boxstyle="round,pad=0.005,rounding_size=0.01",
                                    facecolor=c, edgecolor=EDGE, linewidth=0.9))
        ax.text(x + 4.2, 1.9, lab, va="center", fontsize=8.0)

    fig.savefig(FIG / "SYN1_pipeline.png", facecolor="white")
    plt.close(fig)
    print("  SYN1_pipeline.png")


def figure_2_problem():
    fig, ax = plt.subplots(figsize=(9.0, 3.6))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 48)
    ax.axis("off")

    ax.text(50, 45, "The same words. Two correct answers. Only the date decides.",
            ha="center", fontsize=10.2, fontweight="bold")

    ax.add_patch(FancyBboxPatch((28, 30), 44, 8.0,
                                boxstyle="round,pad=0.01,rounding_size=0.02",
                                facecolor="#ffffff", edgecolor=EDGE, linewidth=1.1))
    ax.text(50, 35.6, '"my husband beats me"', ha="center", fontsize=9.4,
            fontstyle="italic")
    ax.text(50, 32.2, "identical query text", ha="center", fontsize=8.2)

    arrow(ax, 42, 30, 28, 21.5)
    arrow(ax, 58, 30, 72, 21.5)
    ax.text(15.0, 25.6, "conduct in March 2023", ha="center", fontsize=8.0,
            style="italic", color=EDGE)
    ax.text(85.0, 25.6, "conduct last month", ha="center", fontsize=8.0,
            style="italic", color=EDGE)

    box(ax, 4, 11, 42, 10.5,
        ["IPC Section 498A", "Indian Penal Code, 1860",
         "repealed 1 July 2024, still governs", "conduct from before that date"],
        "#fdeaea", fs=8.2)
    box(ax, 54, 11, 42, 10.5,
        ["BNS Section 85", "Bharatiya Nyaya Sanhita, 2023",
         "in force since 1 July 2024", ""], "#e8f4ea", fs=8.2)

    ax.text(50, 5.0,
            "A layperson does not know the Indian Penal Code was replaced, and "
            "will not supply a date.",
            ha="center", fontsize=8.4, style="italic", color="#444444")
    ax.text(50, 1.8,
            "The section number they are given is the one that goes on their "
            "police complaint.",
            ha="center", fontsize=8.4, style="italic", color="#444444")

    fig.savefig(FIG / "SYN2_problem.png", facecolor="white")
    plt.close(fig)
    print("  SYN2_problem.png")


if __name__ == "__main__":
    print("synopsis figures...")
    figure_1_pipeline()
    figure_2_problem()
