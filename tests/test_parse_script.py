"""parse_script 단위 테스트.

- 하위호환: 원본 나레이션 MD(태그 없음)에서 connect-ppt 와 동일하게 동작.
- 신규: [오디오 태그] 는 TTS 텍스트(raw_text)에 보존되고 자막(clean_text)에서 제거된다.
"""

from pathlib import Path

import pytest

from slide_narrator.parse_script import (
    Pause,
    Segment,
    Sfx,
    TextRun,
    parse_script,
    strip_tags,
)

MD_PATH = Path(__file__).resolve().parents[1] / "docs" / "1-1" / "1-1_나레이션대본.md"


# ---- 하위호환 (원본 MD, 태그 없음) ---------------------------------------


@pytest.fixture(scope="module")
def segments() -> list:
    return parse_script(MD_PATH.read_text(encoding="utf-8"))


def test_parses_58_segments(segments):
    assert len(segments) == 58
    assert [s.index for s in segments] == list(range(1, 59))


def test_segment_1_is_silent(segments):
    seg = segments[0]
    assert seg.index == 1
    assert seg.is_silent is True
    assert seg.clean_text == ""


def test_segment_4_pause_becomes_inline_tag(segments):
    # (N초동안 쉼,공백) 은 실제 무음(Pause)이 아니라 v3 인라인 쉼 태그로 변환된다.
    seg = next(s for s in segments if s.index == 4)
    assert seg.is_silent is False
    assert not [r for r in seg.runs if isinstance(r, Pause)]
    assert "[long pause]" in seg.raw_text  # 2초 → [long pause]
    assert "먼저, 시간 관련 어휘를 공부할 것입니다." in seg.clean_text
    assert "아침, 점심, 저녁, 밤" in seg.clean_text


def test_each_nonsilent_segment_is_single_textrun(segments):
    # 슬라이드당 API 1회를 보장하려면 비무음 세그먼트는 TextRun 하나여야 한다.
    for seg in segments:
        if seg.is_silent:
            continue
        textruns = [r for r in seg.runs if isinstance(r, TextRun)]
        assert len(textruns) == 1, f"[{seg.index}] TextRun {len(textruns)}개"


def test_pause_seconds_map_to_tags():
    segs = parse_script("**[1]** 가 (1초동안 쉼,공백) 나 (2초동안 쉼,공백) 다")
    raw = segs[0].raw_text
    assert "[short pause]" in raw  # 1초 → [short pause]
    assert "[long pause]" in raw   # 2초 → [long pause]
    assert segs[0].clean_text == "가 나 다"  # 자막엔 쉼 태그 제거


def test_clean_text_has_no_pause_markers(segments):
    for seg in segments:
        assert "쉼" not in seg.clean_text
        assert "공백" not in seg.clean_text
        assert "초동안" not in seg.clean_text
        assert "pause" not in seg.clean_text


def test_pause_tag_kept_inline_between_text(segments):
    # 변환된 쉼 태그는 앞뒤 텍스트 사이 원래 위치에 인라인으로 남는다.
    seg = next(s for s in segments if s.index == 4)
    txt = seg.raw_text
    i = txt.index("[long pause]")
    assert txt[:i].strip()  # 태그 앞 텍스트 존재
    assert txt[i + len("[long pause]") :].strip()  # 태그 뒤 텍스트 존재


def test_no_arrow_or_shape_symbols_anywhere(segments):
    for seg in segments:
        for sym in ("→", "->", "○", "△", "O(동그라미)"):
            assert sym not in seg.clean_text, f"[{seg.index}] 에 기호 {sym} 남음"


def test_circle_triangle_become_words(segments):
    seg = next(s for s in segments if s.index == 57)
    assert "정답은 동그라미입니다" in seg.clean_text
    assert "정답은 세모입니다" in seg.clean_text


# ---- 신규: v3 오디오 태그 동작 -------------------------------------------

V3_FIXTURE = """
**[1]** (배경음악만, 나레이션 없음)

**[2]** (2초동안 쉼,공백) [warm] 자, 이번 시간에는요, [pause] 인사말을 배워볼 거예요.
[excited] 어렵지 않아요.

**[3]** [warm] 오늘 목표는 [long pause] 자연스럽게 말하기예요.
"""


@pytest.fixture(scope="module")
def v3_segments() -> list:
    return parse_script(V3_FIXTURE)


def test_strip_tags_helper():
    assert strip_tags("[warm] 안녕 [pause] 하세요") == "안녕 하세요"
    assert strip_tags("[long pause]태그만") == "태그만"


def test_tags_preserved_in_raw_text(v3_segments):
    seg = next(s for s in v3_segments if s.index == 2)
    # v3 로 보낼 텍스트에는 태그가 남아야 한다
    assert "[warm]" in seg.raw_text
    assert "[pause]" in seg.raw_text
    assert "[excited]" in seg.raw_text


def test_tags_stripped_in_clean_text(v3_segments):
    for seg in v3_segments:
        assert "[" not in seg.clean_text
        assert "]" not in seg.clean_text
        for word in ("warm", "pause", "excited", "long pause"):
            assert word not in seg.clean_text
    seg2 = next(s for s in v3_segments if s.index == 2)
    assert "인사말을 배워볼 거예요." in seg2.clean_text


def test_tags_preserved_in_textrun(v3_segments):
    # build_segment_audio 는 run.text 를 synth 로 보내므로 태그가 살아 있어야 한다
    seg = next(s for s in v3_segments if s.index == 2)
    joined = " ".join(r.text for r in seg.runs if isinstance(r, TextRun))
    assert "[warm]" in joined and "[excited]" in joined


def test_pause_marker_becomes_tag_with_tags(v3_segments):
    # (2초동안 쉼,공백) → [long pause] 인라인 태그. Pause 런은 생기지 않는다.
    seg = next(s for s in v3_segments if s.index == 2)
    assert not [r for r in seg.runs if isinstance(r, Pause)]
    assert "[long pause]" in seg.raw_text


def test_tag_only_segment_not_broken():
    # 닫히지 않은 대괄호가 있어도 파서가 죽지 않는다(자막엔 남아 미리보기에서 발견됨)
    segs = parse_script("**[1]** [warm 안녕하세요")
    assert len(segs) == 1
    assert segs[0].is_silent is False


# ---- 신규: (효과음 N초) 마커 ----------------------------------------------


def test_sfx_marker_becomes_run_at_end():
    segs = parse_script("**[1]** [warm] 수고하셨습니다. [short pause] (효과음 8초)")
    runs = segs[0].runs
    assert isinstance(runs[-1], Sfx) and runs[-1].seconds == 8.0
    # 마커가 끝에 있으면 본문은 단일 TextRun 유지(슬라이드당 v3 요청 1회)
    assert len([r for r in runs if isinstance(r, TextRun)]) == 1
    assert "효과음" not in segs[0].raw_text
    assert "효과음" not in segs[0].clean_text


def test_sfx_marker_at_start():
    segs = parse_script("**[1]** (효과음 7초) 제6부 작업")
    runs = segs[0].runs
    assert isinstance(runs[0], Sfx) and runs[0].seconds == 7.0
    assert isinstance(runs[1], TextRun)
    assert segs[0].clean_text == "제6부 작업"


def test_sfx_only_segment():
    segs = parse_script("**[1]** (효과음 10초)")
    assert [type(r) for r in segs[0].runs] == [Sfx]
    assert segs[0].is_silent is True  # 낭독 텍스트 없음
    assert segs[0].clean_text == ""
