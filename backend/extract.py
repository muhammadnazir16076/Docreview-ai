"""PDF/DOCX se text, paragraphs, pages aur heading candidates nikalta hai (with OCR fallback for scanned PDFs)."""
import io
import re
from statistics import median

import fitz  # PyMuPDF
from docx import Document

try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False

HEADING_RE = re.compile(r"^(\d+(\.\d+)*\.?\s+)?[A-Z][A-Za-z0-9 ,:&/\-]{2,60}$")


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _ocr_pdf_pages(doc: fitz.Document) -> tuple[list[str], list[str]]:
    """Render PDF pages to images and run Tesseract OCR."""
    if not OCR_AVAILABLE:
        raise RuntimeError(
            "Scanned PDF detected, but Tesseract OCR is not installed on the server."
        )
    paragraphs, headings = [], []
    for page in doc:
        # 200 DPI provides clean OCR accuracy without excessive memory usage
        pix = page.get_pixmap(dpi=200)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        raw_text = pytesseract.image_to_string(img)
        for chunk in re.split(r"\n\s*\n", raw_text):
            cleaned = _clean(chunk)
            if not cleaned:
                continue
            if len(cleaned.split()) <= 8 and HEADING_RE.match(cleaned):
                headings.append(cleaned)
            else:
                paragraphs.append(cleaned)
    return paragraphs, headings


def extract_pdf(data: bytes) -> dict:
    doc = fitz.open(stream=data, filetype="pdf")
    paragraphs, headings, sizes, lines = [], [], [], []
    for page in doc:
        for block in page.get_text("dict")["blocks"]:
            if block.get("type") != 0:
                continue
            block_text = []
            for line in block["lines"]:
                spans = [s for s in line["spans"] if s["text"].strip()]
                if not spans:
                    continue
                text = _clean(" ".join(s["text"] for s in spans))
                size = max(s["size"] for s in spans)
                bold = any(s["flags"] & 16 for s in spans)
                sizes.append(size)
                lines.append((text, size, bold))
                block_text.append(text)
            if block_text:
                paragraphs.append(" ".join(block_text))

    body = median(sizes) if sizes else 11
    for text, size, bold in lines:
        short = len(text.split()) <= 10
        if short and HEADING_RE.match(text) and (size >= body * 1.15 or (bold and size >= body)):
            headings.append(text)

    # Check if text layer is virtually empty (scanned PDF) -> run OCR fallback
    extracted_words = sum(len(p.split()) for p in paragraphs)
    ocr_used = False
    if extracted_words < 40 and len(doc) > 0:
        ocr_paras, ocr_headings = _ocr_pdf_pages(doc)
        if sum(len(p.split()) for p in ocr_paras) > extracted_words:
            paragraphs = ocr_paras
            headings = ocr_headings
            ocr_used = True

    return {
        "paragraphs": paragraphs,
        "headings": headings,
        "pages": len(doc),
        "ocr_used": ocr_used,
    }


def extract_docx(data: bytes) -> dict:
    doc = Document(io.BytesIO(data))
    paragraphs, headings = [], []
    for p in doc.paragraphs:
        text = _clean(p.text)
        if not text:
            continue
        style = (p.style.name or "").lower() if p.style is not None else ""
        if style.startswith("heading") or style == "title":
            headings.append(text)
        else:
            paragraphs.append(text)
    words = sum(len(p.split()) for p in paragraphs)
    return {
        "paragraphs": paragraphs,
        "headings": headings,
        "pages": max(1, round(words / 450)),
        "ocr_used": False,
    }


def extract(filename: str, data: bytes) -> dict:
    ext = filename.lower().rsplit(".", 1)[-1]
    result = extract_pdf(data) if ext == "pdf" else extract_docx(data)
    paras = [p for p in result["paragraphs"] if len(p.split()) >= 3]
    if not result["headings"]:
        result["headings"] = [p for p in paras if len(p.split()) <= 6 and HEADING_RE.match(p)]
    result["paragraphs"] = paras
    result["text"] = "\n\n".join(result["headings"] + paras)
    return result
