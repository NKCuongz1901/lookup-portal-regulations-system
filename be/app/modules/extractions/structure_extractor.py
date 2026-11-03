"""Deterministic structure extraction, independent of SQLAlchemy, R2 and Celery.

``extract_structure(normalize_pages(parse_pdf(pdf_bytes)))`` returns canonical
text, intermediate nodes, and rows that fit DocumentSegment. Every row belongs
to one source page; a clause spanning pages keeps its context in separate rows.
Offsets use Python Unicode characters and half-open [start, end) intervals in
``full_text`` (not PDF bytes, raw OCR text, or JavaScript UTF-16 offsets).
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from app.modules.extractions.structure_rules import (
    is_heading,
    is_list_item,
    match_outline,
    match_structure,
)
from app.modules.extractions.text_normalizer import NormalizedDocument, NormalizedLine


PARSER_VERSION = "structure-1.0"
_LEVELS = ("chapter", "section", "article", "clause", "point")
_PAGE_COUNTER = re.compile(r"^(?:[-–—]\s*)?([0-9]+)(?:\s*[-–—])?$|^Trang\s+([0-9]+)(?:\s*/\s*[0-9]+)?$", re.I)
_DOCUMENT_HEADING = re.compile(r"^(?:QUY CHẾ|QUY ĐỊNH|QUYẾT ĐỊNH|THÔNG BÁO|HƯỚNG DẪN|PHỤ LỤC|ĐƠN|PHIẾU|MẪU)(?:\s|$)")


@dataclass(frozen=True)
class Segment:
    segment_index: int
    page_number: int
    paragraph_index: int  # Zero-based row order within this source page.
    section_title: str | None
    content: str
    char_start: int
    char_end: int


@dataclass(frozen=True)
class StructureNode:
    segment_index: int
    kind: str
    number: str | None
    title: str | None
    source_line_start: int
    source_line_end: int


@dataclass(frozen=True)
class PageSpan:
    page_number: int
    char_start: int
    char_end: int


@dataclass(frozen=True)
class ExtractionResult:
    full_text: str
    segments: tuple[Segment, ...]
    nodes: tuple[StructureNode, ...]
    page_spans: tuple[PageSpan, ...]
    warnings: tuple[str, ...]
    parser_version: str = PARSER_VERSION

    def to_rows(self) -> list[dict[str, Any]]:
        """DocumentSegment fields only; caller supplies document_version_id."""
        return [asdict(segment) for segment in self.segments]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class _Context:
    legal: dict[str, str] = field(default_factory=dict)
    numbers: dict[str, str] = field(default_factory=dict)
    headings: list[tuple[int, str]] = field(default_factory=list)

    def set_legal(self, kind: str, number: str, label: str) -> None:
        self.headings.clear()
        for descendant in _LEVELS[_LEVELS.index(kind):]:
            self.legal.pop(descendant, None)
            self.numbers.pop(descendant, None)
        self.legal[kind] = label
        self.numbers[kind] = number

    def set_heading(self, level: int, label: str) -> None:
        self.headings = [(depth, text) for depth, text in self.headings if depth < level]
        self.headings.append((level, label))

    def title(self) -> str | None:
        labels = [self.legal[key] for key in _LEVELS if key in self.legal]
        labels.extend(text for _, text in self.headings)
        return " / ".join(labels) or None

    def body_kind(self) -> tuple[str, str | None]:
        for kind in ("point", "clause"):
            if kind in self.numbers:
                return kind, self.numbers[kind]
        return "paragraph", None


@dataclass
class _Draft:
    kind: str
    number: str | None
    title: str | None
    section_title: str | None
    lines: list[NormalizedLine]


def _counter(text: str, page_number: int, index: int, line_count: int) -> bool:
    if index not in (0, line_count - 1):
        return False
    match = _PAGE_COUNTER.fullmatch(text)
    return bool(match and int(match[1] or match[2]) == page_number)


def _header_lines(lines: tuple[NormalizedLine, ...], index: int, *, bare: bool) -> tuple[list[NormalizedLine], int]:
    """Keep wrapped titles, conservatively; never consume a following marker."""
    collected = [lines[index]]
    cursor = index + 1
    while cursor < len(lines) and len(collected) < 4:
        following = lines[cursor]
        previous = collected[-1].text
        if following.paragraph_break_before or match_structure(following.text) or match_outline(following.text) or is_list_item(following.text):
            break
        if re.match(r"^(?:https?://|www\.)", following.text, re.I):
            break
        standalone_title = bare and len(collected) == 1 and (
            is_heading(following.text) or (
                len(following.text) <= 160 and not following.text.endswith((".", ";", ":", "!", "?"))
                and cursor + 1 < len(lines) and match_structure(lines[cursor + 1].text) is not None
            )
        )
        continuation = not previous.endswith((".", ";", ":", "!", "?")) and following.text[0].islower()
        if not (standalone_title or continuation):
            break
        collected.append(following)
        cursor += 1
    return collected, cursor


def extract_structure(document: NormalizedDocument) -> ExtractionResult:
    """Flatten legal or fallback structure while preserving all normalized text.

    These are text-based heuristics, not a reconstruction of table cells or
    typography. Generic headings and lists remain ``heading`` / ``list_item``;
    only an active article allows ``clause`` and ``point`` nodes.
    """
    segments: list[Segment] = []
    nodes: list[StructureNode] = []
    spans: list[PageSpan] = []
    chunks: list[str] = []
    warnings: list[str] = []
    offset = 0
    context = _Context()

    for page_index, page in enumerate(document.pages):
        if page_index:
            chunks.append("\n\f\n")
            offset += 3
        page_start = offset
        page_row = 0
        pending: _Draft | None = None

        def emit(draft: _Draft) -> None:
            nonlocal offset, page_row
            content = " ".join(line.text for line in draft.lines)
            if page_row:
                chunks.append("\n\n")
                offset += 2
            title = draft.section_title
            if title and len(title) > 500:
                warnings.append(f"section_title truncated to 500 characters on page {page.page_number}, row {page_row}")
                title = title[:350] + " … " + title[-147:]
            row_index = len(segments)
            segments.append(Segment(row_index, page.page_number, page_row, title, content, offset, offset + len(content)))
            nodes.append(StructureNode(row_index, draft.kind, draft.number, draft.title, draft.lines[0].source_line, draft.lines[-1].source_line))
            chunks.append(content)
            offset += len(content)
            page_row += 1

        def flush() -> None:
            nonlocal pending
            if pending is not None:
                emit(pending)
                pending = None

        index = 0
        while index < len(page.lines):
            line = page.lines[index]
            match = match_structure(line.text)
            if _counter(line.text, page.page_number, index, len(page.lines)):
                flush()
                emit(_Draft("page_marker", None, None, None, [line]))
                index += 1
                continue

            if match and match.kind in ("chapter", "section", "article"):
                flush()
                header, index = _header_lines(page.lines, index, bare=not match.title)
                label = " ".join(item.text for item in header)
                context.set_legal(match.kind, match.number, label)
                emit(_Draft(match.kind, match.number, label, context.title(), header))
                continue

            if match and match.kind in ("clause", "point") and "article" in context.legal:
                flush()
                label = f"{'Khoản' if match.kind == 'clause' else 'Điểm'} {match.number}"
                context.set_legal(match.kind, match.number, label)
                pending = _Draft(match.kind, match.number, label, context.title(), [line])
                index += 1
                continue

            outline = match_outline(line.text) if "article" not in context.legal else None
            document_heading = bool(_DOCUMENT_HEADING.match(line.text))
            # Uppercase table labels such as STT / TÊN ĐỐI TƯỢNG must not
            # replace a numbered outline's context.
            in_outline = any(depth > 0 for depth, _ in context.headings)
            generic_heading = is_heading(line.text) and (
                document_heading or ("article" not in context.legal and not in_outline)
            )
            if outline or generic_heading:
                flush()
                if _DOCUMENT_HEADING.match(line.text):
                    context = _Context()
                header, index = _header_lines(page.lines, index, bare=False)
                label = " ".join(item.text for item in header)
                number, level = outline if outline else (None, 0)
                context.set_heading(level, label)
                emit(_Draft("heading", number, label, context.title(), header))
                continue

            new_list = bool(match and match.kind in ("clause", "point")) or is_list_item(line.text)
            previous_sentence_ended = pending is not None and pending.lines[-1].text.endswith((".", ";", "!", "?")) and line.text[0].isupper()
            if line.paragraph_break_before or new_list or previous_sentence_ended:
                flush()
            if pending is None:
                kind, number = context.body_kind()
                if new_list:
                    kind, number = "list_item", match.number if match else None
                pending = _Draft(kind, number, None, context.title(), [])
            pending.lines.append(line)
            index += 1
        flush()
        spans.append(PageSpan(page.page_number, page_start, offset))
    if not any(node.kind in ("chapter", "section", "article") for node in nodes):
        warnings.append("No legal headings found; used outline/heading/paragraph fallback")
    return ExtractionResult("".join(chunks), tuple(segments), tuple(nodes), tuple(spans), tuple(warnings))
