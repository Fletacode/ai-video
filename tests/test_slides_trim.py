"""슬라이드 흰 여백 제거(크롭) + 렌더 캐시 무효화 로직 테스트."""

import os

import fitz  # PyMuPDF
from PIL import Image

from slide_narrator.slides import _content_bbox, _union, render_slides


def _make_pdf(path, color, pages=2):
    doc = fitz.open()
    for _ in range(pages):
        page = doc.new_page(width=400, height=300)
        page.draw_rect(fitz.Rect(100, 80, 300, 220), fill=color)
    doc.save(str(path))
    doc.close()


def test_content_bbox_finds_drawn_region():
    im = Image.new("RGB", (100, 80), (255, 255, 255))
    for x in range(20, 60):
        for y in range(10, 50):
            im.putpixel((x, y), (0, 0, 0))
    assert _content_bbox(im, tol=8) == (20, 10, 60, 50)


def test_content_bbox_all_white_is_none():
    im = Image.new("RGB", (50, 50), (255, 255, 255))
    assert _content_bbox(im, tol=8) is None


def test_union_merges_boxes():
    assert _union((10, 10, 20, 20), (15, 5, 30, 18)) == (10, 5, 30, 20)
    assert _union(None, (1, 2, 3, 4)) == (1, 2, 3, 4)


def test_render_slides_trims_white_margins(tmp_path):
    pdf = tmp_path / "t.pdf"
    doc = fitz.open()
    for _ in range(2):
        page = doc.new_page(width=400, height=300)
        page.draw_rect(fitz.Rect(100, 80, 300, 220), fill=(0, 0, 0))
    doc.save(str(pdf))
    doc.close()

    paths = render_slides(pdf, tmp_path / "out", zoom=1.0, trim=True, tol=8)
    assert len(paths) == 2
    sizes = {Image.open(p).size for p in paths}
    assert len(sizes) == 1
    w, h = next(iter(sizes))
    assert w < 400 and h < 300
    assert abs(w - 200) <= 3 and abs(h - 140) <= 3


def test_render_rerenders_when_pdf_content_changes(tmp_path):
    # 같은 파일명·같은 페이지 수라도 PDF 내용이 바뀌면 캐시를 버리고 다시 렌더해야 한다
    pdf = tmp_path / "t.pdf"
    out = tmp_path / "out"
    _make_pdf(pdf, (0, 0, 0))
    first = render_slides(pdf, out, zoom=1.0, trim=False)[0].read_bytes()

    _make_pdf(pdf, (1, 0, 0))  # 내용만 교체 (다른 덱으로 바뀐 상황)
    st = os.stat(pdf)
    os.utime(pdf, ns=(st.st_atime_ns, st.st_mtime_ns + 2_000_000_000))
    second = render_slides(pdf, out, zoom=1.0, trim=False)[0].read_bytes()
    assert second != first


def test_render_rerenders_when_zoom_changes(tmp_path):
    pdf = tmp_path / "t.pdf"
    out = tmp_path / "out"
    _make_pdf(pdf, (0, 0, 0))
    p1 = render_slides(pdf, out, zoom=1.0, trim=False)
    assert Image.open(p1[0]).size == (400, 300)
    p2 = render_slides(pdf, out, zoom=2.0, trim=False)
    assert Image.open(p2[0]).size == (800, 600)
