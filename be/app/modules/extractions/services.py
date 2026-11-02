"""PDF text extraction via PyMuPDF (+ Tesseract OCR when needed)."""
from __future__ import annotations

import os
from typing import Any

import pymupdf

# macOS Homebrew default; override with TESSDATA_PREFIX if different.
DEFAULT_TESSDATA = os.environ.get(
    "TESSDATA_PREFIX",
    "/usr/local/share/tessdata",
)
OCR_LANGUAGE = "vie+eng"
MIN_TEXT_CHARS = 40


def needs_ocr(page: pymupdf.Page, text: str) -> bool:
    """OCR when the text layer is weak but the page looks image-heavy."""
    if len(text.strip()) >= MIN_TEXT_CHARS:
        return False
    if page.get_images():
        return True
    return len(text.strip()) == 0


def extract_page_text(page: pymupdf.Page, *, tessdata: str = DEFAULT_TESSDATA) -> str:
    text = page.get_text("text").strip()
    if not needs_ocr(page, text):
        return text

    textpage = page.get_textpage_ocr(
        language=OCR_LANGUAGE,
        dpi=200,
        full=True,
        tessdata=tessdata,
    )
    return page.get_text("text", textpage=textpage).strip()


def parse_pdf(pdf_bytes: bytes, *, tessdata: str = DEFAULT_TESSDATA) -> list[dict[str, Any]]:
    """
    Return one segment-like dict per page.

    Shape aligns with DocumentSegment fields (without document_version_id).
    """
    if not pdf_bytes.startswith(b"%PDF"):
        raise ValueError("Not a PDF file")

    results: list[dict[str, Any]] = []
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        for index, page in enumerate(doc):
            content = extract_page_text(page, tessdata=tessdata)
            results.append(
                {
                    "segment_index": index,
                    "page_number": index + 1,
                    "paragraph_index": None,
                    "section_title": None,
                    "content": content,
                    "char_start": None,
                    "char_end": None,
                }
            )
    return results
