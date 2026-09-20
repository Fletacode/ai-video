"""v3 나레이션 MD → 세그먼트 모델 파서.

MD 형식(connect-ppt 포맷의 상위호환): 각 슬라이드는 `**[n]**` 헤더로 시작하고,
본문에 나레이션 텍스트와 다음 마커가 섞인다.
- `(N초동안 쉼,공백)`         : v3 인라인 쉼 태그로 변환(1초→[short pause], 2초→[long pause],
                                그 외→[pause]). **실제 무음이 아니라** 텍스트에 남아 v3 로 전달된다.
                                (하위호환용 legacy 마커. 신규 작성은 쉼 태그를 직접 쓰는 것을 권장.)
- `(배경음악만, 나레이션 없음)` : 나레이션 없는 무음 세그먼트.
- `(효과음 N초)`               : 징글(효과음) 삽입 지점 → Sfx 런. 합성 단계에서 별도 음원을
                                N초에 맞춰 삽입한다(음원 없으면 N초 무음). 낭독되지 않는다.
- `[태그]`                    : eleven_v3 오디오 태그(예: [warm], [pause], [excited]).
                                TTS 텍스트에는 그대로 보존해 v3 에 전달하고,
                                자막(clean_text)에서는 제거한다.

파서는 세그먼트 본문을 **단일 TextRun**(쉼 태그 인라인 포함)으로 변환한다 → 슬라이드당 v3 요청 1회.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Union


@dataclass
class TextRun:
    """합성해서 읽을 나레이션 텍스트 조각. text 에는 [오디오 태그] 가 그대로 남는다."""

    text: str


@dataclass
class Pause:
    """실제 무음으로 삽입할 쉼(초).

    파서는 더 이상 이 런을 생성하지 않는다(쉼은 v3 인라인 태그로 변환됨).
    tts.build_segment_audio 는 하위호환을 위해 직접 구성된 Pause 런을 계속 무음으로 처리한다.
    """

    seconds: float


@dataclass
class Sfx:
    """별도 효과음(징글)을 삽입할 지점. 합성 단계에서 --jingle 음원을 seconds 초로 맞춰 넣는다."""

    seconds: float


Run = Union[TextRun, Pause, Sfx]


# 오디오 태그: 대괄호로 감싼 한 줄짜리 토큰(예: [warm], [pause]).
# TTS 로는 보존하고 자막에서만 제거하기 위한 패턴.
_TAG_RE = re.compile(r"\[[^\[\]\n]+\]")


def strip_tags(text: str) -> str:
    """오디오 태그([...])를 제거하고 공백을 정리한다(자막/로그용)."""
    return re.sub(r"\s+", " ", _TAG_RE.sub("", text)).strip()


@dataclass
class Segment:
    """슬라이드 한 장에 대응하는 나레이션 세그먼트."""

    index: int
    runs: List[Run]

    @property
    def is_silent(self) -> bool:
        """읽을 텍스트가 하나도 없으면 무음 세그먼트(예: 배경음악만).

        태그만 있고 실제 낭독 텍스트가 없는 경우도 무음으로 본다.
        """
        return not any(
            isinstance(r, TextRun) and strip_tags(r.text) for r in self.runs
        )

    @property
    def raw_text(self) -> str:
        """v3 TTS 로 보낼 텍스트(오디오 태그 유지, Pause 제외)."""
        parts = [r.text for r in self.runs if isinstance(r, TextRun) and r.text]
        return " ".join(parts).strip()

    @property
    def clean_text(self) -> str:
        """마커·오디오 태그가 제거된 나레이션 전체 텍스트(SRT/로그용)."""
        parts = [
            strip_tags(r.text)
            for r in self.runs
            if isinstance(r, TextRun) and r.text
        ]
        return re.sub(r"\s+", " ", " ".join(parts)).strip()


_HEADER_RE = re.compile(r"\*\*\[(\d+)\]\*\*")
_PAUSE_RE = re.compile(r"\(\s*(\d+)\s*초\s*동안\s*쉼\s*[,，]?\s*공백\s*\)")
_BGM_RE = re.compile(r"\(\s*배경음악만[,，]?\s*나레이션\s*없음\s*\)")
_SFX_RE = re.compile(r"\(\s*효과음\s*(\d+(?:\.\d+)?)\s*초\s*\)")


# 기호 → 말로 읽을 형태 정규화.
# 화살표(→)는 제거하고, 도형 기호(○/△)는 "동그라미"/"세모" 로 바꾼다.
# 원문에 이미 "○(동그라미)"/"△(세모)" 형태가 있으면 중복을 없애 한 단어로만 남긴다.
_SYMBOL_PAIRS = [
    ("○(동그라미)", "동그라미"),
    ("O(동그라미)", "동그라미"),
    ("△(세모)", "세모"),
]


def _normalize_symbols(text: str) -> str:
    for src, dst in _SYMBOL_PAIRS:
        text = text.replace(src, dst)
    text = text.replace("○", "동그라미").replace("△", "세모")
    text = text.replace("→", " ").replace("->", " ")
    return text


def _clean(text: str) -> str:
    # 주의: 대괄호([태그])는 건드리지 않는다 → v3 로 전달되도록 TextRun 에 보존.
    return re.sub(r"\s+", " ", _normalize_symbols(text)).strip()


def _pause_to_tag(seconds: int) -> str:
    """legacy `(N초동안 쉼,공백)` 초 → v3 인라인 쉼 태그."""
    if seconds >= 2:
        return "[long pause]"
    if seconds == 1:
        return "[short pause]"
    return "[pause]"


def _parse_runs(body: str) -> List[Run]:
    body = _BGM_RE.sub(" ", body)
    # (N초동안 쉼,공백) → v3 인라인 쉼 태그로 치환. 실제 무음/Pause 런으로 쪼개지 않고
    # 본문 전체를 단일 TextRun 으로 만들어 슬라이드당 v3 요청 1회로 합성한다.
    body = _PAUSE_RE.sub(lambda m: f" {_pause_to_tag(int(m.group(1)))} ", body)
    # (효과음 N초) 는 별도 Sfx 런으로 분리한다. 마커를 세그먼트 시작/끝에만 두면
    # 본문은 단일 TextRun 으로 유지된다(슬라이드당 v3 요청 1회).
    runs: List[Run] = []
    pos = 0
    for m in _SFX_RE.finditer(body):
        text = _clean(body[pos : m.start()])
        if text:
            runs.append(TextRun(text))
        runs.append(Sfx(float(m.group(1))))
        pos = m.end()
    tail = _clean(body[pos:])
    if tail:
        runs.append(TextRun(tail))
    return runs


def parse_script(md_text: str) -> List[Segment]:
    """나레이션 MD 텍스트를 Segment 리스트로 파싱한다(헤더 순서 유지)."""
    matches = list(_HEADER_RE.finditer(md_text))
    segments: List[Segment] = []
    for i, m in enumerate(matches):
        idx = int(m.group(1))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md_text)
        segments.append(Segment(index=idx, runs=_parse_runs(md_text[start:end])))
    return segments
