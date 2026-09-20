"""Phase A 준비: 슬라이드를 PNG 로 렌더해 Claude Code 가 '볼' 수 있게 한다.

    python -m slide_narrator.prep --pdf docs/1-1/1-1.pdf --out build

이후 사람은 Claude Code 를 열어 docs/SCRIPT_FORMAT.md + docs/AUTHORING_GUIDE.md 를
따라, build/slides/<과>/slide_NN.png(렌더된 슬라이드)와 원본 대본을 보고
v3 대본(docs/<과>/<name>.v3.md)을 작성한다. 이 스크립트는 LLM 을 호출하지 않는다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from slide_narrator import slides

_ROOT = Path(__file__).resolve().parents[2]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Phase A: 작성용 슬라이드 렌더")
    p.add_argument("--pdf", type=Path, default=_ROOT / "docs" / "1-1" / "1-1.pdf")
    p.add_argument("--out", type=Path, default=_ROOT / "build")
    p.add_argument("--zoom", type=float, default=2.0)
    p.add_argument("--no-trim", action="store_true", help="흰 여백 제거 끄기")
    args = p.parse_args(argv)

    slide_dir = args.out / "slides" / args.pdf.stem
    paths = slides.render_slides(
        args.pdf, slide_dir, zoom=args.zoom, trim=not args.no_trim
    )
    print(f"✅ 슬라이드 {len(paths)}장 렌더 → {slide_dir}")
    print(
        "\n다음 단계(Phase A, 사람+Claude Code):\n"
        "  1) docs/SCRIPT_FORMAT.md, docs/AUTHORING_GUIDE.md 를 읽는다\n"
        f"  2) {slide_dir}/slide_NN.png 와 원본 대본을 보고\n"
        "  3) v3 대본 docs/<과>/<name>.v3.md 를 작성한다\n"
        "그 다음 Phase B: python -m slide_narrator.pipeline --engine gtts (미리보기)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
