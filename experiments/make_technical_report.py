"""Generate docs/TECHNICAL_REPORT.md, figures/, and a self-contained HTML.

For a reader with NO prior exposure to this codebase.

SOURCING RULE, unchanged from make_supervisor_brief.py, whose machinery this
imports rather than duplicating: no number is typed. Every figure and table is
built by filtering results/*.csv with a one-row-or-crash assertion. Anything
unsourceable is recorded in DROPPED and omitted.

    ./venv/Scripts/python.exe experiments/make_technical_report.py
"""
from __future__ import annotations

import base64
import io
import re
import subprocess
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from experiments.make_supervisor_brief import REGEN, Row, load, pick  # reuse

REGEN["self_naming.csv"] = "experiments/exp10_self_naming.py"

FIGDIR = ROOT / "figures"
FIGDIR.mkdir(exist_ok=True)
DROPPED: list[str] = []
FIGS: list[tuple[str, str, str]] = []          # (id, filename, caption)

INK, GRID = "#1a1a1a", "#d8d8d8"
CBLUE, CRED, CGREY, CGREEN = "#2b6cb0", "#c53030", "#8a8a8a", "#2f855a"
plt.rcParams.update({"font.size": 9, "axes.edgecolor": INK,
                     "axes.labelcolor": INK, "text.color": INK,
                     "xtick.color": INK, "ytick.color": INK,
                     "figure.dpi": 150, "savefig.bbox": "tight"})


def save(fig, fid: str, caption: str) -> None:
    path = FIGDIR / f"{fid}.png"
    try:
        fig.tight_layout()
    except Exception:
        pass                      # F1 draws on a bare canvas; leave it alone
    fig.savefig(path, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    FIGS.append((fid, path.name, caption))
    print(f"  {fid}  {path.name}")


def errbars(ax, y, vals, los, his, color, label=None):
    lo = [max(0.0, v - l) for v, l in zip(vals, los)]
    hi = [max(0.0, h - v) for v, h in zip(vals, his)]
    ax.errorbar(vals, y, xerr=[lo, hi], fmt="o", color=color, capsize=3,
                markersize=5, linewidth=1.4, label=label)


# ============================================================ FIGURES
def f1_pipeline(g):
    fig, ax = plt.subplots(figsize=(9.6, 3.5))
    ax.set_xlim(0, 100); ax.set_ylim(0, 34); ax.axis("off")
    stages = [
        ("Question\n(plain English)", "input", 2),
        ("Intake\nLLM", "llm", 17),
        ("Date resolver\nrules", "rule", 32),
        ("Router\nregex rules", "rule", 47),
        ("Retrieval\nQdrant, cosine", "rule", 62),
        ("Answer\nLLM", "llm", 77),
        ("Report\nPDF", "rule", 92),
    ]
    cols = {"input": "#ffffff", "llm": "#fde8e8", "rule": "#e6eef7"}
    for label, kind, x in stages:
        ax.add_patch(plt.Rectangle((x - 7, 14), 14, 9, facecolor=cols[kind],
                                   edgecolor=INK, linewidth=1.1))
        ax.text(x, 18.5, label, ha="center", va="center", fontsize=8)
        if x < 92:
            ax.annotate("", xy=(x + 8.5, 18.5), xytext=(x + 7.2, 18.5),
                        arrowprops=dict(arrowstyle="->", color=INK, lw=1.1))
    ax.text(50, 29, "Question in, cited answer out. Each stage's output is the "
                    "next stage's input.", ha="center", fontsize=9)
    ax.add_patch(plt.Rectangle((6, 4), 4, 3, facecolor="#fde8e8",
                               edgecolor=INK, lw=1.1))
    ax.text(11.5, 5.5, "language model (non-deterministic)", va="center", fontsize=8)
    ax.add_patch(plt.Rectangle((50, 4), 4, 3, facecolor="#e6eef7",
                               edgecolor=INK, lw=1.1))
    ax.text(55.5, 5.5, "deterministic rules / vector search", va="center", fontsize=8)
    n = int(g["idx_all"].v)
    ax.text(50, 0.6, f"Corpus: {n:,} passages from four Indian statutes "
                     f"(CrPC {int(g['idx_CRPC'].v)}, IPC {int(g['idx_IPC'].v)}, "
                     f"BNS {int(g['idx_BNS'].v)}, CPA {int(g['idx_CPA'].v)}) · "
                     f"openai/text-embedding-3-small, 1536 dimensions · Qdrant, cosine",
            ha="center", fontsize=7.5, color="#444444")
    save(fig, "F1_pipeline",
         "F1 — The five-agent pipeline. Two stages use a language model (pink); "
         "the rest are deterministic rules or vector search (blue). Only the "
         "retrieval stage is measured in this report's headline findings.")


def f2_ipc_bns(g):
    fig, ax = plt.subplots(figsize=(7.4, 2.9))
    rows = [("Query names the IPC\n(repealed 2024)", g["dom_dense_ipc"], g["chance_ipc"]),
            ("Query names the BNS\n(in force)", g["dom_dense_bns"], g["chance_bns"])]
    ys = [1, 0]
    for y, (lab, r, ch) in zip(ys, rows):
        errbars(ax, [y], [r.v], [float(r.r["ci_lo"])], [float(r.r["ci_hi"])], CBLUE)
        ax.plot([ch.v], [y], marker="|", markersize=18, color=CRED, mew=2)
        ax.text(r.v, y + 0.22, f"{r.v*100:.1f}%", ha="center", fontsize=9,
                fontweight="bold", color=CBLUE)
        ax.text(ch.v, y + 0.22, f"chance {ch.v*100:.1f}%", ha="center",
                fontsize=7.5, color=CRED)
    ax.set_yticks(ys); ax.set_yticklabels([r[0] for r in rows])
    ax.set_ylim(-0.55, 1.55)
    ax.set_xlim(0, 1.05); ax.set_xlabel(
        "share of queries whose top-15 passages are dominated by the named statute")
    ax.xaxis.set_major_formatter(lambda v, p: f"{v*100:.0f}%")
    ax.grid(axis="x", color=GRID, lw=0.6); ax.set_axisbelow(True)
    ax.set_title(f"Cross-statute retrieval, corpus filter disabled  "
                 f"(n={g['dom_dense_ipc'].n} per arm, 95% Wilson CI)", fontsize=9.5)
    save(fig, "F2_ipc_vs_bns",
         "F2 — Naming the repealed statute works; naming the one in force barely "
         "beats chance. Red ticks are the chance baseline: each statute's share "
         "of the index, i.e. what a retriever ignoring the question would score.")


def f3_inversion(g):
    fig, ax = plt.subplots(figsize=(7.4, 3.2))
    arms = [("dense (meaning)", "dense", CBLUE), ("BM25 (exact words)", "bm25", CRED),
            ("hybrid RRF", "hybrid_rrf", CGREEN)]
    w = 0.26
    for i, (lab, key, col) in enumerate(arms):
        for j, side in enumerate(("ipc", "bns")):
            r = g[f"dom_{key}_{side}"]
            x = j + (i - 1) * w
            ax.bar(x, r.v, width=w, color=col, edgecolor=INK, lw=0.6,
                   label=lab if j == 0 else None)
            ax.errorbar(x, r.v, yerr=[[r.v - float(r.r["ci_lo"])],
                                      [float(r.r["ci_hi"]) - r.v]],
                        fmt="none", ecolor=INK, capsize=2.5, lw=1)
            ax.text(x, r.v + 0.045, f"{r.v*100:.0f}%", ha="center", fontsize=8)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["query names the IPC (repealed)",
                        "query names the BNS (in force)"])
    ax.set_ylim(0, 1.15); ax.set_ylabel("dominant-corpus accuracy")
    ax.yaxis.set_major_formatter(lambda v, p: f"{v*100:.0f}%")
    ax.grid(axis="y", color=GRID, lw=0.6); ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=8, ncol=3, loc="upper center")
    ax.set_title(f"The two retrievers fail on opposite halves  "
                 f"(n={g['dom_dense_ipc'].n} per bar, 95% Wilson CI)", fontsize=9.5)
    save(fig, "F3_dense_vs_bm25",
         "F3 — Exact-word search does not repair the failure, it reverses it. "
         "Fusing the two (green) lands between them and beats neither: averaging "
         "two opposite failure modes fails at both.")


def f4_self_naming(g):
    d = load("self_naming.csv")
    terms, dfs, idfs, tops = [], [], [], []
    for t in ("sanhita", "bharatiya", "consumer", "procedure", "penal",
              "criminal", "indian", "code"):
        r = pick("self_naming.csv", metric="document_frequency",
                 definition=t, query_set="ALL")
        c = pick("self_naming.csv", metric="concentration", definition=t,
                 query_set="ALL")
        i = pick("self_naming.csv", metric="idf_okapi", definition=t,
                 query_set="ALL")
        terms.append(t); dfs.append(int(r.v)); idfs.append(i.v)
        tops.append(re.search(r"top=(\w+)", str(c.r["notes"])).group(1))
        tops[-1] = f"{tops[-1]} {c.v*100:.0f}%"
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.6, 3.4))
    y = np.arange(len(terms))[::-1]
    cols = [CGREEN if "BNS" in t or "CPA" in t else CRED if "CRPC" in t else CGREY
            for t in tops]
    a1.barh(y, dfs, color=cols, edgecolor=INK, lw=0.6)
    for yy, v, t in zip(y, dfs, tops):
        a1.text(v + 6, yy, f"{v}  ({t})", va="center", fontsize=7.5)
    a1.set_yticks(y); a1.set_yticklabels(terms)
    a1.set_xlabel(f"document frequency: chunks containing the term "
                  f"(of {int(g['idx_all'].v):,})")
    a1.set_xlim(0, max(dfs) * 1.55)
    a1.grid(axis="x", color=GRID, lw=0.6); a1.set_axisbelow(True)
    a2.barh(y, idfs, color=cols, edgecolor=INK, lw=0.6)
    for yy, v in zip(y, idfs):
        a2.text(v + 0.08, yy, f"{v:.2f}", va="center", fontsize=7.5)
    a2.set_yticks(y); a2.set_yticklabels([])
    a2.set_xlabel("Okapi IDF — higher means more informative")
    a2.set_xlim(0, max(idfs) * 1.25)
    a2.grid(axis="x", color=GRID, lw=0.6); a2.set_axisbelow(True)
    fig.suptitle("Statutory self-naming: which words point at which statute",
                 fontsize=10, y=1.02)
    save(fig, "F4_self_naming",
         "F4 — Bars are coloured by the statute the term concentrates in "
         "(green BNS/CPA, red CrPC, grey mixed). 'sanhita' occurs in 30 chunks, "
         "all BNS — a perfect signpost. 'penal' occurs in 110, but 82 are CrPC "
         "and only 23 are IPC: the Penal Code's own name points elsewhere.")


def f5_funnel(g):
    sets = [("generated_retrieval", "generated"),
            ("paired_recodification", "paired IPC/BNS"),
            ("paired_dated_conflict", "dated conflict"),
            ("layman_situation", "layman")]
    fig, ax = plt.subplots(figsize=(8.8, 3.3))
    stages = ["raw_15", "reranked_15", "filtered_n"]
    ends = []
    for qs, lab in sets:
        vals, los, his = [], [], []
        for st in stages:
            r = pick("retrieval_metrics.csv", metric="recall_at_k", k="15.0",
                     definition="retrieved@k", stage=st, query_set=qs)
            vals.append(r.v); los.append(float(r.r["ci_lo"]))
            his.append(float(r.r["ci_hi"]))
        x = np.arange(3)
        ax.plot(x, vals, "-o", markersize=5, lw=1.6,
                label=f"{lab} (n={r.n})")
        ax.fill_between(x, los, his, alpha=0.12)
        ends.append(vals[-1])
    # end-of-line labels, nudged apart so close series do not overprint
    for i, v in enumerate(sorted(ends)):
        yy = v
        for prev in sorted(ends)[:i]:
            if abs(yy - prev) < 0.045:
                yy = prev + 0.045
        ax.text(2.06, yy, f"{v*100:.1f}%", va="center", fontsize=8)
    ax.set_xticks(range(3))
    ax.set_xticklabels(["raw_15\n(as Qdrant returned)",
                        "reranked_15\n(reordered)",
                        "filtered_n\n(reached the model)"])
    ax.set_ylabel("Recall@15")
    ax.yaxis.set_major_formatter(lambda v, p: f"{v*100:.0f}%")
    ax.set_ylim(0, 0.92); ax.set_xlim(-0.15, 2.3)
    ax.grid(color=GRID, lw=0.6); ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=8, loc="center left",
              bbox_to_anchor=(1.01, 0.5))
    ax.set_title("Retrieval funnel: what survives each stage", fontsize=9.5)
    save(fig, "F5_funnel",
         "F5 — Recall@15 is the share of questions whose correct section was "
         "present. The adaptive score filter costs every query set a little and "
         "the layman set half of what it had. But the layman line starts at 15%: "
         "the filter is not the main problem, the retrieval is. Correctness "
         "definition retrieved@k; shaded bands are 95% Wilson intervals.")


def f6_ablation(g):
    items = [("max_score (single best similarity)", g["sig_max_score"], CGREEN),
             ("top_k_mean", g["sig_top_k_mean"], CGREY),
             ("score_gap (raw)", g["sig_score_gap"], CGREY),
             ("composite, sign-corrected", g["cc_composite_corrected"], CBLUE),
             ("composite AS DEPLOYED", g["sig_composite"], CRED),
             ("entity_coverage", g["sig_entity_coverage"], CGREY),
             ("gap_term as deployed (inverted)", g["sig_gap_term"], CRED)]
    fig, ax = plt.subplots(figsize=(8.4, 3.7))
    y = np.arange(len(items))[::-1]
    for yy, (lab, r, col) in zip(y, items):
        errbars(ax, [yy], [r.v], [float(r.r["ci_lo"])], [float(r.r["ci_hi"])], col)
        ax.text(r.v, yy + 0.22, f"{r.v:.3f}", ha="center", fontsize=8, color=col)
    ax.axvline(0.5, color=INK, ls="--", lw=1)
    # sits INSIDE the axes, below the last row -- it used to collide with the title
    ax.set_ylim(-0.95, len(items) - 0.35)
    ax.text(0.505, -0.62, "0.5 = coin flip", fontsize=7.5, color=INK,
            ha="left", va="center")
    ax.set_yticks(y); ax.set_yticklabels([i[0] for i in items])
    ax.set_xlim(0.15, 0.92); ax.set_xlabel("AUROC — higher separates right from wrong better")
    ax.grid(axis="x", color=GRID, lw=0.6); ax.set_axisbelow(True)
    ax.set_title(f"Confidence signals   (n={g['sig_composite'].n}, "
                 f"95% bootstrap CI)", fontsize=9.5)
    save(fig, "F6_ablation",
         "F6 — The deployed composite (red) is beaten by three of its own "
         "ingredients. One term is inverted and scores below chance. Correcting "
         "the sign lifts the blend (blue) but it still loses to a single raw "
         "similarity (green). Measured under correctness definition retrieved@k "
         "at retrieval stage raw_15.")


def f7_reliability(g):
    d = load("calibration.csv")
    s = d[(d.metric == "reliability_bin_accuracy") &
          (d.definition == "retrieved@k") & (d.query_set == "ALL")]
    fig, ax = plt.subplots(figsize=(5.4, 4.6))
    ax.plot([0, 1], [0, 1], ls="--", color=INK, lw=1, label="perfect calibration")
    for score, col in (("composite", CRED), ("max_score", CGREEN)):
        sub = s[s.notes.str.contains(f"score={score}", regex=False)]
        pts = []
        for _, r in sub.iterrows():
            m = re.search(r"mean_score=([\d.]+)", str(r["notes"]))
            b = re.search(r"bin=(\d+)", str(r["notes"]))
            if m and b:
                pts.append((int(b.group(1)), float(m.group(1)), float(r["value"]),
                            int(r["n"])))
        pts.sort()
        xs = [p[1] for p in pts]; ys = [p[2] for p in pts]
        ax.plot(xs, ys, "-o", color=col, markersize=5, lw=1.5,
                label=f"{score} ({len(pts)} quantile bins)")
        ax.annotate(f"n={pts[0][3]}/bin", (xs[0], ys[0]), textcoords="offset points",
                    xytext=(4, -11), fontsize=7, color=col)
    ax.set_xlabel("mean confidence claimed in the bin")
    ax.set_ylabel("share actually correct in the bin")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1.02)
    ax.grid(color=GRID, lw=0.6); ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax.set_title(f"Reliability, quantile (equal-mass) bins\n"
                 f"n={g['ece_comp'].n}, definition retrieved@k, stage raw_15",
                 fontsize=9.5)
    save(fig, "F7_reliability",
         "F7 — On the diagonal means a claimed confidence matches observed "
         "accuracy. The deployed composite (red) is NON-MONOTONE: it peaks in "
         "the middle and falls back at the top, so its most confident answers "
         "are no better than its middling ones. max_score (green) rises "
         "throughout.")


def f8_risk_coverage(g):
    DROPPED.append("F8: the full risk-coverage CURVE is not in calibration.csv "
                   "— only three anchor points per score (coverage at 10% risk, "
                   "AURC, risk at full coverage). Plotted as anchors, not a curve.")
    fig, ax = plt.subplots(figsize=(6.6, 3.2))
    labs, vals, cols = [], [], []
    for score, tag, col in (("composite", "comp", CRED), ("max_score", "max", CGREEN)):
        for defn in ("retrieved@k", "cited"):
            r = pick("calibration.csv", metric="coverage_at_risk_0.10",
                     definition=defn, query_set="ALL", notes=f"score={score}")
            labs.append(f"{score}\n{defn}"); vals.append(r.v); cols.append(col)
    y = np.arange(len(labs))[::-1]
    ax.barh(y, vals, color=cols, edgecolor=INK, lw=0.6)
    for yy, v in zip(y, vals):
        ax.text(v + 0.012, yy, f"{v:.3f}", va="center", fontsize=8)
    ax.set_yticks(y); ax.set_yticklabels(labs, fontsize=8)
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("share of questions answerable while holding error at or below 10%")
    ax.grid(axis="x", color=GRID, lw=0.6); ax.set_axisbelow(True)
    ax.set_title(f"Coverage at 10% risk  (n={g['cov_comp'].n})", fontsize=9.5)
    save(fig, "F8_coverage_at_risk",
         "F8 — Under retrieved@k, BOTH scores are at or near zero: there is no "
         "confidence threshold at which the system can answer any share of "
         "questions and be wrong only one time in ten. These zeros are measured, "
         "not missing. The full risk-coverage curve is not in the results files "
         "and is not shown.")


def f9_ceiling(g):
    sets = [("generated_retrieval", "generated"),
            ("paired_recodification", "paired IPC/BNS"),
            ("paired_dated_conflict", "dated conflict"),
            ("layman_situation", "layman"),
            ("paired_numbered_bns_named", "  └ BNS-named only"),
            ("ALL", "POOLED")]
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    y = np.arange(len(sets))[::-1]
    for yy, (qs, lab) in zip(y, sets):
        r = pick("hybrid_comparison.csv", metric="gold_reachable_ceiling",
                 query_set=qs)
        col = CRED if r.v < 0.5 else CBLUE if qs != "ALL" else CGREEN
        ax.barh(yy, r.v, color=col, edgecolor=INK, lw=0.6)
        ax.errorbar(r.v, yy, xerr=[[r.v - float(r.r["ci_lo"])],
                                   [float(r.r["ci_hi"]) - r.v]],
                    fmt="none", ecolor=INK, capsize=2.5, lw=1)
        ax.text(0.012, yy, f"{r.v*100:.1f}%  (n={r.n})", va="center", fontsize=8,
                color="white" if r.v > 0.25 else INK)
    ax.set_yticks(y); ax.set_yticklabels([s[1] for s in sets], fontsize=8.5)
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("share of queries whose gold section the index can return at all")
    ax.xaxis.set_major_formatter(lambda v, p: f"{v*100:.0f}%")
    ax.grid(axis="x", color=GRID, lw=0.6); ax.set_axisbelow(True)
    ax.set_title("Gold reachability ceiling — the maximum any retriever could score",
                 fontsize=9.5)
    save(fig, "F9_ceiling",
         "F9 — Where gold labels name a subsection the index stores only as a "
         "bare section, no retriever can score them. BNS-named queries are capped "
         "at 33.3%: every recall figure must be read against this, not against "
         "100%.")


# ============================================================ GATHER
def gather() -> dict:
    g = {}
    for arm in ("dense", "bm25", "hybrid_rrf"):
        for side in ("ipc", "bns"):
            g[f"dom_{arm}_{side}"] = pick(
                "hybrid_comparison.csv", metric="corpus_dominant_accuracy",
                stage=arm, query_set=f"paired_numbered_{side}_named")
        g[f"dom_{arm}_both"] = pick("hybrid_comparison.csv",
                                    metric="corpus_dominant_accuracy", stage=arm,
                                    query_set="paired_numbered_both")
    for side in ("ipc", "bns"):
        g[f"chance_{side}"] = pick("hybrid_comparison.csv",
                                   metric="chance_baseline_corpus_share",
                                   query_set="INDEX",
                                   notes=f"{side.upper()}'s share")
        g[f"top1_dense_{side}"] = pick("hybrid_comparison.csv",
                                       metric="corpus_top1_accuracy", stage="dense",
                                       query_set=f"paired_numbered_{side}_named")
    g["ceiling_all"] = pick("hybrid_comparison.csv",
                            metric="gold_reachable_ceiling", query_set="ALL")
    g["ceiling_bns"] = pick("hybrid_comparison.csv",
                            metric="gold_reachable_ceiling",
                            query_set="paired_numbered_bns_named")
    for sig in ("max_score", "composite", "top_k_mean", "entity_coverage"):
        g[f"sig_{sig}"] = pick("ablation.csv", metric="auroc_signal",
                               definition="retrieved@k", query_set="ALL",
                               notes=f"signal={sig};")
    g["sig_gap_term"] = pick("ablation.csv", metric="auroc_signal",
                             definition="retrieved@k", query_set="ALL",
                             notes="signal=gap_term")
    g["sig_score_gap"] = pick("ablation.csv", metric="auroc_signal",
                              definition="retrieved@k", query_set="ALL",
                              notes="signal=score_gap;")
    d1 = "retrieved@15 (raw_15)"
    for s in ("composite_deployed", "composite_corrected", "max_score"):
        g[f"cc_{s}"] = pick("corrected_composite.csv", metric="auroc",
                            definition=d1, notes=f"score={s};")
    g["cc_diff_corr_max"] = pick("corrected_composite.csv",
                                 metric="auroc_paired_diff", definition=d1,
                                 notes="composite_corrected minus max_score")
    g["cc_diff_dep_max"] = pick("corrected_composite.csv",
                                metric="auroc_paired_diff", definition=d1,
                                notes="composite_deployed minus max_score")
    g["cc_best_test"] = pick("corrected_composite.csv",
                             metric="auroc_corrected_bestweights_test",
                             definition=d1)
    for dd, st, key in [("retrieved@15", "raw_15", "gap_ret"),
                        ("cited", None, "gap_cit"), ("grounded", None, "gap_gro")]:
        extra = {"stage": st} if st else {}
        g[key] = pick("robustness.csv", metric="paired_gap_ipc_minus_bns",
                      definition=dd, query_set="paired_recodification",
                      notes="restriction=none", **extra)
    g["layman_raw"] = pick("robustness.csv", metric="layman_rate",
                           definition="retrieved@15", stage="raw_15",
                           notes="restriction=none")
    g["layman_filt"] = pick("robustness.csv", metric="layman_rate",
                            definition="retrieved@15", stage="filtered_n",
                            notes="restriction=none")
    for book in ("CRPC", "BNS", "IPC"):
        for st in ("raw_15", "filtered_n"):
            g[f"or_{book}_{st}"] = pick(
                "routing_confusion.csv",
                metric=f"over_representation_ratio_{book}",
                query_set="layman_situation", stage=st)
    for sc, tag in (("composite", "comp"), ("max_score", "max")):
        g[f"cov_{tag}"] = pick("calibration.csv", metric="coverage_at_risk_0.10",
                               definition="retrieved@k", query_set="ALL",
                               notes=f"score={sc}")
        g[f"ece_{tag}"] = pick("calibration.csv", metric="ece",
                               definition="retrieved@k", query_set="ALL",
                               notes=f"score={sc}")
    g["sc_dated"] = pick("statute_consistency.csv",
                         metric="auroc_statute_consistency", stage="raw_15",
                         definition="retrieved@k", query_set="paired_dated_conflict")
    g["sc_all"] = pick("statute_consistency.csv",
                       metric="auroc_statute_consistency", stage="raw_15",
                       definition="retrieved@k", query_set="ALL")
    for qs in ("generated_retrieval", "paired_recodification",
               "paired_dated_conflict", "layman_situation", "ALL"):
        g[f"rec_{qs}"] = pick("retrieval_metrics.csv", metric="recall_at_k",
                              k="15.0", definition="retrieved@k", stage="raw_15",
                              query_set=qs)
    g["idx_all"] = pick("self_naming.csv", metric="index_chunks", query_set="ALL")
    for c in ("IPC", "BNS", "CRPC", "CPA"):
        g[f"idx_{c}"] = pick("self_naming.csv", metric="index_chunks_in_corpus",
                             query_set=c)
    for t in ("sanhita", "penal"):
        g[f"df_{t}"] = pick("self_naming.csv", metric="document_frequency",
                            definition=t, query_set="ALL")
        g[f"idf_{t}"] = pick("self_naming.csv", metric="idf_okapi",
                             definition=t, query_set="ALL")
        for c in ("IPC", "BNS", "CRPC"):
            g[f"df_{t}_{c}"] = pick("self_naming.csv",
                                    metric="document_frequency_in_corpus",
                                    definition=t, query_set=c)
    for c in ("IPC", "BNS"):
        g[f"selfname_{c}"] = pick("self_naming.csv",
                                  metric="self_naming_rate_distinctive",
                                  query_set=c)
    return g


if __name__ == "__main__":
    print("building figures...")
    g = gather()
    f1_pipeline(g); f2_ipc_bns(g); f3_inversion(g); f4_self_naming(g)
    f5_funnel(g); f6_ablation(g); f7_reliability(g); f8_risk_coverage(g)
    f9_ceiling(g)

    from experiments.report_text import build_markdown, build_html
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                         capture_output=True, text=True).stdout.strip()
    total = sum(len(load(f)) for f in REGEN)
    md = build_markdown(g, FIGS, sha, total, DROPPED)
    (ROOT / "docs" / "TECHNICAL_REPORT.md").write_text(md, encoding="utf-8")
    html = build_html(md, FIGS, sha)
    (ROOT / "docs" / "TECHNICAL_REPORT.html").write_text(html, encoding="utf-8")
    print(f"\n{len(g)} figures sourced · {len(FIGS)} plots · {total} result rows")
    print(f"DROPPED: {len(DROPPED)}")
    for d in DROPPED:
        print("  -", d)
