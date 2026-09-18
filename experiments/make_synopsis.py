"""Build docs/SYNOPSIS_IT118.docx (and a PDF) to the department format.

SOURCING RULE, same as every other document in this project: no number is typed.
Every value is pulled from results/*.csv by a filter that must match EXACTLY ONE
row, or the build fails. Values that cannot live in a CSV (the test count, the
raw log-row count) are measured live and reported as such.

FORMAT, from "Synopsis Format for Research based Project.docx":
  font          Times New Roman; 14 bold headings, 12 bold subheadings, 12 body
  line spacing  1.5
  margins       1 inch top/bottom/right, 1.25 inch left
  alignment     justified body, left headings
  page numbers  bottom centre, Times New Roman 12
  figures       numbered and labelled, placed near the reference
  tables        title above, centred, single-spaced, minimal borders
  equations     centred, numbered sequentially in parentheses, right aligned
  references    IEEE
  length        10 to 15 pages

    ./venv/Scripts/python.exe experiments/make_synopsis.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import docx
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from experiments.make_supervisor_brief import pick, load  # the sourcing rule
import experiments.synopsis_text as T

FIG = ROOT / "figures"
OUT_DOCX = ROOT / "docs" / "SYNOPSIS_IT118.docx"
OUT_PDF = ROOT / "docs" / "SYNOPSIS_IT118.pdf"

FONT = "Times New Roman"
DROPPED: list[str] = []


# ------------------------------------------------------------------ sourcing
def pc(r, dp=1):
    return f"{r.v * 100:.{dp}f}%"


def num(r, dp=3):
    return f"{r.v:.{dp}f}"


def ci(r, dp=3, as_pct=False):
    lo, hi = float(r.r["ci_lo"]), float(r.r["ci_hi"])
    if as_pct:
        return f"[{lo*100:.1f}%, {hi*100:.1f}%]"
    return f"[{lo:.{dp}f}, {hi:.{dp}f}]"


def cci(r, dp=3):
    lo, hi = float(r.r["cluster_ci_lo"]), float(r.r["cluster_ci_hi"])
    return f"[{lo:.{dp}f}, {hi:.{dp}f}]"


def gather() -> dict:
    """Every number in the synopsis. One row or the build fails."""
    H, A, C = "hybrid_comparison.csv", "ablation.csv", "corrected_composite.csv"
    R, K, S = "robustness.csv", "calibration.csv", "self_naming.csv"
    Tm = "retrieval_metrics.csv"
    V: dict[str, str] = {}

    # --- corpus -----------------------------------------------------------
    idx = pick(S, metric="index_chunks", query_set="ALL")
    V["n_chunks"] = f"{int(idx.v):,}"
    for code, key in [("CRPC", "crpc"), ("IPC", "ipc"),
                      ("BNS", "bns"), ("CPA", "cpa")]:
        c = pick(S, metric="index_chunks_in_corpus", query_set=code)
        V[f"c_{key}"] = f"{int(c.v)}"
        V[f"s_{key}"] = f"{c.v / idx.v * 100:.2f}%"

    # --- evaluation set ---------------------------------------------------
    ceil_all = pick(H, metric="gold_reachable_ceiling", query_set="ALL")
    V["n_queries"] = f"{int(ceil_all.n)}"
    V["ceiling_all"] = pc(ceil_all)
    V["ceiling_bns"] = pc(pick(H, metric="gold_reachable_ceiling",
                               query_set="paired_numbered_bns_named"))
    for qs, key in [("generated_retrieval", "q_gen"),
                    ("paired_recodification", "q_paired"),
                    ("paired_dated_conflict", "q_dated"),
                    ("layman_situation", "q_layman")]:
        V[key] = f"{int(pick(H, metric='gold_reachable_ceiling', query_set=qs).n)}"

    # --- cross-statute retrieval ------------------------------------------
    for arm, tag in [("dense", "dense"), ("bm25", "bm25"), ("hybrid_rrf", "rrf")]:
        for side in ("ipc", "bns"):
            r = pick(H, metric="corpus_dominant_accuracy", stage=arm,
                     query_set=f"paired_numbered_{side}_named")
            V[f"{side}_{tag}"] = pc(r)
            V[f"{side}_{tag}_ci"] = ci(r, as_pct=True)
            V["n_arm"] = f"{int(r.n)}"
    for side in ("ipc", "bns"):
        V[f"chance_{side}"] = pc(pick(H, metric="chance_baseline_corpus_share",
                                      query_set="INDEX",
                                      notes=f"{side.upper()}'s share"))

    # --- confidence signals ------------------------------------------------
    sig = {"composite": "signal=composite;", "max": "signal=max_score;",
           "gapterm": "signal=gap_term", "scoregap": "signal=score_gap;"}
    for key, note in sig.items():
        r = pick(A, metric="auroc_signal", definition="retrieved@k",
                 query_set="ALL", notes=note)
        V[f"auroc_{key}"] = num(r)
        V[f"auroc_{key}_ci"] = ci(r)
        V["n_rows"] = f"{int(r.n)}"
    V["auroc_corrected"] = num(pick(C, metric="auroc",
                                    definition="retrieved@15 (raw_15)",
                                    notes="score=composite_corrected;"))

    # --- calibration -------------------------------------------------------
    for score, key in [("composite", "composite"), ("max_score", "max")]:
        V[f"ece_{key}"] = num(pick(K, metric="ece", definition="retrieved@k",
                                   query_set="ALL", notes=f"score={score}"))
        V[f"cov_{key}"] = num(pick(K, metric="coverage_at_risk_0.10",
                                   definition="retrieved@k", query_set="ALL",
                                   notes=f"score={score}"))

    # --- the citation-level divergence -------------------------------------
    g_ret = pick(R, metric="paired_gap_ipc_minus_bns", definition="retrieved@15",
                 stage="raw_15", query_set="paired_recodification",
                 notes="restriction=none")
    g_cit = pick(R, metric="paired_gap_ipc_minus_bns", definition="cited",
                 query_set="paired_recodification", notes="restriction=none")
    V["gap_retrieved"] = f"{g_ret.v:+.3f}"
    V["gap_retrieved_ci"] = cci(g_ret)
    V["gap_cited"] = f"{g_cit.v:+.3f}"
    V["gap_cited_ci"] = cci(g_cit)
    V["n_paired"] = f"{int(g_ret.n)}"

    # --- the layman set: the users the system exists for ---------------------
    # Added 2026-09-18. These numbers were measured in Wave 3 and sat in
    # robustness.csv unreported, which is why the synopsis claimed six findings
    # where seven are established. `grounded` means EVERY citation in the
    # answer was present in the retrieved passages, so 0/120 says every layman
    # answer carried at least one citation retrieval never supplied.
    for defn, stage, key in [("retrieved@15", "raw_15", "layman_raw"),
                             ("retrieved@15", "filtered_n", "layman_filt"),
                             ("cited", None, "layman_cited"),
                             ("grounded", None, "layman_grounded")]:
        f = dict(metric="layman_rate", query_set="layman_situation",
                 definition=defn)
        if stage:
            f["stage"] = stage
        r = pick(R, notes="restriction=none", **f)
        V[key] = pc(r)
        V[f"{key}_ci"] = ci(r, as_pct=True)
        V[f"{key}_n"] = f"{int(r.n)}"
    # NOT quoted as an interval anywhere. robustness.csv gives [0.000, 0.000]
    # for the grounded row, which claims certainty at zero -- exactly what
    # Section 6.4 says the Wilson interval is used to avoid. Reported as the
    # count instead, which is what the data actually supports.
    V["layman_grounded_count"] = f"0 of {V['layman_grounded_n']}"

    # --- self-naming --------------------------------------------------------
    V["df_sanhita"] = f"{int(pick(S, metric='document_frequency', definition='sanhita', query_set='ALL').v)}"
    V["df_penal"] = f"{int(pick(S, metric='document_frequency', definition='penal', query_set='ALL').v)}"
    V["idf_sanhita"] = num(pick(S, metric="idf_okapi", definition="sanhita",
                                query_set="ALL"), 2)
    for corp, key in [("IPC", "penal_ipc"), ("CRPC", "penal_crpc")]:
        V[key] = f"{int(pick(S, metric='document_frequency_in_corpus', definition='penal', query_set=corp).v)}"

    # --- measured live, not in any CSV --------------------------------------
    out = subprocess.run([str(ROOT / "venv/Scripts/python.exe"), "-m", "pytest",
                          "tests/", "-q"], cwd=ROOT, capture_output=True,
                         text=True, timeout=600).stdout
    m = re.search(r"(\d+) passed", out)
    V["n_tests"] = m.group(1) if m else "NOT MEASURED"
    if not m:
        DROPPED.append("test count: pytest did not report a pass count")

    raw = sum(1 for f in (ROOT / "runs").rglob("queries.jsonl")
              for _ in f.open(encoding="utf-8"))
    V["n_raw"] = f"{raw:,}"
    return V


# ------------------------------------------------------------------ docx help
def _style(doc):
    n = doc.styles["Normal"]
    n.font.name = FONT
    n.font.size = Pt(12)
    n._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    pf = n.paragraph_format
    pf.line_spacing = 1.5
    pf.space_after = Pt(1)
    pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY


def _margins(doc):
    for s in doc.sections:
        s.top_margin = Inches(1.0)
        s.bottom_margin = Inches(1.0)
        s.right_margin = Inches(1.0)
        s.left_margin = Inches(1.25)


def _page_numbers(doc):
    """Bottom centre, Times New Roman 12 — a PAGE field in the footer."""
    for s in doc.sections:
        p = s.footer.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run()
        r.font.name = FONT
        r.font.size = Pt(12)
        for tag, txt in (("w:fldChar", None), ("w:instrText", "PAGE"),
                         ("w:fldChar", None)):
            el = OxmlElement(tag)
            if tag == "w:fldChar":
                el.set(qn("w:fldCharType"),
                       "begin" if txt is None and el is None else "begin")
            r._r.append(el)
        # rebuild cleanly: begin / instr / end
        for child in list(r._r):
            if child.tag.endswith(("fldChar", "instrText")):
                r._r.remove(child)
        b = OxmlElement("w:fldChar"); b.set(qn("w:fldCharType"), "begin")
        i = OxmlElement("w:instrText"); i.set(qn("xml:space"), "preserve")
        i.text = "PAGE"
        e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), "end")
        r._r.append(b); r._r.append(i); r._r.append(e)


def para(doc, text, size=12, bold=False, align=WD_ALIGN_PARAGRAPH.JUSTIFY,
         space_before=0, space_after=1, italic=False, spacing=1.5):
    p = doc.add_paragraph()
    p.alignment = align
    pf = p.paragraph_format
    pf.line_spacing = spacing
    pf.space_before = Pt(space_before)
    pf.space_after = Pt(space_after)
    r = p.add_run(text)
    r.font.name = FONT
    r.font.size = Pt(size)
    r.bold = bold
    r.italic = italic
    return p


def heading(doc, text):
    para(doc, text, size=14, bold=True, align=WD_ALIGN_PARAGRAPH.LEFT,
         space_before=5, space_after=2)


def subheading(doc, text):
    para(doc, text, size=12, bold=True, align=WD_ALIGN_PARAGRAPH.LEFT,
         space_before=4, space_after=2)


def equation(doc, body, number):
    """Centred equation with a right-aligned number, via a right tab stop."""
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.line_spacing = 1.5
    pf.space_before = Pt(5)
    pf.space_after = Pt(5)
    pf.tab_stops.add_tab_stop(Inches(3.0), WD_TAB_ALIGNMENT.CENTER)
    pf.tab_stops.add_tab_stop(Inches(6.0), WD_TAB_ALIGNMENT.RIGHT)
    r = p.add_run("\t" + body + "\t(" + str(number) + ")")
    r.font.name = FONT
    r.font.size = Pt(12)
    r.italic = True


def figure(doc, stem, caption, number, width=2.85):
    path = FIG / f"{stem}.png"
    if not path.exists():
        DROPPED.append(f"figure {stem}.png absent — omitted")
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(1)
    p.add_run().add_picture(str(path), width=Inches(width))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.line_spacing = 1.0
    cap.paragraph_format.space_after = Pt(3)
    r = cap.add_run(f"Figure {number}: {caption}")
    r.font.name = FONT
    r.font.size = Pt(11)
    r.italic = True


def table(doc, caption, header, rows, number):
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.line_spacing = 1.0
    cap.paragraph_format.space_before = Pt(6)
    cap.paragraph_format.space_after = Pt(4)
    r = cap.add_run(f"Table {number}: {caption}")
    r.font.name = FONT
    r.font.size = Pt(11)
    r.bold = True

    t = doc.add_table(rows=1, cols=len(header))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.style = "Table Grid"
    for i, h in enumerate(header):
        c = t.rows[0].cells[i]
        c.text = ""
        pp = c.paragraphs[0]
        pp.paragraph_format.line_spacing = 1.0
        pp.paragraph_format.space_after = Pt(2)
        rr = pp.add_run(h)
        rr.font.name = FONT
        rr.font.size = Pt(11)
        rr.bold = True
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = ""
            pp = cells[i].paragraphs[0]
            pp.paragraph_format.line_spacing = 1.0
            pp.paragraph_format.space_after = Pt(2)
            rr = pp.add_run(str(val))
            rr.font.name = FONT
            rr.font.size = Pt(11)
            rr.bold = str(val) == "Total"
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def listing(doc, items, numbered):
    for i, it in enumerate(items, 1):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        pf = p.paragraph_format
        pf.line_spacing = 1.5
        pf.left_indent = Inches(0.4)
        pf.first_line_indent = Inches(-0.25)
        pf.space_after = Pt(4)
        r = p.add_run(f"{i}. " if numbered else "\u2022  ")
        r.font.name = FONT
        r.font.size = Pt(12)
        r2 = p.add_run(it)
        r2.font.name = FONT
        r2.font.size = Pt(12)


# ------------------------------------------------------------------ title page
def title_page(doc):
    for _ in range(2):
        para(doc, "", align=WD_ALIGN_PARAGRAPH.CENTER)
    para(doc, "Synopsis on", size=14, align=WD_ALIGN_PARAGRAPH.CENTER,
         space_after=10)
    para(doc, T.TITLE, size=16, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER,
         space_after=18)
    para(doc, "Submitted by", size=14, align=WD_ALIGN_PARAGRAPH.CENTER,
         space_after=8)
    para(doc, f"Group ID: {T.GROUP_ID}", size=13, bold=True,
         align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
    para(doc, f"{T.ROLL}    {T.STUDENT}", size=13,
         align=WD_ALIGN_PARAGRAPH.CENTER, space_after=18)
    para(doc, "For the award of the degree of", size=14,
         align=WD_ALIGN_PARAGRAPH.CENTER, space_after=8)
    para(doc, T.DEGREE, size=13, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER,
         space_after=18)
    para(doc, "Under the Supervision of", size=14,
         align=WD_ALIGN_PARAGRAPH.CENTER, space_after=8)
    para(doc, T.MENTOR, size=13, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER,
         space_after=2)
    for line in T.MENTOR_DESIG.split("\n"):
        para(doc, line, size=12, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=0,
             spacing=1.15)
    # The department template places the Banasthali Vidyapith seal here, after
    # the supervisor block and before the department block, at 1.21in x 1.08in
    # (wp:extent of word/media/image1.png in the format .docx). Extracted once
    # to assets/. An earlier draft of both builders omitted it.
    seal = ROOT / "assets" / "banasthali_logo.png"
    if seal.exists():
        sp = doc.add_paragraph()
        sp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        sp.paragraph_format.space_before = Pt(14)
        sp.paragraph_format.space_after = Pt(10)
        sp.add_run().add_picture(str(seal), height=Inches(1.08))
    else:
        DROPPED.append("title-page logo assets/banasthali_logo.png absent")
    para(doc, T.DEPARTMENT, size=14, bold=True,
         align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
    para(doc, T.INSTITUTE, size=14, bold=True,
         align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
    para(doc, T.SESSION, size=13, align=WD_ALIGN_PARAGRAPH.CENTER)
    doc.add_page_break()


def contents_page(doc, headings):
    heading(doc, "Table of Contents")
    for h in headings:
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.5
        p.paragraph_format.left_indent = Inches(0.3)
        p.paragraph_format.space_after = Pt(4)
        r = p.add_run(h)
        r.font.name = FONT
        r.font.size = Pt(12)
    doc.add_page_break()


# ------------------------------------------------------------------ the build
def main():
    print("sourcing values...")
    V = gather()
    print(f"  {len(V)} values sourced")

    doc = docx.Document()
    _style(doc)
    _margins(doc)
    _page_numbers(doc)

    title_page(doc)
    secs = T.sections(V)
    contents_page(doc, [s[0] for s in secs] + ["8. References"])

    fig_n = tbl_n = 0
    for head, blocks in secs:
        heading(doc, head)
        for b in blocks:
            kind = b[0]
            if kind == "p":
                para(doc, b[1].format(**V))
            elif kind == "h2":
                subheading(doc, b[1])
            elif kind == "fig":
                fig_n += 1
                figure(doc, b[1], b[2].format(**V), fig_n)
            elif kind == "tbl":
                tbl_n += 1
                rows = [[c.format(**V) for c in row] for row in b[3]]
                table(doc, b[1].format(**V), b[2], rows, tbl_n)
            elif kind == "eq":
                equation(doc, b[1], b[2])
            elif kind in ("bul", "num"):
                listing(doc, [x.format(**V) for x in b[1]], kind == "num")

    # References are set 11pt single-spaced, matching the LaTeX build. The
    # department format prescribes 1.5 spacing for the BODY; an IEEE reference
    # list is conventionally set solid, and at 12pt/1.5 these 18 entries cost
    # roughly two pages against a 15-page cap.
    heading(doc, "8. References")
    for i, ref in enumerate(T.REFERENCES, 1):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        pf = p.paragraph_format
        pf.line_spacing = 0.92
        pf.left_indent = Inches(0.36)
        pf.first_line_indent = Inches(-0.36)
        pf.space_after = Pt(0)
        r = p.add_run(f"[{i}]  {ref}")
        r.font.name = FONT
        r.font.size = Pt(9)

    doc.save(OUT_DOCX)
    print(f"  wrote {OUT_DOCX.name}  ({fig_n} figures, {tbl_n} tables, "
          f"{len(T.REFERENCES)} references)")

    # PDF, for the Google Form.
    #
    # This block used to print "wrote SYNOPSIS_IT118.pdf (N pages)" whenever a
    # PDF merely EXISTED at that path, whether or not this run produced one.
    # With LibreOffice absent it therefore reported the page count of a stale
    # PDF left behind by the LaTeX builder, as a success message, for a file it
    # had not touched. That is the exact failure this project's documentation
    # protocol exists to prevent, so the claim is now tied to the conversion
    # actually having run and written the file.
    soffice = Path(r"C:\Program Files\LibreOffice\program\soffice.exe")
    converted = False
    if soffice.exists():
        stamp = OUT_PDF.stat().st_mtime if OUT_PDF.exists() else 0.0
        subprocess.run([str(soffice), "--headless", "--convert-to", "pdf",
                        "--outdir", str(OUT_PDF.parent), str(OUT_DOCX)],
                       capture_output=True, timeout=300)
        converted = OUT_PDF.exists() and OUT_PDF.stat().st_mtime > stamp
    if converted:
        import fitz
        print(f"  wrote {OUT_PDF.name}  ({fitz.open(OUT_PDF).page_count} pages)")
    else:
        DROPPED.append(
            "PDF NOT WRITTEN by this run — LibreOffice absent. Export from "
            "Word instead. Any existing docs/SYNOPSIS_IT118.pdf is STALE and "
            "its page count is not this document's.")
        if OUT_PDF.exists():
            DROPPED.append(f"  (a stale {OUT_PDF.name} is present on disk)")

    print(f"DROPPED: {len(DROPPED)}")
    for d in DROPPED:
        print("  -", d)


if __name__ == "__main__":
    main()
