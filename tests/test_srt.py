"""srt 빌더 단위 테스트."""

from slide_narrator.parse_script import Segment, TextRun
from slide_narrator.srt import format_timestamp, to_srt


def _seg(index: int, text: str) -> Segment:
    return Segment(index=index, runs=[TextRun(text)] if text else [])


def test_format_timestamp():
    assert format_timestamp(0) == "00:00:00,000"
    assert format_timestamp(3.5) == "00:00:03,500"
    assert format_timestamp(3661.001) == "01:01:01,001"


def test_cue_count_matches_segments():
    segs = [_seg(1, "가"), _seg(2, "나"), _seg(3, "다")]
    srt = to_srt(segs, [1.0, 2.0, 3.0])
    assert srt.count(" --> ") == 3


def test_cumulative_timing():
    segs = [_seg(1, "첫째"), _seg(2, "둘째")]
    srt = to_srt(segs, [3.0, 2.0])
    assert "1\n00:00:00,000 --> 00:00:03,000\n첫째" in srt
    assert "2\n00:00:03,000 --> 00:00:05,000\n둘째" in srt


def test_silent_segment_text_blank_but_timed():
    segs = [_seg(1, ""), _seg(2, "말")]
    srt = to_srt(segs, [6.0, 2.0])
    assert "1\n00:00:00,000 --> 00:00:06,000\n" in srt
    assert "2\n00:00:06,000 --> 00:00:08,000\n말" in srt


def test_audio_tags_absent_from_srt():
    # 오디오 태그는 자막에 나오지 않아야 한다(clean_text 에서 제거됨)
    segs = [_seg(1, "[warm] 안녕하세요 [pause] 반가워요")]
    srt = to_srt(segs, [3.0])
    assert "[" not in srt and "]" not in srt
    assert "warm" not in srt and "pause" not in srt
    assert "안녕하세요 반가워요" in srt
