"""Offline contracts for segment persistence helpers (no database)."""
from app.modules.extractions.segment_service import SEGMENT_FIELDS
from app.modules.extractions.structure_extractor import extract_structure
from app.modules.extractions.text_normalizer import normalize_pages


def test_to_rows_fields_match_persistence_contract():
    result = extract_structure(normalize_pages([
        {"page_number": 1, "content": "Điều 1. Phạm vi\n1. Áp dụng cho sinh viên."},
    ]))
    rows = result.to_rows()
    assert rows
    for row in rows:
        assert set(SEGMENT_FIELDS) <= set(row)
        assert row["content"].strip()
        assert row["char_end"] > row["char_start"]
