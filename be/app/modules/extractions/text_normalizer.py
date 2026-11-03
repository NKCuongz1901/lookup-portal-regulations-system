"""Normalize page text without erasing the boundaries needed by the extractor.

No OCR correction, accent removal, header removal, or page renumbering is done.
Wrapped lines are joined only after structural boundaries have been identified.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NormalizedLine:
    text: str
    source_line: int  # One-based physical line in the extracted page text.
    paragraph_break_before: bool = False


@dataclass(frozen=True)
class NormalizedPage:
    page_number: int
    lines: tuple[NormalizedLine, ...]


@dataclass(frozen=True)
class NormalizedDocument:
    pages: tuple[NormalizedPage, ...]


def normalize_pages(pages: Iterable[Mapping[str, Any]]) -> NormalizedDocument:
    """Accept the ``content`` / ``page_number`` dictionaries from parse_pdf.

    Preserve blank-page records and ascending source page numbers, including
    gaps when processing a subset of pages. Reject ambiguous or malformed input
    instead of silently producing incorrect citations.
    """
    result: list[NormalizedPage] = []
    previous_page = 0
    for page in pages:
        number = page.get("page_number")
        content = page.get("content")
        if type(number) is not int or number <= previous_page:
            raise ValueError("page_number must be a positive, strictly increasing integer")
        if not isinstance(content, str):
            raise ValueError("Each page must contain a string content field")
        previous_page = number
        content = unicodedata.normalize("NFC", content)
        content = content.replace("\r\n", "\n").replace("\r", "\n")
        content = content.replace("\u2029", "\n\n").replace("\u2028", "\n").replace("\f", "\n")
        content = content.replace("\ufeff", "").replace("\u200b", "").replace("\u00ad", "")
        lines: list[NormalizedLine] = []
        blank_before = False
        for index, raw in enumerate(content.split("\n"), start=1):
            text = re.sub(r"[^\S\n]+", " ", raw).strip()
            if not text:
                blank_before = True
                continue
            lines.append(NormalizedLine(text, index, blank_before))
            blank_before = False
        result.append(NormalizedPage(number, tuple(lines)))
    return NormalizedDocument(tuple(result))
