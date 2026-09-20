"""이미지 + 세그먼트 오디오 → MP4 (ffmpeg 서브프로세스).

세그먼트별로 정지 이미지를 오디오 길이만큼 노출하는 파트 MP4 를 만들고,
concat demuxer 로 무재인코딩 결합한다. 모든 파트가 동일 코덱 파라미터라 -c copy 가능.

(connect-ppt/src/connect_ppt/video.py 를 그대로 이식)
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List

FPS = 25


def build_part(image: Path, audio: Path, duration: float, out: Path) -> None:
    """정지 이미지 1장을 정확히 duration 초 동안 보여주는 파트 MP4 생성.

    -t 로 길이를 명시(측정된 오디오 길이)하고 CFR·고정 타임스케일로 만들어
    이후 concat -c copy 가 길이를 정확히 합산하도록 한다(-shortest 는 loop 이미지에서
    길이를 정확히 자르지 못하는 문제가 있음).
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-loop", "1", "-framerate", str(FPS), "-i", str(image),
            "-i", str(audio),
            "-t", f"{duration:.3f}",
            "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
            "-r", str(FPS), "-vsync", "cfr", "-video_track_timescale", "90000",
            # yuv420p 는 짝수 해상도 요구
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            # 채널 수를 항상 2로 고정 — 파트별 소스가 모노(TTS)/스테레오(징글) 로 섞여도
            # 모든 파트의 오디오 파라미터가 동일해야 concat -c copy 재생이 깨지지 않는다
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
            str(out),
        ],
        check=True,
        capture_output=True,
    )


def concat_parts(parts: List[Path], out: Path) -> None:
    """파트 MP4 들을 concat demuxer 로 결합."""
    out.parent.mkdir(parents=True, exist_ok=True)
    list_file = out.parent / f"{out.stem}_concat.txt"
    list_file.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in parts) + "\n", encoding="utf-8"
    )
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(list_file),
            "-c", "copy",
            str(out),
        ],
        check=True,
        capture_output=True,
    )


def build_video(
    pairs: List["tuple[Path, Path, float]"], out: Path, parts_dir: Path
) -> Path:
    """(image, audio, duration) 리스트로 파트 생성 후 결합해 out MP4 를 만든다."""
    parts: List[Path] = []
    for i, (image, audio, duration) in enumerate(pairs, start=1):
        part = parts_dir / f"part_{i:02d}.mp4"
        build_part(image, audio, duration, part)
        parts.append(part)
    concat_parts(parts, out)
    return out
