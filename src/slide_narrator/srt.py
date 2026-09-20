"""세그먼트 + 측정된 오디오 길이 → SRT 문자열.

세그먼트마다 큐 1개. start 는 누적 길이, end 는 start+duration.
자막 텍스트는 Segment.clean_text(오디오 태그·마커 제거) 를 사용한다.
"""

from __future__ import annotations

from typing import List, Sequence

from slide_narrator.parse_script import Segment


def format_timestamp(seconds: float) -> str:
    """초 → SRT 타임스탬프(HH:MM:SS,mmm)."""
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(segments: Sequence[Segment], durations: Sequence[float]) -> str:
    """세그먼트별 측정 길이로 누적 타이밍 SRT 를 만든다."""
    if len(segments) != len(durations):
        raise ValueError(
            f"segments({len(segments)}) 와 durations({len(durations)}) 개수 불일치"
        )
    lines: List[str] = []
    cursor = 0.0
    for n, (seg, dur) in enumerate(zip(segments, durations), start=1):
        start, end = cursor, cursor + dur
        cursor = end
        lines.append(str(n))
        lines.append(f"{format_timestamp(start)} --> {format_timestamp(end)}")
        lines.append(seg.clean_text)
        lines.append("")
    return "\n".join(lines)
