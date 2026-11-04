from __future__ import annotations

import re
from datetime import date
from collections.abc import Iterator


# Optional whitespace tolerates common OCR joins without rewriting source text.
DATE = r"(?:ngày\s*)?(?:\d{1,2}\s*[/\-]\s*\d{1,2}\s*[/\-]\s*\d{4}|\d{1,2}\s*tháng\s*\d{1,2}\s*năm\s*\d{4})"
_NUMERIC_DATE = re.compile(r"(?:ngày\s*)?(\d{1,2})\s*[/\-]\s*(\d{1,2})\s*[/\-]\s*(\d{4})", re.I)
_WORD_DATE = re.compile(r"(?:ngày\s*)?(\d{1,2})\s*tháng\s*(\d{1,2})\s*năm\s*(\d{4})", re.I)
_PROTECTED = re.compile(r"https?://\S+|www\.\S+|\b(?:TP|ThS|TS|PGS|GS|v\.v)\.", re.I)
_BOUNDARY = re.compile(r"[;!?]|(?<!\d)\.(?=\s|$)|(?<=\d)\.(?!\d)(?=\s|$)|\n(?=\s*(?:[-–—•+]|\d+[.)]|[a-zđ]\))\s)")


def parse_date(value: str) -> str | None:
    match = _NUMERIC_DATE.fullmatch(value.strip()) or _WORD_DATE.fullmatch(value.strip())
    if not match:
        return None
    try:
        return date(int(match[3]), int(match[2]), int(match[1])).isoformat()
    except ValueError:
        return None


def clean(value: str) -> str:
    """For normalized values only. Never use these positions as evidence offsets."""
    return " ".join(value.split()).strip(" ;.\n")


def sentences(text: str) -> Iterator[tuple[int, int, str]]:
    """Keep dates, decimals and URLs intact; retain positions in the input."""
    protected = [(m.start(), m.end()) for m in _PROTECTED.finditer(text)]
    start = 0
    for match in _BOUNDARY.finditer(text):
        if any(a <= match.start() < b for a, b in protected):
            continue
        end = match.start()
        a, b = trim_span(text, start, end)
        if a < b:
            yield a, b, text[a:b]
        start = match.end()
    a, b = trim_span(text, start, len(text))
    if a < b:
        yield a, b, text[a:b]


def trim_span(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def negated(prefix: str) -> bool:
    return bool(re.search(r"(?:không|chưa|không\s*cần|không\s*bắt\s*buộc|có\s*thể|có)\s*$", prefix, re.I))
