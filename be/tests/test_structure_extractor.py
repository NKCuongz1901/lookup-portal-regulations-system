"""Offline contracts for legal structure, fallback, and source provenance."""
import random
import unicodedata

import pytest

from app.modules.extractions.structure_extractor import extract_structure
from app.modules.extractions.structure_rules import match_outline, match_structure
from app.modules.extractions.text_normalizer import normalize_pages


def extract(*texts):
    return extract_structure(normalize_pages([
        {"page_number": index + 1, "content": text} for index, text in enumerate(texts)
    ]))


def assert_provenance(pages, result):
    normalized = normalize_pages(pages)
    source = "".join(line.text for page in normalized.pages for line in page.lines)
    assert "".join(source.split()) == "".join(result.full_text.split())
    assert [segment.segment_index for segment in result.segments] == list(range(len(result.segments)))
    assert len(result.nodes) == len(result.segments)
    for page in normalized.pages:
        span = next(span for span in result.page_spans if span.page_number == page.page_number)
        rows = [segment for segment in result.segments if segment.page_number == page.page_number]
        assert [row.paragraph_index for row in rows] == list(range(len(rows)))
        covered_lines = []
        for row in rows:
            assert row.content.strip()
            assert result.full_text[row.char_start:row.char_end] == row.content
            assert span.char_start <= row.char_start < row.char_end <= span.char_end
            assert row.section_title is None or len(row.section_title) <= 500
            node = result.nodes[row.segment_index]
            covered_lines.extend(line.source_line for line in page.lines
                                 if node.source_line_start <= line.source_line <= node.source_line_end)
        assert covered_lines == [line.source_line for line in page.lines]
    for before, after in zip(result.segments, result.segments[1:]):
        assert before.char_end < after.char_start


def test_normalize_unicode_whitespace_and_page_provenance_without_joining_markers():
    text = unicodedata.normalize('NFD', '\ufeffĐiều 5. Điều kiện\r\n\t1. Sinh\u00a0viên\r\nhoàn thành\u200b học phần.\r\n\r\na) Nộp hồ sơ.')
    normalized = normalize_pages([{"page_number": 3, "content": text}, {"page_number": 5, "content": " \r\n"}])
    assert [page.page_number for page in normalized.pages] == [3, 5]
    assert [line.text for line in normalized.pages[0].lines] == [
        "Điều 5. Điều kiện", "1. Sinh viên", "hoàn thành học phần.", "a) Nộp hồ sơ.",
    ]
    assert normalized.pages[0].lines[-1].source_line == 5
    assert normalized.pages[0].lines[-1].paragraph_break_before
    assert normalized.pages[1].lines == ()


@pytest.mark.parametrize('pages', [
    [{"content": "text"}], [{"page_number": 0, "content": "text"}],
    [{"page_number": True, "content": "text"}], [{"page_number": 1, "content": None}],
    [{"page_number": 2, "content": "a"}, {"page_number": 1, "content": "b"}],
    [{"page_number": 1, "content": "a"}, {"page_number": 1, "content": "b"}],
])
def test_reject_ambiguous_page_inputs(pages):
    with pytest.raises(ValueError):
        normalize_pages(pages)


@pytest.mark.parametrize(('text', 'kind', 'number', 'title'), [
    ('CHƯƠNG II', 'chapter', 'II', ''),
    ('Chương IV. QUY ĐỊNH CHUNG', 'chapter', 'IV', 'QUY ĐỊNH CHUNG'),
    ('Chương 2: Nội dung', 'chapter', '2', 'Nội dung'),
    ('MỤC 1', 'section', '1', ''),
    ('Mục II. Đào tạo', 'section', 'II', 'Đào tạo'),
    ('Điều 5.', 'article', '5', ''),
    ('ĐIỀU 12. ĐIỀU KIỆN', 'article', '12', 'ĐIỀU KIỆN'),
    ('Điều 5a. Trách nhiệm', 'article', '5a', 'Trách nhiệm'),
    ('Điều 5 Điều kiện', 'article', '5', 'Điều kiện'),
    ('1. Sinh viên phải hoàn thành học phí.', 'clause', '1', 'Sinh viên phải hoàn thành học phí.'),
    ('2.', 'clause', '2', ''),
    ('đ) Đối tượng khác.', 'point', 'đ', 'Đối tượng khác.'),
    ('a)', 'point', 'a', ''),
])
def test_structural_markers(text, kind, number, title):
    match = match_structure(text)
    assert (match.kind, match.number, match.title, match.start, match.end) == (kind, number, title, 0, len(text))


@pytest.mark.parametrize('text', [
    'Theo Điều 5. Điều kiện...', 'Điều 5 của Quy chế này', 'Điều 5 quy định về quyền lợi',
    'Mục 2.4 của thông báo', 'Chương trình đào tạo', 'Điều kiện xét tuyển',
    '1.000 đồng', '2.1. Điều kiện', '2026-2027', 'a/b',
])
def test_references_decimal_values_and_prose_are_not_legal_markers(text):
    assert match_structure(text) is None


def test_legal_hierarchy_continues_across_pages_and_resets_descendants():
    pages = [
        {"page_number": 1, "content": "Chương I\nQUY ĐỊNH CHUNG\nMục 1. Đào tạo\nĐiều 5. Điều kiện\n1. Sinh viên phải\nhoàn thành học phần.\na) Nộp hồ sơ\nđầy đủ"},
        {"page_number": 2, "content": "- 2 -\ntrước ngày thông báo.\nđ) Hoàn thành nghĩa vụ.\n2. Trường hợp khác.\nĐiều 6. Trách nhiệm\n1. Nhà trường thực hiện.\nMục 2. Tổ chức\nChương II\nTHI HÀNH\nĐiều 7. Hiệu lực"},
    ]
    result = extract_structure(normalize_pages(pages))
    assert_provenance(pages, result)
    continuation = next(row for row in result.segments if row.content == 'trước ngày thông báo.')
    assert continuation.page_number == 2
    assert continuation.section_title == 'Chương I QUY ĐỊNH CHUNG / Mục 1. Đào tạo / Điều 5. Điều kiện / Khoản 1 / Điểm a'
    assert result.nodes[continuation.segment_index].kind == 'point'
    second_clause = next(row for row in result.segments if row.content == '2. Trường hợp khác.')
    assert second_clause.section_title.endswith('Điều 5. Điều kiện / Khoản 2')
    assert 'Điểm' not in second_clause.section_title
    article6 = next(row for row in result.segments if row.content == '1. Nhà trường thực hiện.')
    assert 'Điều 6. Trách nhiệm / Khoản 1' in article6.section_title
    assert 'Điều 5' not in article6.section_title
    assert result.segments[-1].section_title == 'Chương II THI HÀNH / Điều 7. Hiệu lực'


def test_standalone_and_wrapped_article_titles_do_not_consume_next_clause():
    result = extract('Điều 5.\nĐiều kiện xét tốt nghiệp\n1. Sinh viên hoàn thành chương trình.',
                     'Điều 6. Trách nhiệm của\nnhà trường\n1. Thông báo công khai.')
    assert [row.content for row in result.segments] == [
        'Điều 5. Điều kiện xét tốt nghiệp', '1. Sinh viên hoàn thành chương trình.',
        'Điều 6. Trách nhiệm của nhà trường', '1. Thông báo công khai.',
    ]
    assert result.segments[1].section_title == 'Điều 5. Điều kiện xét tốt nghiệp / Khoản 1'


def test_bare_article_followed_by_body_is_not_given_a_fabricated_title():
    result = extract('Điều 1.\nBan hành kèm theo quyết định này quy chế đào tạo.\nĐiều 2.\nCó hiệu lực kể từ ngày ký.')
    assert result.segments[0].content == 'Điều 1.'
    assert result.segments[1].section_title == 'Điều 1.'
    assert result.segments[1].content.startswith('Ban hành')


def test_outline_does_not_swallow_urls_or_promote_wrapped_numbered_list_items():
    result = extract('II. TUYỂN SINH\n2.7. Tổ chức tuyển sinh\n1. Phiếu ĐKDT (sẽ được gửi đến email của thí sinh ngay sau khi đăng ký trực tuyến\nthành công).\n2.8. Thông tin công khai\nhttps://dau.edu.vn/ba-cong-khai.html')
    assert [node.number for node in result.nodes if node.kind == 'heading'] == ['II', '2.7', '2.8']
    assert result.segments[-1].content == 'https://dau.edu.vn/ba-cong-khai.html'
    assert result.segments[-1].section_title == 'II. TUYỂN SINH / 2.8. Thông tin công khai'


def test_attached_application_form_starts_a_new_context():
    result = extract('3. Thời gian áp dụng:\n— Áp dụng từ năm học 2021-2022;',
                     'ĐƠN XIN XÉT GIẢM HỌC PHÍ\nKính gửi: Hiệu trưởng\nTôi tên là: ...')
    assert result.segments[-1].section_title == 'ĐƠN XIN XÉT GIẢM HỌC PHÍ'
    assert 'Thời gian' not in result.segments[-1].section_title


def test_notice_numbered_lists_do_not_become_legal_clauses():
    pages = [{"page_number": 1, "content": 'THÔNG BÁO\nVề việc đăng ký học phần\n\n1. Nộp hồ sơ.\na) Bản sao giấy tờ.\n2. Hoàn thành học phí.'}]
    result = extract_structure(normalize_pages(pages))
    assert_provenance(pages, result)
    assert not any(node.kind in ('article', 'clause', 'point') for node in result.nodes)
    assert [node.kind for node in result.nodes].count('list_item') == 3
    assert result.warnings == ('No legal headings found; used outline/heading/paragraph fallback',)


def test_real_admissions_outline_excerpt_and_table_scores_use_fallback():
    # Text patterns observed in the user-provided 2026 admissions PDF.
    pages = [{"page_number": 2, "content": 'II. TUYỂN SINH ĐÀO TẠO ĐẠI HỌC\n2.2 Mô tả phương thức tuyển sinh4 (thi tuyển, xét tuyển hoặc kết hợp thi tuyển và xét\ntuyển...)\n2.2.1. Phương thức, mã phương thức xét tuyển:\nSTT\nPhương thức\n1\nPhương thức 1\n100\n2.2.2. Mô tả phương thức tuyển sinh\na) Phương thức 1: Xét tuyển\n- Đối tượng: Áp dụng cho các ngành.\n19.5\n21.5 ; 23'}]
    result = extract_structure(normalize_pages(pages))
    assert_provenance(pages, result)
    assert [node.number for node in result.nodes if node.kind == 'heading'] == ['II', '2.2', '2.2.1', '2.2.2']
    table = next(row for row in result.segments if row.content.startswith('STT'))
    assert '2.2.1.' in table.section_title
    assert not any(node.kind in ('article', 'clause', 'point') for node in result.nodes)


def test_real_tuition_outline_excerpt_preserves_ocr_text_and_cross_page_context():
    # Keep OCR errors/spelling intact; the structure layer must not invent fixes.
    pages = [
        {"page_number": 2, "content": '2. Điều kiện và thủtục xét giảm học phí:\n2.1. Điều kiện:\n— Sinh viên thuộc các đối tượng trên không thuộc diện bịcảnh báo kết\nquảhọc tập.\n2.2. Thủtục xét giảm học phí đối-với sinh viên có hoàn cảnh khó khăn:\n— Các giấy tờxác nhận đối tượng'},
        {"page_number": 3, "content": 'nộp một lần.\n3. Thời gian áp dụng:\n— Quy định này được áp dụng ké từhọc kỳ1 năm học 2021-2022;'},
    ]
    result = extract_structure(normalize_pages(pages))
    assert_provenance(pages, result)
    continuation = next(row for row in result.segments if row.content == 'nộp một lần.')
    assert '2.2.' in continuation.section_title
    assert all(node.kind not in ('article', 'clause', 'point') for node in result.nodes)
    assert 'áp dụng ké từhọc kỳ1' in result.full_text


@pytest.mark.parametrize('text', ['19.5', '21.5 ; 23', '1.000 đồng', '2.1. được quy định', '2026. Ngày ký.'])
def test_fallback_heading_does_not_promote_numbers_or_running_prose(text):
    assert match_outline(text) is None


def test_blank_pages_gaps_and_empty_document_are_retained_without_empty_segments():
    pages = [{"page_number": 2, "content": ''}, {"page_number": 4, "content": 'Một đoạn\ntiếp nối.'}, {"page_number": 5, "content": '\n'}]
    result = extract_structure(normalize_pages(pages))
    assert_provenance(pages, result)
    assert [span.page_number for span in result.page_spans] == [2, 4, 5]
    assert result.page_spans[0].char_start == result.page_spans[0].char_end
    assert result.segments[0].page_number == 4
    assert extract().segments == ()


def test_long_titles_respect_schema_without_truncating_content_or_losing_clause_number():
    heading = 'Điều 1. ' + 'Nội dung ' * 100
    pages = [{"page_number": 1, "content": heading + '\n1. Giữ đầy đủ nội dung.'}]
    result = extract_structure(normalize_pages(pages))
    assert_provenance(pages, result)
    assert result.segments[0].content == heading.strip()
    assert result.segments[1].section_title.endswith('Khoản 1')
    assert any('truncated' in warning for warning in result.warnings)


def test_output_rows_only_have_existing_segment_columns_and_are_deterministic():
    normalized = normalize_pages([{"page_number": 1, "content": 'Điều 1. Nội dung\n1. Áp dụng.\nđ) Sinh viên.'}])
    first, second = extract_structure(normalized), extract_structure(normalized)
    assert first == second
    assert set(first.to_rows()[0]) == {'segment_index', 'page_number', 'paragraph_index', 'section_title', 'content', 'char_start', 'char_end'}
    assert first.to_dict()['parser_version'] == 'structure-1.0'


def test_mixed_input_preserves_every_normalized_line_and_offset():
    rng = random.Random(20261103)
    choices = ['Điều 2. Nội dung', '1. Đối tượng:', 'a) Sinh viên', 'nộp hồ sơ đầy đủ.', '',
               '19.5', 'THÔNG BÁO', '2.1. Điều kiện', '- Hồ sơ bổ sung.', 'Chương II', 'ĐÀO TẠO', 'Đơn vị: Phòng Đào tạo']
    pages = [{"page_number": index + 1, "content": '\n'.join(rng.choices(choices, k=35))} for index in range(8)]
    result = extract_structure(normalize_pages(pages))
    assert_provenance(pages, result)
