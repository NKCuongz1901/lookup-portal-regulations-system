"""Field correctness and source attribution, independent of PDF/R2/DB services."""
from dataclasses import replace

import pytest

from app.modules.extractions.field_extractor import extract_fields
from app.modules.extractions.field_types import FieldSegment, RULE_VERSION


def fields(text, key):
    result = extract_fields([FieldSegment(0, text, 302, 3)])
    audit(result, [FieldSegment(0, text, 302, 3)])
    return [candidate for candidate in result.candidates if candidate.field_key == key]


def audit(result, segments):
    source = {row.segment_index: row for row in segments}
    per_field = {}
    for item in result.candidates:
        assert item.item_index == per_field.get(item.field_key, 0)
        per_field[item.field_key] = item.item_index + 1
        assert item.review_status == "pending"
        assert item.rule_version == RULE_VERSION
        assert item.evidences
        for evidence in item.evidences:
            row = source[evidence.segment_index]
            assert row.id == evidence.document_segment_id
            assert row.page_number == evidence.page_number
            assert row.section_title == evidence.section_title
            assert 0 <= evidence.start_offset < evidence.end_offset <= len(row.content)
            assert row.content[evidence.start_offset:evidence.end_offset] == evidence.quote
        value = [e.quote for e in item.evidences if e.role == "value" and e.occurrence_index == 0]
        assert "\n".join(value) == item.raw_value


@pytest.mark.parametrize("text, expected, boundary", [
    ("Nộp hồ sơ trước ngày 15/12/2026.", "2026-12-15", "before"),
    ("Chậm nhất ngày 5-1-2027 nộp hồ sơ.", "2027-01-05", "on_or_before"),
    ("Không muộn hơn ngày 29/02/2028.", "2028-02-29", "on_or_before"),
    ("Hạn chót là ngày 15 tháng 12 năm 2026.", "2026-12-15", "on_or_before"),
    ("Hạn nộp hồ sơ: 15/12/2026.", "2026-12-15", "on_or_before"),
    ("Nộp trướcngày15/12/2026.", "2026-12-15", "before"),
    ("Nhận hồ sơ đến hết ngày 01/09/2026.", "2026-09-01", "on_or_before"),
])
def test_absolute_dates(text, expected, boundary):
    found = fields(text, "deadline")
    assert len(found) == 1
    assert found[0].normalized_value == {"kind": "absolute", "date": expected, "boundary": boundary}


@pytest.mark.parametrize("text", [
    "Ngày ban hành 01/09/2026.", "Theo Quyết định số 15/QĐ-ĐH ngày 01/09/2026.",
    "Nộp trước ngày 31/02/2026.", "Nộp trước 29/02/2027.",
    "Nộp trước 15/13/2026.", "Nộp trước 00/12/2026.",
    "Nộp trước ngày 15/12.", "Nộp trước 15/12/20260.",
    "Từ 20/03/2026, thí sinh đăng ký nguyện vọng.",
    "Thời gian thi: 20-21/06/2026.", "Làm bài trong 50 phút.",
    "Đăng ký tại trường. Thời gian thi: 20-21/06/2026.",
])
def test_no_invented_deadlines(text):
    assert not fields(text, "deadline")


@pytest.mark.parametrize("text, start, end", [
    ("Nộp từ ngày 01/09/2026 đến ngày 15/09/2026.", "2026-09-01", "2026-09-15"),
    ("Đăng ký từ 01/09 đến 15/09/2026.", "2026-09-01", "2026-09-15"),
    ("Nhận hồ sơ 02/07- 14/07/2026.", "2026-07-02", "2026-07-14"),
    ("Nộp hồ sơ từ ngày 20–21/06/2026.", "2026-06-20", "2026-06-21"),
])
def test_date_intervals(text, start, end):
    found = fields(text, "deadline")
    assert len(found) == 1
    assert found[0].normalized_value["start_date"] == start
    assert found[0].normalized_value["end_date"] == end


@pytest.mark.parametrize("text", [
    "Nộp từ 31/02 đến 15/03/2026.", "Nộp từ 20/12 đến 10/01/2026.",
    "Nộp từ 20/09/2026 đến 10/09/2026.",
])
def test_invalid_or_ambiguous_date_ranges(text):
    assert not fields(text, "deadline")


def test_relative_date_keeps_anchor_and_does_not_calculate_due_date():
    found = fields("Nộp hồ sơ trong vòng 15 ngày làm việc kể từ ngày nhận thông báo.", "deadline")
    assert found[0].normalized_value == {
        "kind": "relative", "amount": 15, "unit": "day", "working_days": True,
        "anchor_text": "ngày nhận thông báo",
    }
    assert "date" not in found[0].normalized_value
    assert fields("Hoàn thành trong 2 tháng.", "deadline")[0].normalized_value["anchor_text"] is None


def test_recurring_ocr_join_and_multiple_deadlines():
    found = fields("Nộp đơn vào cuối mỗi học kỳcủa năm học.", "deadline")
    assert found[0].normalized_value == {"kind": "recurring", "position": "cuối", "period": "semester"}
    found = fields("Nộp đơn trước 15/12/2026 và nộp phí trước 20/12/2026.", "deadline")
    assert [c.normalized_value["date"] for c in found] == ["2026-12-15", "2026-12-20"]
    assert [c.item_index for c in found] == [0, 1]


@pytest.mark.parametrize("text", [
    "Sinh viên không phải nộp hồ sơ.", "Sinh viên không bắt buộc phải nộp ảnh.",
    "Sinh viên có thể phải nộp bổ sung.", "Có phải sinh viên phải nộp hồ sơ?",
    "Sinh viên phải chăng đã nộp hồ sơ?", "Sinh viên không phải là người nộp đơn.",
    "Sinh viên được phép nộp hồ sơ.", "Điểm xét tuyển phải đạt 18.0 điểm.",
])
def test_no_false_obligations(text):
    assert not fields(text, "obligation")


@pytest.mark.parametrize("text", [
    "Sinh viên phải nộp hồ sơ.", "Người học có trách nhiệm cung cấp thông tin chính xác.",
    "Thí sinh bắt buộc phải tham gia kỳ thi.", "Phải nộp đủ giấy tờ.",
    "Phòng Công tác sinh viên có trách nhiệm tiếp nhận hồ sơ.",
])
def test_explicit_obligations(text):
    found = fields(text, "obligation")
    assert len(found) == 1
    assert found[0].normalized_value["requirement"]


def test_positive_and_negative_obligations_in_same_sentence():
    found = fields("Sinh viên không phải nộp ảnh nhưng phải nộp hồ sơ.", "obligation")
    assert len(found) == 1
    assert found[0].raw_value == "phải nộp hồ sơ"
    assert found[0].normalized_value["subject"] == "Sinh viên"
    assert any("không phải nộp ảnh" in e.quote for e in found[0].evidences if e.role == "context")


def test_multiple_actors_and_parenthetical_requirement():
    found = fields("Sinh viên phải nộp đơn, nhà trường có trách nhiệm tiếp nhận.", "obligation")
    assert len(found) == 2
    assert "nhà trường" not in found[0].raw_value
    found = fields("Thí sinh ĐKXT trực tuyến trên Cổng thông tin của Bộ GDĐT (bắt buộc).", "obligation")
    assert len(found) == 1
    assert "ĐKXT trực tuyến" in found[0].normalized_value["requirement"]


def test_subject_markers_and_negation():
    found = fields("Đối tượng: Áp dụng cho sinh viên thuộc hộ nghèo.", "applicable_subject")
    assert len(found) == 1
    assert found[0].normalized_value["text"] == "sinh viên thuộc hộ nghèo"
    assert not fields("Không áp dụng cho sinh viên đã tốt nghiệp.", "applicable_subject")
    assert not fields("Đối tượng áp dụng:", "applicable_subject")
    assert not fields("Sinh viên hỏi về việc đăng ký.", "applicable_subject")


def test_subject_value_stops_before_another_label():
    found = fields("Kỳ thi áp dụng cho thí sinh đăng ký môn Vẽ. Thời gian thi: 20/06/2026.", "applicable_subject")
    assert len(found) == 1
    assert "Thời gian" not in found[0].raw_value
    found = fields("Áp dụng cho thí sinh đăng ký môn Vẽ Thông tin chi tiết về kỳ thi: - Thời gian thi: 20/06/2026.", "applicable_subject")
    assert found[0].normalized_value["text"] == "thí sinh đăng ký môn Vẽ"


def test_heading_context_uses_real_heading_evidence_and_resets():
    title = "Điều 1. Đối tượng áp dụng"
    rows = [FieldSegment(0, title, 10, 1, title),
            FieldSegment(1, "- Sinh viên thuộc hộ nghèo.", 11, 1, title),
            FieldSegment(2, "- Người đã tốt nghiệp THPT.", 12, 2, title),
            FieldSegment(3, "Điều 2. Thủ tục", 13, 2, "Điều 2. Thủ tục"),
            FieldSegment(4, "Sinh viên phải nộp đơn.", 14, 2, "Điều 2. Thủ tục")]
    result = extract_fields(rows)
    audit(result, rows)
    subjects = [c for c in result.candidates if c.field_key == "applicable_subject"]
    assert len(subjects) == 2
    assert all(any(e.document_segment_id == 10 and e.role == "context" for e in c.evidences) for c in subjects)


def test_legal_clause_inherits_subject_article_heading():
    from app.modules.extractions.structure_extractor import extract_structure
    from app.modules.extractions.text_normalizer import normalize_pages

    structure = extract_structure(normalize_pages([{"page_number": 1, "content":
        "Điều 1. Đối tượng áp dụng\n1. Sinh viên thuộc hộ nghèo.\n2. Người học thuộc diện bảo trợ.\n"
        "Điều 2. Hồ sơ\n1. Sinh viên cần chuẩn bị giấy xác nhận."}]))
    result = extract_fields(structure.to_rows())
    subjects = [c for c in result.candidates if c.field_key == "applicable_subject"]
    assert len(subjects) == 2
    assert all(any(e.segment_index == 0 and e.role == "context" for e in c.evidences) for c in subjects)


@pytest.mark.parametrize("text, kind, number, issue_date", [
    ("Căn cứ Nghị định số 81/2021/NĐ-CP ngày 27/8/2021 của Chính phủ;", "decree", "81/2021/NĐ-CP", "2021-08-27"),
    ("Căn cứNghịđịnh 81/ND-CP ngày 27/8/2021 của Thủtướng Chính phủ.", "decree", "81/ND-CP", "2021-08-27"),
    ("Theo Thông tư số 08/2021/TT-BGDĐT ngày 18 tháng 3 năm 2021.", "circular", "08/2021/TT-BGDĐT", "2021-03-18"),
    ("Theo Luật Giáo dục năm 2019.", "law", None, None),
])
def test_legal_references(text, kind, number, issue_date):
    found = fields(text, "legal_basis")
    assert len(found) == 1
    value = found[0].normalized_value
    assert (value["document_type"], value["document_number"], value["issue_date"]) == (kind, number, issue_date)
    assert not fields(text, "deadline")


@pytest.mark.parametrize("text", ["Căn cứ xét tuyển: điểm thi THPT.", "Theo quy định của nhà trường.", "Căn cứ vào kế hoạch năm học."])
def test_no_generic_text_as_legal_instrument(text):
    assert not fields(text, "legal_basis")


def test_cross_page_provenance_with_counter_and_emoji():
    title = "Điều 5. Hồ sơ"
    rows = [FieldSegment(0, "📄 Sinh viên phải nộp hồ sơ trước ngày", 10, 1, title),
            FieldSegment(1, "1", 11, 1),
            FieldSegment(2, "15/12/2026.", 12, 2, title)]
    result = extract_fields(reversed(rows), document_version_id=7)
    audit(result, rows)
    assert result.document_version_id == 7
    assert {c.field_key for c in result.candidates} == {"deadline", "obligation"}
    for candidate in result.candidates:
        assert {e.document_segment_id for e in candidate.evidences if e.role == "value"} == {10, 12}


@pytest.mark.parametrize("change", ["section", "page_gap", "index_gap", "new_list"])
def test_no_join_across_unrelated_boundaries(change):
    first = FieldSegment(0, "Sinh viên phải nộp hồ sơ trước ngày", 10, 1, "Điều 1. Hồ sơ")
    second = FieldSegment(1, "15/12/2026.", 11, 2, first.section_title)
    if change == "section": second = replace(second, section_title="Điều 2. Lệ phí")
    if change == "page_gap": second = replace(second, page_number=4)
    if change == "index_gap": second = replace(second, segment_index=4)
    if change == "new_list": second = replace(second, content="- 15/12/2026.")
    assert not any(c.field_key == "deadline" for c in extract_fields([first, second]).candidates)


def test_page_counter_does_not_bridge_missing_segments():
    rows = [FieldSegment(0, "Nộp hồ sơ trước ngày", 1, 1),
            FieldSegment(10, "1", 2, 1), FieldSegment(11, "15/12/2026.", 3, 2)]
    assert not any(c.field_key == "deadline" for c in extract_fields(rows).candidates)


def test_dedup_keeps_all_occurrences_but_distinct_actions_and_conditions():
    rows = [FieldSegment(0, "Nộp đơn trước 15/12/2026.", 10, 1),
            FieldSegment(1, "Nộp đơn trước 15/12/2026.", 11, 2),
            FieldSegment(2, "Nộp phí trước 15/12/2026.", 12, 2)]
    result = extract_fields(rows)
    audit(result, rows)
    assert len(result.candidates) == 2
    assert {e.document_segment_id for e in result.candidates[0].evidences} == {10, 11}
    assert {e.occurrence_index for e in result.candidates[0].evidences} == {0, 1}


def test_missing_ids_empty_results_and_determinism():
    rows = [{"segment_index": 0, "page_number": 1, "content": "Nộp trước ngày 15/12/2026."}]
    result = extract_fields(rows)
    assert result.to_dict() == extract_fields(rows).to_dict()
    assert result.warnings
    assert all(e.document_segment_id is None for c in result.candidates for e in c.evidences)
    assert not extract_fields([]).candidates
    assert not extract_fields([FieldSegment(0, "Nội dung thông thường.", 1)]).candidates


@pytest.mark.parametrize("rows", [
    [FieldSegment(0, "a"), FieldSegment(0, "b")],
    [FieldSegment(0, "a", 1), FieldSegment(1, "b", 1)],
    [FieldSegment(-1, "a")], [FieldSegment(True, "a")],
    [FieldSegment(0, " ")], [FieldSegment(0, None)],
    [FieldSegment(0, "a", page_number=0)],
])
def test_invalid_inputs(rows):
    with pytest.raises(ValueError):
        extract_fields(rows)


def test_real_admissions_excerpt_keeps_registration_window_context():
    text = ("Thí sinh ĐKXT trực tuyến trên Cổng thông tin tuyển sinh của Bộ GDĐT (bắt buộc). "
            "Thí sinh chọn căn cứ để xét tuyển bao gồm: Thứ tự nguyện vọng; "
            "Mã trường KTD – Trường Đại học Kiến trúc Đà Nẵng; Mã xét tuyển (Mã ngành). 02/07- 14/07/2026")
    found = fields(text, "deadline")
    assert len(found) == 1
    assert found[0].normalized_value["end_date"] == "2026-07-14"
    assert any("ĐKXT" in e.quote or "căn cứ" in e.quote for e in found[0].evidences if e.role == "context")


def test_real_tuition_ocr_retains_literal_source_and_recurring_deadline():
    text = ("Vềchếđộgiảm học phí đối với sinh viên Căn cứNghịđịnh 81/ND-CP ngày 27/8/2021 "
            "của Thủtướng Chính phủ; Đơn xin xét giảm học phí thực hiệntheo mẫu của Nhà trường "
            "vào cuối mỗi học kỳ của năm học.")
    rows = [FieldSegment(0, text, 31, 3)]
    result = extract_fields(rows)
    audit(result, rows)
    assert {c.field_key for c in result.candidates} == {"deadline", "legal_basis"}
    assert "Nghịđịnh 81/ND-CP" in next(c.raw_value for c in result.candidates if c.field_key == "legal_basis")
