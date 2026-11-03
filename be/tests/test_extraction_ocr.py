"""Regression for a scanned PDF with a native digital-signature overlay."""
from types import SimpleNamespace

import pymupdf

from app.modules.extractions.services import extract_page_text, needs_ocr


def page_with(*, images=(), text_box=(0, 0, 100, 30)):
    return SimpleNamespace(
        rect=pymupdf.Rect(0, 0, 600, 800),
        get_image_info=lambda: [{"bbox": box} for box in images],
        get_images=lambda: list(images),
        get_text=lambda kind: [(*text_box, 'Native text', 0, 0)],
    )


def test_full_page_scan_with_small_native_signature_requires_ocr():
    page = page_with(images=[(0, 0, 600, 800)], text_box=(300, 680, 550, 760))
    assert needs_ocr(page, 'Tài liệu đã ký số. Tra cứu chữ ký số. ' * 6)


def test_native_text_pages_and_small_logos_do_not_force_ocr():
    text = 'Nội dung văn bản có sẵn. ' * 6
    assert not needs_ocr(page_with(), text)
    assert not needs_ocr(page_with(images=[(0, 0, 40, 40)]), text)


def test_existing_ocr_text_covering_the_page_is_not_reprocessed():
    page = page_with(images=[(0, 0, 600, 800)], text_box=(30, 60, 550, 700))
    assert not needs_ocr(page, 'Nội dung đã nhận diện. ' * 10)
    assert not needs_ocr(page, 'Nội dung đã nhận diện. ' * 100)


def test_short_image_pages_still_require_ocr():
    assert needs_ocr(page_with(images=[(0, 0, 600, 800)]), '')
    assert not needs_ocr(page_with(), 'Trang ký tên')


def test_signature_overlay_flows_through_ocr_and_returns_the_body():
    page = page_with(images=[(0, 0, 600, 800)], text_box=(300, 680, 550, 760))
    calls = []
    token = object()
    native_get_text = page.get_text

    def get_text(kind, **kwargs):
        if kind == 'blocks':
            return native_get_text(kind)
        if kwargs.get('textpage') is token:
            return 'ĐƠN XIN XÉT GIẢM HỌC PHÍ\nNội dung mẫu đơn.'
        return 'Tài liệu đã ký số. Tra cứu chữ ký số. ' * 6

    def ocr(**kwargs):
        calls.append(kwargs)
        return token

    page.get_text = get_text
    page.get_textpage_ocr = ocr
    assert extract_page_text(page, tessdata='/test/tessdata').startswith('ĐƠN XIN XÉT GIẢM HỌC PHÍ')
    assert calls == [{'language': 'vie+eng', 'dpi': 200, 'full': True, 'tessdata': '/test/tessdata'}]
