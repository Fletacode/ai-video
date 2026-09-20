"""PDF → 페이지별 PNG (PyMuPDF, poppler 불필요).

기본적으로 흰 여백을 제거(trim)한다: PowerPoint 16:9 슬라이드가 A4 페이지 가운데
놓여 생기는 상/하/좌/우 흰 여백을 잘라내, 슬라이드가 프레임을 꽉 채우게 한다.
전 페이지 공통(합집합) 내용 영역으로 크롭하므로 크기가 균일해 영상 결합에도 안전하다.

(connect-ppt/src/connect_ppt/slides.py 를 그대로 이식)
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import fitz  # PyMuPDF
from PIL import Image, ImageChops

Box = Tuple[int, int, int, int]


def _content_bbox(im: Image.Image, tol: int = 8) -> Optional[Box]:
    """흰색이 아닌 픽셀의 경계 상자를 반환한다(전부 흰색이면 None). tol 은 흰색 허용오차."""
    rgb = im.convert("RGB")
    bg = Image.new("RGB", rgb.size, (255, 255, 255))
    diff = ImageChops.difference(rgb, bg).convert("L")
    if tol:
        diff = diff.point(lambda p: 255 if p > tol else 0)
    return diff.getbbox()


def _union(a: Optional[Box], b: Optional[Box]) -> Optional[Box]:
    if a is None:
        return b
    if b is None:
        return a
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def render_slides(
    pdf_path: Path,
    out_dir: Path,
    *,
    zoom: float = 2.0,
    force: bool = False,
    trim: bool = True,
    tol: int = 8,
    pad: int = 0,
) -> List[Path]:
    """PDF 각 페이지를 slide_{n:02d}.png 로 렌더한다.

    trim=True 면 원본은 out_dir/raw/ 에 캐시하고, 흰 여백을 제거한 결과를
    out_dir/slide_NN.png 로 저장한다. trim=False 면 원본을 그대로 out_dir 에 렌더.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) 원본 페이지 렌더 (느린 단계 → 캐시)
    src_dir = (out_dir / "raw") if trim else out_dir
    src_dir.mkdir(parents=True, exist_ok=True)

    # 캐시는 파일명(slide_NN.png) 기반이라 소스가 바뀌어도 파일이 남아 있으면 재사용된다.
    # PDF 경로·mtime·크기·zoom 스탬프를 기록해 두고, 다르면 통째로 무효화한다.
    st = pdf_path.stat()
    stamp = f"{Path(pdf_path).resolve()}|{st.st_mtime_ns}|{st.st_size}|{zoom}"
    stamp_file = src_dir / ".source"
    cached = stamp_file.read_text(encoding="utf-8") if stamp_file.exists() else None
    if not force and cached != stamp and any(src_dir.glob("slide_*.png")):
        force = True
    if force:
        for old in src_dir.glob("slide_*.png"):
            old.unlink()
        if trim:
            for old in out_dir.glob("slide_*.png"):
                old.unlink()

    doc = fitz.open(str(pdf_path))
    matrix = fitz.Matrix(zoom, zoom)
    src_paths: List[Path] = []
    try:
        for i, page in enumerate(doc, start=1):
            p = src_dir / f"slide_{i:02d}.png"
            if force or not p.exists():
                page.get_pixmap(matrix=matrix).save(str(p))
            src_paths.append(p)
    finally:
        doc.close()
    stamp_file.write_text(stamp, encoding="utf-8")

    if not trim:
        return src_paths

    # 2) 흰 여백 제거: 전 페이지 공통(합집합) 내용 영역으로 균일 크롭
    union: Optional[Box] = None
    for p in src_paths:
        with Image.open(p) as im:
            union = _union(union, _content_bbox(im, tol))
    if union is None:
        return src_paths  # 전부 흰색이면 크롭하지 않음

    left, top, right, bottom = union
    if pad:
        with Image.open(src_paths[0]) as im0:
            w, h = im0.size
        left, top = max(0, left - pad), max(0, top - pad)
        right, bottom = min(w, right + pad), min(h, bottom + pad)

    out_paths: List[Path] = []
    for i, p in enumerate(src_paths, start=1):
        out = out_dir / f"slide_{i:02d}.png"
        with Image.open(p) as im:
            im.crop((left, top, right, bottom)).save(str(out))
        out_paths.append(out)
    return out_paths
