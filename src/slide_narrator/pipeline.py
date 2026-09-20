"""Phase B 오케스트레이터 + CLI.

v3 나레이션 MD + 슬라이드 PDF → 세그먼트별 TTS(쉼=무음, 태그=v3 전달) → SRT
→ 슬라이드 1:1 자동 전환 MP4.

  python -m slide_narrator.pipeline --engine gtts        # 미리보기 → build/preview.mp4
  python -m slide_narrator.pipeline --engine elevenlabs  # 최종(v3) → build/final.mp4

렌더할 슬라이드(과)는 --pdf + --script 쌍으로 선택한다(같은 과의 파일이어야 함):

  python -m slide_narrator.pipeline --engine gtts \\
      --pdf docs/6-5/6-5.pdf --script docs/6-5/6-5_나레이션대본.v3.md
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from pydub import AudioSegment

from slide_narrator import slides, srt, tts, video
from slide_narrator.parse_script import Segment, Sfx, parse_script

_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class RunResult:
    engine: str
    video: Path
    srt: Path
    combined_audio: Path
    audio_dir: Path
    total_sec: float
    n_segments: int


def _fmt(sec: float) -> str:
    m, s = divmod(int(round(sec)), 60)
    return f"{m}:{s:02d}"


def run(
    pdf: Path,
    script: Path,
    engine: str,
    out_dir: Path,
    *,
    default_silent_sec: float = 6.0,
    bgm_path: Optional[Path] = None,
    jingle_path: Optional[Path] = None,
    opening_path: Optional[Path] = None,
    zoom: float = 2.0,
    limit: Optional[int] = None,
    trim: bool = True,
    progress: Optional[callable] = None,
) -> RunResult:
    def _tick(msg: str) -> None:
        print(msg)
        if progress is not None:
            progress(msg)

    # 1) 파싱
    segments: List[Segment] = parse_script(script.read_text(encoding="utf-8"))
    _tick(f"[parse] 세그먼트 {len(segments)}개")

    # 2) 슬라이드 렌더 (기본: 흰 여백 제거) — 과별 폴더 build/slides/<과>/ 에 캐시
    slide_dir = out_dir / "slides" / pdf.stem
    slide_paths = slides.render_slides(pdf, slide_dir, zoom=zoom, trim=trim)
    _tick(
        f"[slides] 페이지 {len(slide_paths)}장 렌더 → {slide_dir}"
        + (" (여백 제거)" if trim else "")
    )

    # 3) 개수 정합
    n = min(len(segments), len(slide_paths))
    if len(segments) != len(slide_paths):
        _tick(
            f"⚠️ 세그먼트({len(segments)})와 슬라이드({len(slide_paths)}) 수 불일치 "
            f"→ 앞 {n}개만 사용"
        )
    if limit:
        n = min(n, limit)
        _tick(f"[limit] 앞 {n}개 세그먼트만 처리")
    segments, slide_paths = segments[:n], slide_paths[:n]

    # 4) synth 준비
    cfg = tts.load_eleven_cfg() if engine == "elevenlabs" else None
    if cfg is not None:
        _tick(f"[eleven] model_id={cfg.model_id} seed={cfg.seed}")
    synth = tts.make_synth(engine, cfg=cfg)
    bgm = AudioSegment.from_file(str(bgm_path)) if bgm_path else None
    jingle = None
    if jingle_path is not None and jingle_path.exists():
        jingle = AudioSegment.from_file(str(jingle_path))
        _tick(f"[jingle] {jingle_path} ({len(jingle) / 1000:.1f}초)")
    opening = None
    if opening_path is not None and opening_path.exists():
        opening = AudioSegment.from_file(str(opening_path))
        _tick(f"[opening] {opening_path} ({len(opening) / 1000:.1f}초)")
    n_sfx = sum(1 for s in segments for r in s.runs if isinstance(r, Sfx))
    if n_sfx and jingle is None:
        _tick(
            f"⚠️ (효과음 N초) 마커 {n_sfx}곳이 있지만 징글 음원이 없어 무음으로 대체됩니다 "
            f"(uv run -m slide_narrator.sfx 로 생성)"
        )
    # 첫 세그먼트가 선행 (효과음 N초) 마커(=오프닝 음악)로 시작하는데 오프닝 음원이 없으면 안내
    if (
        opening is None
        and segments
        and segments[0].runs
        and isinstance(segments[0].runs[0], Sfx)
    ):
        _tick(
            "⚠️ 첫 슬라이드가 오프닝 음악 마커로 시작하지만 오프닝 음원이 없어 "
            "징글(없으면 무음)로 대체됩니다 "
            "(uv run -m slide_narrator.sfx --preset opening 으로 생성)"
        )

    # 5) 세그먼트별 오디오 합성 (쉼=무음)
    audio_dir = out_dir / "audio"
    durations: List[float] = []
    audio_paths: List[Path] = []
    for i, (seg, slide) in enumerate(zip(segments, slide_paths), start=1):
        audio_path = audio_dir / f"seg_{seg.index:02d}.mp3"
        dur = tts.synthesize_segment(
            seg, synth, audio_path,
            default_silent_sec=default_silent_sec,
            bgm=bgm if seg.is_silent else None,
            jingle=jingle,
            opening=opening,
            is_opening_segment=(i == 1),
        )
        durations.append(dur)
        audio_paths.append(audio_path)
        label = "(무음)" if seg.is_silent else seg.clean_text[:24]
        _tick(f"[tts {i}/{n}] [{seg.index:02d}] {_fmt(dur):>5}  {label}")

    # 6) 전체 나레이션 합친 mp3
    combined_audio = audio_dir / f"full_{engine}.mp3"
    tts.combine_audio(audio_paths, combined_audio)

    # 7) SRT (오디오 태그는 clean_text 에서 이미 제거됨)
    srt_path = out_dir / "script.srt"
    srt_path.write_text(srt.to_srt(segments, durations), encoding="utf-8")
    total = sum(durations)
    _tick(f"[srt] {srt_path}  (총 {_fmt(total)})")

    # 8) 영상 합성 (슬라이드 1:1, 측정된 오디오 길이만큼 정지)
    out_name = "final.mp4" if engine == "elevenlabs" else "preview.mp4"
    out_video = out_dir / out_name
    video.build_video(
        list(zip(slide_paths, audio_paths, durations)), out_video, out_dir / "parts"
    )
    _tick(f"[video] {out_video}  (총 {_fmt(total)}, 슬라이드 {n}장)")

    return RunResult(
        engine=engine,
        video=out_video,
        srt=srt_path,
        combined_audio=combined_audio,
        audio_dir=audio_dir,
        total_sec=total,
        n_segments=n,
    )


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="v3 나레이션 대본 → 슬라이드 자동 전환 영상",
        epilog=(
            "슬라이드(과) 선택: --pdf 와 --script 를 같은 과의 파일 쌍으로 지정한다. "
            "예) --pdf docs/6-5/6-5.pdf --script docs/6-5/6-5_나레이션대본.v3.md "
            "(PDF 페이지와 대본의 **[n]** 헤더가 1:1 이어야 하며, 슬라이드는 --pdf 에서 "
            "--out/slides/<과>/ 로 렌더·캐시된다)"
        ),
    )
    p.add_argument(
        "--pdf", type=Path, default=_ROOT / "docs" / "1-1" / "1-1.pdf",
        help="렌더할 슬라이드 덱 PDF. --script 와 같은 과(docs/<과>/)의 파일을 지정",
    )
    p.add_argument(
        "--script", type=Path,
        default=_ROOT / "docs" / "1-1" / "1-1_나레이션대본.v3.md",
        help="v3 나레이션 대본(.v3.md). --pdf 와 같은 과의 파일을 지정",
    )
    p.add_argument("--engine", choices=["gtts", "elevenlabs"], default="gtts")
    p.add_argument("--out", type=Path, default=_ROOT / "build")
    p.add_argument("--default-silent-sec", type=float, default=6.0)
    p.add_argument("--bgm", type=Path, default=None)
    p.add_argument(
        "--jingle", type=Path, default=_ROOT / "assets" / "jingle.mp3",
        help="(효과음 N초) 마커에 삽입할 음원(없으면 N초 무음)",
    )
    p.add_argument(
        "--opening", type=Path, default=_ROOT / "assets" / "opening.mp3",
        help="영상 맨 처음(첫 슬라이드, 나레이션 앞)의 (효과음 N초) 마커에 삽입할 "
        "오프닝 음원(없으면 --jingle 로 대체)",
    )
    p.add_argument("--zoom", type=float, default=2.0)
    p.add_argument("--limit", type=int, default=None, help="앞 N개 세그먼트만(빠른 확인)")
    p.add_argument("--no-trim", action="store_true", help="슬라이드 흰 여백 제거 끄기")
    args = p.parse_args(argv)

    result = run(
        args.pdf, args.script, args.engine, args.out,
        default_silent_sec=args.default_silent_sec,
        bgm_path=args.bgm, jingle_path=args.jingle,
        opening_path=args.opening,
        zoom=args.zoom, limit=args.limit,
        trim=not args.no_trim,
    )
    print(f"\n✅ 완료: {result.video}")
    print(f"   합친 음성: {result.combined_audio}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
