"""Conservative, line-anchored rules; hierarchy is decided by the extractor."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


StructureKind = Literal["chapter", "section", "article", "clause", "point"]


@dataclass(frozen=True)
class StructureMatch:
    kind: StructureKind
    number: str
    title: str
    start: int
    end: int


_HEADINGS: tuple[tuple[StructureKind, re.Pattern[str]], ...] = (
    ("chapter", re.compile(r"^Chương\s+(?P<number>[IVXLCDM]+|[0-9]+)(?=$|[\s.:–—-])(?P<tail>.*)$", re.I)),
    ("section", re.compile(r"^Mục\s+(?P<number>[0-9]+|[IVXLCDM]+)(?=$|[\s.:–—-])(?P<tail>.*)$", re.I)),
    ("article", re.compile(r"^Điều\s+(?P<number>[0-9]+[a-zđ]?)(?=$|[\s.:–—-])(?P<tail>.*)$", re.I)),
)
_CLAUSE = re.compile(r"^(?P<number>[1-9][0-9]*)\.\s+(?P<title>.+)$|^(?P<bare>[1-9][0-9]*)\.$")
_POINT = re.compile(r"^(?P<number>[a-zđ])\)\s*(?P<title>.*)$", re.I)
_BULLET = re.compile(r"^(?:[-–—•●▪]|[IVXLCDM]+\.)\s+\S")
_OUTLINE = re.compile(r"^(?P<number>[IVXLCDM]+|[0-9]+(?:\.[0-9]+)+)\.?\s+(?P<title>.+)$")


def match_structure(line: str) -> StructureMatch | None:
    """Recognize normalized lines, including headings without a title.

    Offsets refer to this line, not to the original PDF or final full text.
    A title without a separator must start with an uppercase letter; this
    avoids treating references such as 'Điều 5 của Quy chế...' as headings.
    """
    for kind, pattern in _HEADINGS:
        match = pattern.fullmatch(line)
        if match is None:
            continue
        tail = match["tail"].strip()
        if re.match(r"^\.[0-9]", tail):
            return None  # A reference such as Mục 2.4 is not Mục 2.
        if tail and tail[0] not in ".:–—-" and not tail[0].isupper():
            return None
        title = tail.lstrip(".:–—- ")
        number = match["number"]
        number = number.upper() if kind in {"chapter", "section"} else number.lower()
        return StructureMatch(kind, number, title, match.start(), match.end())
    for kind, pattern in (("clause", _CLAUSE), ("point", _POINT)):
        match = pattern.fullmatch(line)
        if match:
            groups = match.groupdict()
            number = groups.get("number") or groups["bare"]
            return StructureMatch(kind, number.lower(), groups.get("title") or "", match.start(), match.end())
    return None


def is_heading(line: str) -> bool:
    """Fallback for short uppercase headings in notices and other prose."""
    letters = [character for character in line if character.isalpha()]
    return 3 <= len(letters) and len(line) <= 180 and all(character.isupper() for character in letters)


def is_list_item(line: str) -> bool:
    return bool(_BULLET.match(line))


def match_outline(line: str) -> tuple[str, int] | None:
    """Numbered headings in non-legal documents, not legal clauses.

    Require an uppercase textual title, so decimal values in tables (19.5,
    21.5 ; 23, 1.000 đồng) do not become headings. Level 1 includes Roman
    headings; 2.1 and 2.1.1 have levels 2 and 3 respectively.
    """
    match = _OUTLINE.fullmatch(line)
    if match and match["title"][0].isupper():
        number = match["number"]
        return number, number.count(".") + 1
    match = _CLAUSE.fullmatch(line)
    if match and match.groupdict().get("title"):
        title = match["title"]
        if title[0].isupper() and len(line) <= 180 and (line.endswith(":") or is_heading(title)):
            return match["number"], 1
    return None
