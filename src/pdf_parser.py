"""
PDF parsing: type detection, OCR, table extraction, metadata tagging.
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

CLAUSE_RE = re.compile(r"^(\d+(?:\.\d+)+)\s")


def detect_pdf_type(path: str | Path) -> str:
    """Return 'scanned' if the PDF has no usable text layer, else 'text'."""
    from src.config import cfg

    doc = fitz.open(str(path))
    total_chars = sum(len(page.get_text("text")) for page in doc)
    avg = total_chars / max(len(doc), 1)
    doc.close()
    threshold = cfg.get("pdf", {}).get("scanned_text_threshold", 50)
    result = "scanned" if avg < threshold else "text"
    logger.info("PDF type detected: %s (avg chars/page=%.1f)", result, avg)
    return result


def _page_to_image(page: fitz.Page, dpi: int = 200) -> Any:
    """Render a PDF page to a PIL Image."""
    from PIL import Image
    import io

    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
    return Image.open(io.BytesIO(pix.tobytes("png")))


def _ocr_with_paddle(image: Any) -> str:
    """Run PaddleOCR on a PIL image, return plain text."""
    import numpy as np
    from paddleocr import PaddleOCR

    ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
    result = ocr.ocr(np.array(image), cls=True)
    lines = []
    if result and result[0]:
        for line in result[0]:
            lines.append(line[1][0])
    return "\n".join(lines)


def _ocr_with_tesseract(image: Any) -> str:
    """Fallback OCR using pytesseract."""
    import pytesseract

    return pytesseract.image_to_string(image, lang="chi_sim+eng")


def ocr_page(image: Any) -> str:
    """OCR a page image; falls back to Tesseract if PaddleOCR fails."""
    engine = os.getenv("OCR_ENGINE", "paddleocr").lower()
    if engine == "tesseract":
        return _ocr_with_tesseract(image)
    try:
        return _ocr_with_paddle(image)
    except Exception as exc:
        logger.warning("PaddleOCR failed (%s), falling back to Tesseract", exc)
        return _ocr_with_tesseract(image)


def extract_tables(page_image: Any) -> list[dict]:
    """
    Extract tables from a page image using PaddleOCR structure recognition.
    Returns list of dicts with 'markdown' and 'confidence' keys.
    Falls back to empty list with a logged warning on failure.
    """
    try:
        import numpy as np
        from paddleocr import PPStructure

        table_engine = PPStructure(table=True, ocr=True, show_log=False)
        result = table_engine(np.array(page_image))
        tables = []
        for region in result:
            if region.get("type") != "table":
                continue
            html = region.get("res", {}).get("html", "")
            confidence = region.get("score", 0.0)
            if confidence < 0.5:
                logger.warning("table_parse_warning: low confidence %.2f, using raw text", confidence)
                tables.append({"markdown": _html_table_to_markdown(html), "confidence": confidence})
            else:
                tables.append({"markdown": _html_table_to_markdown(html), "confidence": confidence})
        return tables
    except Exception as exc:
        logger.warning("table_parse_warning: table extraction failed (%s)", exc)
        return []


def _html_table_to_markdown(html: str) -> str:
    """Convert an HTML table string to Markdown table format."""
    import re as _re

    rows = _re.findall(r"<tr[^>]*>(.*?)</tr>", html, _re.DOTALL | _re.IGNORECASE)
    md_rows = []
    for i, row in enumerate(rows):
        cells = _re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, _re.DOTALL | _re.IGNORECASE)
        cleaned = [_re.sub(r"<[^>]+>", "", c).strip().replace("\n", " ") for c in cells]
        md_rows.append("| " + " | ".join(cleaned) + " |")
        if i == 0:
            md_rows.append("| " + " | ".join(["---"] * len(cleaned)) + " |")
    return "\n".join(md_rows)


def _extract_clause_id(text: str) -> str:
    """Return the leading clause number (e.g. '4.1') or empty string."""
    m = CLAUSE_RE.match(text.strip())
    return m.group(1) if m else ""


def parse_pdf(path: str | Path) -> list[dict]:
    """
    Parse a PDF and return a list of block dicts.

    Each block contains:
        page       int   1-based page number
        type       str   'text' | 'table'
        source     str   filename
        clause_id  str   e.g. '4.1' or ''
        content    str   extracted text or Markdown table
    """
    path = Path(path)
    source = path.name
    pdf_type = detect_pdf_type(path)
    doc = fitz.open(str(path))
    blocks: list[dict] = []

    # Save raw OCR output for inspection
    from src.config import cfg

    ocr_cache_dir = Path(cfg.get("paths", {}).get("ocr_cache", "data/ocr_cache"))
    ocr_cache_dir.mkdir(parents=True, exist_ok=True)

    for page_num, page in enumerate(doc, start=1):
        if pdf_type == "text":
            raw_text = page.get_text("text")
            paragraphs = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
            for para in paragraphs:
                blocks.append({
                    "page": page_num,
                    "type": "text",
                    "source": source,
                    "clause_id": _extract_clause_id(para),
                    "content": para,
                })
        else:
            image = _page_to_image(page)

            # Cache raw OCR text
            cache_file = ocr_cache_dir / f"{path.stem}_page{page_num:03d}.txt"

            # Extract tables first
            tables = extract_tables(image)
            for tbl in tables:
                blocks.append({
                    "page": page_num,
                    "type": "table",
                    "source": source,
                    "clause_id": "",
                    "content": tbl["markdown"],
                })

            # OCR remaining text
            text = ocr_page(image)
            cache_file.write_text(text, encoding="utf-8")

            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            for para in paragraphs:
                if not para:
                    continue
                blocks.append({
                    "page": page_num,
                    "type": "text",
                    "source": source,
                    "clause_id": _extract_clause_id(para),
                    "content": para,
                })

    doc.close()
    logger.info(
        "Parsed %s: %d blocks (%d text, %d table) from %d pages",
        source,
        len(blocks),
        sum(1 for b in blocks if b["type"] == "text"),
        sum(1 for b in blocks if b["type"] == "table"),
        page_num,
    )
    return blocks
