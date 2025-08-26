import fitz, pdfplumber, pytesseract
from PIL import Image
from docx import Document
from pathlib import Path
from core.config import LANGS_OCR

def extract_text_pdf(path: str) -> list[tuple[int, str]]:
    pages = []
    with pdfplumber.open(path) as pdf:
        for i, p in enumerate(pdf.pages, start=1):
            t = p.extract_text() or ""
            # OCR fallback if text extraction is poor (e.g., a scanned doc)
            if len(t.strip()) < 20:
                try:
                    pix = fitz.open(path)[i-1].get_pixmap(dpi=300)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    t = pytesseract.image_to_string(img, lang=LANGS_OCR)
                except Exception as e:
                    print(f"OCR failed for page {i}: {e}")
                    t = ""
            pages.append((i, t))
    return pages

def extract_text_docx(path: str) -> list[tuple[int, str]]:
    doc = Document(path)
    text = "\n".join(p.text for p in doc.paragraphs)
    return [(1, text)]

def extract_text_txt(path: str) -> list[tuple[int, str]]:
    return [(1, Path(path).read_text(encoding="utf-8", errors="ignore"))]
