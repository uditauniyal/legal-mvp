"""Build docs/SYNOPSIS_IT118.tex and compile it to PDF with pdflatex.

Same content and same sourcing rule as every other document in this project:
every number is pulled from results/*.csv by a filter that must match EXACTLY
ONE row, or the build fails. Prose comes from experiments/synopsis_text.py.

FORMAT, from "Synopsis Format for Research based Project.docx":
  font          Times New Roman; 14 bold headings, 12 bold subheadings, 12 body
  line spacing  1.5
  margins       1 inch top/bottom/right, 1.25 inch left
  alignment     justified body, left headings
  page numbers  bottom centre, Times New Roman 12
  figures       numbered and labelled, placed near the reference
  tables        title above, centred, single-spaced, minimal borders
  equations     centred, numbered sequentially in parentheses
  references    IEEE
  length        10 to 15 pages

NOTE FOR ANYONE EDITING THIS FILE: do not patch it through a shell heredoc.
Backslashes do not survive the round trip -- \\v became a vertical tab and \\f a
form feed, which produced LaTeX errors that looked like content errors. Edit the
file directly or with a patch script written to disk.

    ./venv/Scripts/python.exe experiments/make_synopsis_tex.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from experiments.make_synopsis import gather
import experiments.synopsis_text as T

BUILD = ROOT / "build" / "tex"
BUILD.mkdir(parents=True, exist_ok=True)
TEX = BUILD / "SYNOPSIS_IT118.tex"
OUT_TEX = ROOT / "docs" / "SYNOPSIS_IT118.tex"
OUT_PDF = ROOT / "docs" / "SYNOPSIS_IT118.pdf"
PDFLATEX = Path(r"C:\Users\uniya\AppData\Local\Programs\MiKTeX\miktex\bin\x64"
                r"\pdflatex.exe")

DROPPED: list[str] = []
BS = chr(92)          # backslash, built from its code point so no shell eats it
NL = BS + BS          # a LaTeX forced line break


def esc(s: str) -> str:
    """LaTeX-safe. Applied to prose only, never to markup this file emits."""
    s = s.replace(BS, r"\textbackslash{}")
    for a, b in [("&", r"\&"), ("%", r"\%"), ("$", r"\$"), ("#", r"\#"),
                 ("_", r"\_"), ("{", r"\{"), ("}", r"\}"),
                 ("~", r"\textasciitilde{}"), ("^", r"\textasciicircum{}")]:
        s = s.replace(a, b)
    s = re.sub(r'"([^"]*)"', r"``\1''", s)
    s = s.replace(" -- ", " --- ")
    return s


PREAMBLE = r"""\documentclass[12pt,a4paper]{article}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{times}
\usepackage[top=1in,bottom=1in,right=1in,left=1.25in]{geometry}
\usepackage{setspace}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{amsmath}
\usepackage{caption}
\usepackage{fancyhdr}
\usepackage{enumitem}
\usepackage{titlesec}
\usepackage{array}
\usepackage[hidelinks]{hyperref}
\usepackage{ragged2e}

\setlength{\floatsep}{7pt}
\setlength{\textfloatsep}{9pt}
\setlength{\intextsep}{7pt}
\setlength{\abovecaptionskip}{3pt}
\setlength{\belowcaptionskip}{2pt}

\onehalfspacing
\setlength{\parindent}{0pt}
\setlength{\parskip}{4pt}

\titleformat{\section}{\normalfont\fontsize{14}{17}\bfseries\raggedright}{\thesection}{0.6em}{}
\titlespacing*{\section}{0pt}{11pt}{6pt}
\titleformat{\subsection}{\normalfont\fontsize{12}{15}\bfseries\raggedright}{\thesubsection}{0.55em}{}
\titlespacing*{\subsection}{0pt}{8pt}{4pt}

\pagestyle{fancy}
\fancyhf{}
\renewcommand{\headrulewidth}{0pt}
\fancyfoot[C]{\fontsize{12}{14}\selectfont\thepage}

\captionsetup{font={small,it},labelfont={small,bf},justification=centering,skip=3pt}
\captionsetup[table]{position=above,font={small},labelfont={small,bf}}

\setlist[enumerate]{leftmargin=1.6em,itemsep=2pt,topsep=2pt,parsep=0pt}
\setlist[itemize]{leftmargin=1.6em,itemsep=2pt,topsep=2pt,parsep=0pt}

\begin{document}
\justifying
"""


def sized(pt: int, lead: int, text: str, bold: bool = False) -> str:
    b = r"\bfseries " if bold else ""
    return "{" + BS + "fontsize{" + str(pt) + "}{" + str(lead) + "}" \
           + BS + "selectfont " + b + text + "}"


def title_page() -> str:
    # escape each line BEFORE joining, or esc() turns the break into markup
    desig = (NL + "[1pt]").join(esc(l) for l in T.MENTOR_DESIG.split("\n"))
    L = [
        r"\thispagestyle{empty}",
        r"\begin{center}",
        r"\vspace*{1.1cm}",
        sized(14, 17, "Synopsis on") + NL + "[14pt]",
        sized(17, 21, esc(T.TITLE), bold=True) + NL + "[22pt]",
        sized(14, 17, "Submitted by") + NL + "[10pt]",
        sized(13, 16, "Group ID: " + esc(T.GROUP_ID), bold=True) + NL + "[4pt]",
        sized(13, 16, esc(T.ROLL) + r"\quad " + esc(T.STUDENT)) + NL + "[22pt]",
        sized(14, 17, "For the award of the degree of") + NL + "[10pt]",
        sized(13, 16, esc(T.DEGREE), bold=True) + NL + "[22pt]",
        sized(14, 17, "Under the Supervision of") + NL + "[10pt]",
        sized(13, 16, esc(T.MENTOR), bold=True) + NL + "[5pt]",
        sized(12, 15, desig) + NL + "[24pt]",
        sized(14, 17, esc(T.DEPARTMENT), bold=True) + NL + "[4pt]",
        sized(14, 17, esc(T.INSTITUTE), bold=True) + NL + "[4pt]",
        sized(13, 16, esc(T.SESSION)),
        r"\end{center}",
        r"\clearpage",
        "",
    ]
    return "\n".join(L) + "\n"


def contents(heads) -> str:
    # No \clearpage after the list: it fills a quarter of a page, and the format
    # caps the document at 15 pages, so Section 1 continues below it.
    L = [r"\thispagestyle{empty}",
         sized(14, 17, "Table of Contents", bold=True),
         r"\vspace{8pt}",
         r"\begin{enumerate}[label=\arabic*.,leftmargin=2.2em]"]
    for h in heads:
        L.append(r"  \item " + esc(re.sub(r"^\d+\.\s*", "", h)))
    L += [r"\end{enumerate}", ""]
    return "\n".join(L) + "\n"


def figure(stem: str, caption: str) -> str:
    p = ROOT / "figures" / f"{stem}.png"
    if not p.exists():
        DROPPED.append(f"figure {stem}.png absent")
        return ""
    return ("\n" + r"\begin{figure}[htbp]" + "\n" + r"\centering" + "\n"
            + r"\includegraphics[width=0.80\textwidth]{" + p.as_posix() + "}\n"
            + r"\caption{" + esc(caption) + "}\n"
            + r"\end{figure}" + "\n\n")


def table(caption: str, header: list, rows: list) -> str:
    widths = {4: r"p{0.30\textwidth}p{0.22\textwidth}rr",
              5: r"p{0.26\textwidth}rrrp{0.16\textwidth}"}
    spec = widths.get(len(header), "l" * len(header))
    L = ["\n" + r"\begin{table}[htbp]", r"\centering",
         r"\caption{" + esc(caption) + "}",
         r"\small", r"\setstretch{1.0}",
         r"\begin{tabular}{@{}" + spec + r"@{}}", r"\toprule",
         " & ".join(r"\textbf{" + esc(h) + "}" for h in header) + " " + NL,
         r"\midrule"]
    for row in rows:
        cells = [esc(str(c)) for c in row]
        if cells[0] == "Total":
            L.append(r"\midrule")
            cells = [r"\textbf{" + c + "}" if c else "" for c in cells]
        L.append(" & ".join(cells) + " " + NL)
    L += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    return "\n".join(L) + "\n"


def equation(body: str) -> str:
    b = body.replace("<=", r"\leq").replace(">=", r"\geq")
    b = b.replace("SUM", r"\sum").replace("s_top", r"s_{\text{top}}")
    # lambda replacements: a plain string would be read as a regex template,
    # where a lone backslash is an invalid escape.
    for w in ("min", "ln"):
        b = re.sub(r"\b" + w + r"\b", lambda m, w=w: BS + w, b)
    for w in ("idf", "RRF", "rank"):
        b = re.sub(r"\b" + w + r"\b",
                   lambda m, w=w: BS + "mathrm{" + w + "}", b)
    return ("\n" + r"\begin{equation}" + "\n" + b + "\n"
            + r"\end{equation}" + "\n\n")


def build_body(V: dict) -> str:
    out = []
    for head, blocks in T.sections(V):
        out.append(r"\section*{" + esc(head) + "}")
        for b in blocks:
            kind = b[0]
            if kind == "p":
                out.append(esc(b[1].format(**V)) + "\n")
            elif kind == "h2":
                out.append(r"\subsection*{" + esc(b[1]) + "}")
            elif kind == "fig":
                out.append(figure(b[1], b[2].format(**V)))
            elif kind == "tbl":
                rows = [[c.format(**V) for c in r] for r in b[3]]
                out.append(table(b[1].format(**V), b[2], rows))
            elif kind == "eq":
                out.append(equation(b[1]))
            elif kind in ("bul", "num"):
                env = "enumerate" if kind == "num" else "itemize"
                out.append(r"\begin{" + env + "}")
                for item in b[1]:
                    out.append(r"  \item " + esc(item.format(**V)))
                out.append(r"\end{" + env + "}" + "\n")
    out.append(r"\section*{8. References}")
    out.append(r"\begin{enumerate}[label={[\arabic*]},leftmargin=2.6em]")
    for ref in T.REFERENCES:
        out.append(r"  \item " + esc(ref))
    out.append(r"\end{enumerate}")
    return "\n".join(out)


def compile_tex():
    for _ in range(2):          # twice, so page references settle
        subprocess.run([str(PDFLATEX), "-interaction=nonstopmode",
                        "-halt-on-error", TEX.name],
                       cwd=BUILD, capture_output=True, timeout=900)
    pdf = BUILD / "SYNOPSIS_IT118.pdf"
    if not pdf.exists():
        log = BUILD / "SYNOPSIS_IT118.log"
        if log.exists():
            for line in log.read_text(errors="replace").splitlines():
                if line.startswith("!"):
                    print("   ", line)
        return None
    OUT_PDF.write_bytes(pdf.read_bytes())
    import fitz
    return fitz.open(OUT_PDF).page_count


def main() -> None:
    print("sourcing values...")
    V = gather()
    print(f"  {len(V)} values sourced")

    heads = [h for h, _ in T.sections(V)] + ["8. References"]
    doc = (PREAMBLE + title_page() + contents(heads) + build_body(V)
           + "\n" + r"\end{document}" + "\n")
    TEX.write_text(doc, encoding="utf-8")
    OUT_TEX.write_text(doc, encoding="utf-8")
    print(f"  wrote {OUT_TEX.name}  ({len(doc.splitlines())} lines)")

    print("compiling...")
    pages = compile_tex()
    if pages:
        print(f"  wrote {OUT_PDF.name}  ({pages} pages)")
        if pages > 15:
            DROPPED.append(f"OVER LENGTH: {pages} pages, format caps at 15")
    else:
        DROPPED.append("pdflatex produced no PDF")

    print(f"DROPPED: {len(DROPPED)}")
    for d in DROPPED:
        print("  -", d)


if __name__ == "__main__":
    main()
