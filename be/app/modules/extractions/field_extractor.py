"""Rule extraction over stored segment text; no I/O or source-text rewriting."""
from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from typing import Any

from app.modules.extractions.field_types import (
    FieldCandidate, FieldEvidence, FieldExtractionResult, FieldSegment,
)
from app.modules.extractions.rules.common import clean
from app.modules.extractions.rules.deadline_rules import find_deadlines
from app.modules.extractions.rules.legal_basis_rules import find_legal_bases, is_legal_basis_heading
from app.modules.extractions.rules.obligation_rules import find_obligations
from app.modules.extractions.rules.subject_rules import find_subjects, is_subject_heading
from app.modules.extractions.structure_rules import match_outline, match_structure


_LIST_START = re.compile(r"^\s*(?:[-–—•+]|\d+[.)]|[a-zđ]\)|[IVXLCDM]+\.)\s", re.I)
_PAGE_MARKER = re.compile(r"^(?:[-–—]\s*)?(\d+)(?:\s*[-–—])?$|^Trang\s+(\d+)(?:\s*/\s*\d+)?$", re.I)


@dataclass
class _Block:
    text: str
    spans: list[tuple[int, int, FieldSegment]]
    heading: FieldSegment | None
    is_heading: bool
    basis_heading: FieldSegment | None

    def append(self, segment: FieldSegment) -> None:
        start = len(self.text) + 1
        self.text += "\n" + segment.content
        self.spans.append((start, len(self.text), segment))


def _segments(values: Iterable[FieldSegment | Mapping[str, Any]]) -> list[FieldSegment]:
    rows = []
    for value in values:
        if isinstance(value, FieldSegment):
            row = value
        else:
            row = FieldSegment(**{name: value[name] for name in FieldSegment.__dataclass_fields__ if name in value})
        if type(row.segment_index) is not int or row.segment_index < 0:
            raise ValueError("segment_index must be a nonnegative integer")
        if not isinstance(row.content, str) or not row.content.strip():
            raise ValueError("segment content must be nonempty text")
        for name in ("id", "page_number"):
            value = getattr(row, name)
            if value is not None and (type(value) is not int or value <= 0):
                raise ValueError(f"{name} must be a positive integer or None")
        if row.section_title is not None and not isinstance(row.section_title, str):
            raise ValueError("section_title must be text or None")
        rows.append(row)
    rows.sort(key=lambda row: row.segment_index)
    if len({row.segment_index for row in rows}) != len(rows):
        raise ValueError("duplicate segment_index")
    ids = [row.id for row in rows if row.id is not None]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate segment id")
    return rows


def _blocks(rows: list[FieldSegment]) -> list[_Block]:
    blocks: list[_Block] = []
    heading = None
    basis_heading = None
    previous = None
    for row in rows:
        if basis_heading and (
            previous is None or row.segment_index != previous.segment_index + 1
            or (row.page_number is not None and previous.page_number is not None
                and not 0 <= row.page_number - previous.page_number <= 1)
        ):
            basis_heading = None
        text = row.content.strip()
        counter = _PAGE_MARKER.fullmatch(text)
        if counter and row.page_number == int(counter[1] or counter[2]):
            # A page counter may bridge contiguous rows, never a missing chunk.
            previous = row if previous and row.segment_index == previous.segment_index + 1 else None
            continue
        title = (row.section_title or "").rsplit(" / ", 1)[-1]
        match = match_structure(text)
        is_heading = text == title or bool(match and match.kind in {"chapter", "section", "article"}) or bool(match_outline(text))
        is_heading = is_heading or (len(text) < 150 and is_subject_heading(text) and text.endswith(":") and not _LIST_START.match(text))
        is_heading = is_heading or is_legal_basis_heading(text)
        if is_heading:
            heading = row if is_subject_heading(text) else None
            basis_heading = row if is_legal_basis_heading(text) else None
        elif heading and heading.section_title != row.section_title:
            if not (heading.section_title and (row.section_title or "").startswith(heading.section_title + " / ")):
                heading = None
        if basis_heading and basis_heading.section_title != row.section_title:
            if not (basis_heading.section_title and (row.section_title or "").startswith(basis_heading.section_title + " / ")):
                basis_heading = None
        join = bool(
            blocks and previous and not blocks[-1].is_heading and not is_heading
            and row.segment_index == previous.segment_index + 1
            and row.section_title == blocks[-1].spans[-1][2].section_title
            and (row.page_number is None or blocks[-1].spans[-1][2].page_number is None
                 or 0 <= row.page_number - blocks[-1].spans[-1][2].page_number <= 1)
            and not blocks[-1].text.rstrip().endswith((".", ";", "!", "?", ":"))
            and not _LIST_START.match(text)
            and len(blocks[-1].text) + len(row.content) < 8000
        )
        if join:
            blocks[-1].append(row)
        else:
            blocks.append(_Block(row.content, [(0, len(row.content), row)], heading, is_heading, basis_heading))
        previous = row
    return blocks


def _evidence(block: _Block, start: int, end: int, role: str, occurrence: int) -> list[FieldEvidence]:
    values = []
    for a, b, row in block.spans:
        left, right = max(start, a), min(end, b)
        if left >= right:
            continue
        left, right = left - a, right - a
        values.append(FieldEvidence(row.id, row.segment_index, row.page_number, row.section_title,
                                    left, right, row.content[left:right], role, occurrence))
    return values


def extract_fields(
    segments: Iterable[FieldSegment | Mapping[str, Any]],
    *, document_version_id: int | None = None,
) -> FieldExtractionResult:
    """Return review candidates. This function neither persists nor approves them.

    Join only adjacent, unfinished paragraphs in the same section, preserving a
    character map back to each segment. Exact repeated values in the same textual
    context share a candidate; distinct conditions/actions remain separate.
    """
    if document_version_id is not None and (type(document_version_id) is not int or document_version_id <= 0):
        raise ValueError("document_version_id must be a positive integer")
    rows = _segments(segments)
    candidates: list[FieldCandidate] = []
    seen: dict[tuple, int] = {}
    counts: Counter = Counter()
    for block in _blocks(rows):
        hits = (
            find_deadlines(block.text) + find_obligations(block.text)
            + find_subjects(block.text, subject_context=block.heading is not None and not block.is_heading)
            + find_legal_bases(block.text, basis_context=block.basis_heading is not None and not block.is_heading)
        )
        for hit in sorted(hits, key=lambda item: (item.start, item.field_key, item.end)):
            if not 0 <= hit.context_start <= hit.start < hit.end <= hit.context_end <= len(block.text):
                raise ValueError(f"invalid span from rule {hit.rule_id}")
            raw = block.text[hit.start:hit.end]
            context = block.text[hit.context_start:hit.context_end]
            key = (hit.field_key, clean(raw).casefold(), clean(context).casefold(), block.spans[0][2].section_title)
            old_index = seen.get(key)
            occurrence = 0 if old_index is None else 1 + max(e.occurrence_index for e in candidates[old_index].evidences)
            evidence = _evidence(block, hit.start, hit.end, "value", occurrence)
            if (hit.context_start, hit.context_end) != (hit.start, hit.end):
                evidence.extend(_evidence(block, hit.context_start, hit.context_end, "context", occurrence))
            context_heading = (block.heading if hit.rule_id == "subject.heading_context"
                               else block.basis_heading if hit.rule_id == "legal_basis.heading_context" else None)
            if context_heading:
                row = context_heading
                evidence.append(FieldEvidence(row.id, row.segment_index, row.page_number, row.section_title,
                                              0, len(row.content), row.content, "context", occurrence))
            if old_index is not None:
                old = candidates[old_index]
                candidates[old_index] = replace(old, evidences=old.evidences + tuple(evidence))
            else:
                seen[key] = len(candidates)
                candidates.append(FieldCandidate(hit.field_key, counts[hit.field_key], raw, hit.normalized_value,
                                                 hit.rule_id, tuple(evidence)))
                counts[hit.field_key] += 1
    warnings = []
    if any(row.id is None for row in rows):
        warnings.append("Dry-run segments have no database IDs; evidence uses segment_index until persistence")
    if any("|" in row.content for row in rows):
        warnings.append("Source contains table separators; rules do not reconstruct table cells or repair OCR")
    return FieldExtractionResult(document_version_id, tuple(candidates), len(rows), tuple(warnings))
