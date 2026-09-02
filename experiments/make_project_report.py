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


WORKED_REQ = "8134c48bf465"          # a layman query; see worked_example()


def worked_example() -> str:
    """One real logged query, rendered from its log record. Nothing is typed.

    Chosen because it makes finding 6.6 concrete in a single row: retrieval
    missed the governing section entirely, and the written answer cited it
    anyway. The same record also shows the routing fallback, the never-firing
    refusal gate, and the tier-logging bug.
    """
    import glob, json
    rec = None
    for f in glob.glob(str(ROOT / "runs" / "**" / "queries.jsonl"), recursive=True):
        for line in open(f, encoding="utf-8"):
            r = json.loads(line)
            if r.get("req_id") == WORKED_REQ:
                rec = r
    if rec is None:
        tr.DROPPED.append(f"worked example: req_id {WORKED_REQ} not found in runs/")
        return ""

    from experiments.metrics_lib import (load_stages, ranked_sections,
                                         same_section, load_logs)
    from agents.answer import tier_for_confidence

    st = load_stages().get(WORKED_REQ, {})
    rows = load_logs()
    row = rows[rows.req_id == WORKED_REQ].iloc[0]
    gold = list(row["expected_sections"])

    i, ro, rt = rec["intake"], rec["router"], rec["retrieval"]
    cf, an, ve = rec["confidence"], rec["answer"], rec["verifier"]

    def stage_rows(name, limit=5):
        out = []
        for k, c in enumerate(st.get(name, [])[:limit], 1):
            sec = c.get("section_number")
            label = ("s. " + str(sec)) if sec else "no section number"
            out.append("| {} | {} | {} | {:.4f} | p{} |".format(
                k, c.get("corpus"), label, c.get("score"), c.get("page")))
        return "\n".join(out)

    def present(name):
        rk = ranked_sections(st.get(name, []))
        return any(same_section(g, x) for g in gold for x in rk)

    cited = ve.get("cited") or []
    grounded = set(ve.get("grounded") or [])
    ooc = set(ve.get("out_of_corpus") or [])
    cite_rows = "\n".join(
        "| `{}` | {} | {} |".format(
            c, "yes" if c in grounded else "no",
            "**not in the corpus at all**" if c in ooc else "")
        for c in cited)

    true_tier = tier_for_confidence(float(cf["composite"]))
    first_para = (an.get("answer_text") or "").strip().split("\n")[0].strip()
    lab_ret = "correct" if present("raw_15") else "**incorrect**"
    lab_cit = ("correct" if any(same_section(g, c) for g in gold for c in cited)
               else "**incorrect**")
    lab_gro = ("correct" if float(ve.get("ungrounded_rate") or 1) == 0
               else "**incorrect**")

    return f"""### 5.5 One query, all the way through

Everything above is aggregate. This is one real question from the layman set,
`{rec['query_id']}`, traced end to end from its log record. Every value below is
read from that log; none is typed.

It is here because it makes section 6.6 concrete: **the search never found the
governing section, and the answer cited it anyway.**

**The question, exactly as it was typed:**

> {rec['query_raw']}

**What the intake stage extracted.** It read the situation as
*{i.get('scenario')}*, the asker as *{i.get('persona')}*, urgency
*{i.get('urgency')}*, and listed {len(i.get('missing_facts') or [])} facts it
would need in order to answer properly — beginning with which police station is
holding him. The person asking supplied none of them, which is the normal case.

**What the router decided.** Target corpus `{ro.get('target_corpus')}`, decision
path `{ro.get('decision_path')}`, intent `{ro.get('intent')}`, entities
extracted: {ro.get('entities') or 'none'}. The question names no statute and no
section number, so no rule matched, **no corpus filter was applied, and the
search ran across all four books at once.**

**The five best passages the search returned**, of fifteen:

| rank | statute | section | similarity | page |
|---|---|---|---|---|
{stage_rows('raw_15')}

**None is the governing provision.** The top result concerns the trial of a
person of unsound mind. The second is a blank warrant form carrying no section
number at all. Only the third, on producing an arrested person before a court
without delay, is close to the subject.

**What survived the adaptive filter.** {rt.get('n_retrieved')} passages went in
and **{rt.get('n_after_filter')}** came out — the minimum the rule forces
through regardless of score. The best similarity anywhere in the search was
{rt.get('max_score'):.4f}, which is low.

**The confidence signals, and what they produced:**

| signal | value |
|---|---|
| top-5 mean similarity | {cf.get('top_k_mean')} |
| score gap | {cf.get('score_gap')} |
| entity coverage | {cf.get('entity_coverage')} |
| statute consistency | not computed at run time; built later, section 6.4 |
| **composite confidence** | **{cf.get('composite')}** |

A composite of {cf.get('composite')} falls in the **{true_tier}** band. The log
records the tier as `{an.get('prompt_variant')}`, which is wrong — that is the
tier-logging bug from section 7, visible here in a single record. The refusal
gate did not fire, as it never has.

**The first line the system wrote:**

> {first_para}

**What it cited, and whether the retrieved passages actually supported it:**

| provision cited | supported by a retrieved passage? | |
|---|---|---|
{cite_rows}

**{ve.get('n_cited')} provisions cited; {ve.get('n_grounded')} supported.** Three
come from books that were never ingested, so no passage could ever have
supported them — the model supplied those from its own training.

**The correct answer** is `{gold[0]}` for conduct before 1 July 2024 and
`{gold[1]}` on or after it. Neither appears anywhere in the fifteen passages:
present at `raw_15` — {present('raw_15')}; at `reranked_15` —
{present('reranked_15')}; at `filtered_n` — {present('filtered_n')}.

**So was this query answered correctly?** It depends entirely on the definition:

| definition | verdict | why |
|---|---|---|
| `retrieved@15` | {lab_ret} | the governing section was never fetched |
| `cited` | {lab_cit} | the answer names `{gold[1]}` regardless |
| `grounded` | {lab_gro} | {ve.get('n_ungrounded')} of {ve.get('n_cited')} citations are unsupported |

**This one row is the whole argument.** Someone asked why their father was still
in custody after three days. The search returned nothing relevant, the system
recorded itself as confident, and the answer it wrote cited the right law
anyway — so nobody reading the output would know the retrieval had failed.
"""


def build_toc(pdf_path: Path, headings: list) -> str:
    """Map each section heading to the page it starts on, from the rendered PDF."""
    import fitz
    doc = fitz.open(pdf_path)
    # Match on FONT SIZE, not text alone: the contents table repeats every
    # heading string on page 1, so a plain text search returns 1 for everything.
    # Section headings render at ~10.6pt; contents rows at ~6.6pt.
    heads = []
    for i, page in enumerate(doc):
        for blk in page.get_text("dict")["blocks"]:
            for ln in blk.get("lines", []):
                for sp in ln.get("spans", []):
                    if sp["size"] >= 9.0 and sp["text"].strip():
                        heads.append((i + 1, sp["text"].strip()))
    pages = {}
    for h in headings:
        needle = h.split(" · ", 1)[-1].strip()
        for pg, txt in heads:
            if needle in txt:
                pages[h] = pg
                break
    doc.close()
    out = ["| Section | Page |", "|---|---|"]
    for h in headings:
        out.append(f"| {h} | {pages.get(h, '-')} |")
    return "\n".join(out)


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

    print("worked example...")
    worked = worked_example()

    md_path = ROOT / "docs" / "PROJECT_REPORT.md"
    html = ROOT / "docs" / "PROJECT_REPORT.html"
    pdf = ROOT / "docs" / "PROJECT_REPORT.pdf"

    import re as _re
    toc, prev = "", None
    for attempt in range(4):
        md = build_project(g, figs, sha, total, tr.DROPPED, worked=worked, toc=toc)
        md_path.write_text(md, encoding="utf-8")
        html.write_text(build_html(md, figs, sha), encoding="utf-8")
        if not to_pdf(html, pdf):
            break
        heads = [h for h in _re.findall(r"^## (.+)$", md, _re.M) if h != "Contents"]
        toc_new = build_toc(pdf, heads)
        if toc_new == prev:
            print(f"  contents stable after {attempt + 1} render(s)")
            break
        prev, toc = toc_new, toc_new
    else:
        print("  contents did not settle in 4 renders")

    if pdf.exists():
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
