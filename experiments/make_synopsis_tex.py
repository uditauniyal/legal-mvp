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


% letterpaper, NOT a4paper. The department template is 8.5 x 11 in (read from
% its own sectPr), and A4 is 0.69 in taller -- so an A4 build silently gets
% about 7% more text per page than the format allows. The written rule in the
% template gives margins as 1 in top/bottom/right and 1.25 in left, which is
% what geometry sets below; note the template FILE contradicts its own written
% rule with a 1.25 in right margin. The written rule governs.
PREAMBLE = r"""\documentclass[12pt,letterpaper]{article}
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
\usepackage{float}

\setlength{\floatsep}{7pt}
\setlength{\textfloatsep}{9pt}
\setlength{\intextsep}{7pt}
\setlength{\abovecaptionskip}{3pt}
\setlength{\belowcaptionskip}{2pt}

% amsmath's default display skips are ~12pt above and below each numbered
% equation. Across five equations that is a fifth of a page of pure gap.
\setlength{\abovedisplayskip}{5pt}
\setlength{\belowdisplayskip}{5pt}
\setlength{\abovedisplayshortskip}{3pt}
\setlength{\belowdisplayshortskip}{3pt}

% Float packing. LaTeX defaults refuse to put more than 70% of a page into
% floats and insist on at least 20% text, which on a figure-dense document
% leaves half-empty pages. These six figures are wide and short, so the
% defaults cost more than a page of whitespace. Loosened, not removed:
% \textfraction 0.07 still forbids a page that is figures with one stray line.
\renewcommand{\topfraction}{0.92}
\renewcommand{\bottomfraction}{0.85}
\renewcommand{\textfraction}{0.07}
\renewcommand{\floatpagefraction}{0.80}
\setcounter{topnumber}{3}
\setcounter{bottomnumber}{2}
\setcounter{totalnumber}{4}

% Do NOT replace this with \setstretch{1.4x} to save space. setspace's
% \onehalfspacing already compensates for \baselineskip being 1.2x the font
% size, so it resolves to a stretch of about 1.25, and any \setstretch above
% that makes the document LONGER. Measured: 1.43 took 16 pages to 18.
% \onehalfspacing is the correct rendering of the format's "1.5 line spacing".
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

    # The department template carries the Banasthali Vidyapith seal on the
    # title page, between the supervisor block and the department block, at
    # 1.21in x 1.08in (read from the wp:extent of word/media/image1.png in
    # "Synopsis Format for Research based Project.docx"). Extracted to
    # assets/ and flattened onto white, because pdflatex composites PNG
    # alpha unreliably. An earlier draft omitted it entirely.
    logo = ROOT / "assets" / "banasthali_logo.png"
    if logo.exists():
        seal = (r"\includegraphics[height=1.08in]{" + logo.as_posix() + "}"
                + NL + "[10pt]")
    else:
        DROPPED.append("title-page logo assets/banasthali_logo.png absent")
        seal = ""

    L = [
        r"\thispagestyle{empty}",
        r"\begin{center}",
        r"\vspace*{0.7cm}",
        sized(14, 17, "Synopsis on") + NL + "[14pt]",
        sized(17, 21, esc(T.TITLE), bold=True) + NL + "[22pt]",
        sized(14, 17, "Submitted by") + NL + "[10pt]",
        sized(13, 16, "Group ID: " + esc(T.GROUP_ID), bold=True) + NL + "[4pt]",
        sized(13, 16, esc(T.ROLL) + r"\quad " + esc(T.STUDENT)) + NL + "[22pt]",
        sized(14, 17, "For the award of the degree of") + NL + "[10pt]",
        sized(13, 16, esc(T.DEGREE), bold=True) + NL + "[22pt]",
        sized(14, 17, "Under the Supervision of") + NL + "[10pt]",
        sized(13, 16, esc(T.MENTOR), bold=True) + NL + "[5pt]",
        sized(12, 15, desig) + NL + "[16pt]",
        seal,
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
    # [!ht] not [H]: measured, not guessed. Total content is 9614pt, which
    # fits in 14 pages; the document ran to 16 purely on page-break waste,
    # because a pinned figure that does not fit at the foot of a page leaves
    # the rest of that page blank. Floating lets the text close the gap. The
    # "!" tells LaTeX to ignore its own fullness limits, so a figure still
    # lands beside the sentence that reads it wherever that is possible.
    return ("\n" + r"\begin{figure}[!ht]" + "\n" + r"\centering" + "\n"
            + r"\includegraphics[width=0.62\textwidth]{" + p.as_posix() + "}\n"
            + r"\caption{" + esc(caption) + "}\n"
            + r"\end{figure}" + "\n\n")


def table(caption: str, header: list, rows: list) -> str:
    # Column types are DERIVED from the data, never assumed from the column
    # count. A fixed per-arity spec assumed columns 3 and 4 of any 4-column
    # table were numeric; the query-set table has prose there and ran 99pt
    # past the right margin. A numeric column gets "r" and takes its natural
    # width; the remaining textwidth is shared among the prose columns in
    # proportion to their longest cell, so nothing overflows.
    NUMERIC = re.compile(r"^[-+]?[\d,]+(\.\d+)?%?$|^\[.*\]$|^n/?a$", re.I)
    body = [[str(c) for c in r] for r in rows]
    cols = list(zip(*body)) if body else []
    kinds = ["r" if col and all(NUMERIC.match(c.strip()) or not c.strip()
                                for c in col) else "p"
             for col in cols]
    if not kinds:
        kinds = ["p"] * len(header)

    # Budget the line exactly, in points, rather than approximately. At the
    # \small size used for tables, Times averages ~5.6pt per character, and
    # every column boundary costs 2*\tabcolsep = 12pt. Leaving these out is
    # what pushed two tables 7pt and 22pt past the margin.
    TW, CHAR, GAP = 434.0, 5.6, 12.0          # textwidth pt, pt/char, pt/gap
    prose = [i for i, k in enumerate(kinds) if k == "p"]
    longest = {i: max([len(header[i])] + [len(c) for c in cols[i]])
               for i in range(len(kinds))}
    fixed = sum(longest[i] * CHAR + 2 for i in range(len(kinds))
                if kinds[i] == "r")
    budget = TW - GAP * (len(kinds) - 1) - fixed
    total = sum(longest[i] for i in prose) or 1
    spec = "".join(
        "r" if kinds[i] == "r"
        else r"p{%.3f\textwidth}" % max(0.10,
                                        budget * longest[i] / total / TW)
        for i in range(len(kinds)))
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
    # "SUM over lists of" must be handled BEFORE the bare "SUM", or the words
    # fall through to math mode and set as one italic variable, "overlistsof".
    b = body.replace("SUM over lists of", BS + "sum_{" + BS + "text{lists}}")
    b = b.replace("<=", r"\leq").replace(">=", r"\geq")
    b = b.replace("SUM", r"\sum").replace("s_top", r"s_{\text{top}}")
    b = re.sub(r"\bs1\b", "s_{1}", b)
    b = re.sub(r"\bs5\b", "s_{5}", b)
    # lambda replacements: a plain string would be read as a regex template,
    # where a lone backslash is an invalid escape.
    # "max" belongs here with "min": omitted, it set as italic "max".
    for w in ("min", "max", "ln"):
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
    # References are set single-spaced. The department format prescribes 1.5
    # line spacing for the BODY; a reference list is conventionally set solid
    # in IEEE style, and at 1.5 it cost most of a page against a 15-page cap.
    out.append(r"\section*{8. References}")
    out.append(r"\begingroup\setstretch{1.0}\footnotesize")
    out.append(r"\begin{enumerate}[label={[\arabic*]},leftmargin=2.4em,"
               r"itemsep=1pt]")
    for ref in T.REFERENCES:
        out.append(r"  \item " + esc(ref))
    out.append(r"\end{enumerate}\endgroup")
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
