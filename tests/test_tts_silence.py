"""build_segment_audio 의 무음 삽입 + elevenlabs synth 의 청킹 통합(네트워크 없음)."""

from io import BytesIO

from pydub import AudioSegment

from slide_narrator import tts
from slide_narrator.parse_script import Pause, Segment, Sfx, TextRun
from slide_narrator.tts import (
    ElevenConfig,
    build_segment_audio,
    chunk_text,
    fit_jingle,
    make_synth,
)


def fake_synth(text: str) -> AudioSegment:
    # 텍스트 1글자당 100ms 로 가정한 결정적 오디오
    return AudioSegment.silent(duration=len(text) * 100)


def test_silent_segment_uses_default_duration():
    seg = Segment(index=1, runs=[])
    audio = build_segment_audio(seg, fake_synth, default_silent_sec=6.0)
    assert len(audio) == 6000


def test_pause_inserted_as_real_silence():
    seg = Segment(index=2, runs=[TextRun("ab"), Pause(1.0), TextRun("c")])
    audio = build_segment_audio(seg, fake_synth)
    assert len(audio) == 1300


def test_multiple_pauses_sum():
    seg = Segment(index=3, runs=[Pause(2.0), TextRun("x"), Pause(1.5)])
    audio = build_segment_audio(seg, fake_synth)
    assert len(audio) == 2000 + 100 + 1500


def test_tag_only_segment_is_silent():
    # 태그만 있고 낭독 텍스트가 없으면 무음 세그먼트로 처리
    seg = Segment(index=4, runs=[TextRun("[warm]")])
    assert seg.is_silent is True
    audio = build_segment_audio(seg, fake_synth, default_silent_sec=3.0)
    assert len(audio) == 3000


def test_sfx_uses_jingle_fitted_to_duration():
    # 3초 음원이 반복 후 컷되어 마커의 8초에 정확히 맞는다
    jingle = AudioSegment.silent(duration=3000)
    seg = Segment(index=5, runs=[TextRun("ab"), Sfx(8.0)])
    audio = build_segment_audio(seg, fake_synth, jingle=jingle)
    assert len(audio) == 200 + 8000


def test_sfx_without_jingle_falls_back_to_silence():
    seg = Segment(index=6, runs=[TextRun("ab"), Sfx(2.0)])
    audio = build_segment_audio(seg, fake_synth)
    assert len(audio) == 200 + 2000


def test_sfx_only_segment_uses_marker_duration_not_default():
    # 징글만 있는 세그먼트는 default_silent_sec 이 아니라 마커의 N초를 쓴다
    seg = Segment(index=7, runs=[Sfx(4.0)])
    audio = build_segment_audio(seg, fake_synth, default_silent_sec=6.0)
    assert len(audio) == 4000


def test_fit_jingle_trims_long_asset():
    jingle = AudioSegment.silent(duration=10_000)
    assert len(fit_jingle(jingle, 8.0)) == 8000


def _tone(ms: int) -> AudioSegment:
    # 무음(jingle 더미)과 구별 가능한, 진폭이 있는 결정적 오디오
    n_frames = 44100 * ms // 1000
    return AudioSegment(
        data=b"\x10\x27" * n_frames, sample_width=2, frame_rate=44100, channels=1
    )


def test_leading_sfx_uses_opening_in_opening_segment():
    # 첫 세그먼트의 선행 Sfx(오프닝 음악)는 jingle 이 아니라 opening 을 쓴다
    opening, jingle = _tone(1000), AudioSegment.silent(duration=1000)
    seg = Segment(index=1, runs=[Sfx(2.0), TextRun("ab")])
    audio = build_segment_audio(
        seg, fake_synth, jingle=jingle, opening=opening, is_opening_segment=True
    )
    assert len(audio) == 2000 + 200
    assert audio[:1000].max > 0  # 앞 구간이 opening(비무음)


def test_leading_sfx_uses_jingle_when_not_opening_segment():
    opening, jingle = _tone(1000), AudioSegment.silent(duration=1000)
    seg = Segment(index=2, runs=[Sfx(2.0), TextRun("ab")])
    audio = build_segment_audio(
        seg, fake_synth, jingle=jingle, opening=opening, is_opening_segment=False
    )
    assert audio[:1000].max == 0  # 첫 세그먼트가 아니면 jingle(무음 더미)


def test_trailing_sfx_uses_jingle_even_in_opening_segment():
    # 나레이션 뒤(앤딩 자리) Sfx 는 첫 세그먼트라도 jingle 을 쓴다
    opening, jingle = _tone(1000), AudioSegment.silent(duration=1000)
    seg = Segment(index=1, runs=[TextRun("ab"), Sfx(2.0)])
    audio = build_segment_audio(
        seg, fake_synth, jingle=jingle, opening=opening, is_opening_segment=True
    )
    assert audio[200:].max == 0


def test_leading_sfx_falls_back_to_jingle_without_opening():
    jingle = _tone(1000)
    seg = Segment(index=1, runs=[Sfx(2.0), TextRun("ab")])
    audio = build_segment_audio(
        seg, fake_synth, jingle=jingle, opening=None, is_opening_segment=True
    )
    assert audio[:1000].max > 0  # opening 이 없으면 jingle 로 폴백


def _dummy_mp3(ms: int) -> bytes:
    buf = BytesIO()
    AudioSegment.silent(duration=ms).export(buf, format="mp3")
    return buf.getvalue()


def test_elevenlabs_synth_chunks_long_text(monkeypatch):
    """긴 TextRun 은 chunk_text 조각 수만큼 v3 호출로 나뉘고, 오디오는 이어붙여진다."""
    calls = []

    def fake_convert(text, cfg, **kwargs):
        calls.append(text)
        # seed 는 모든 청크에 동일하게 전달되어야 한다(톤 일관성)
        assert kwargs.get("seed") == 42
        return _dummy_mp3(100), "rid-x"

    monkeypatch.setattr(tts, "synthesize_elevenlabs", fake_convert)

    cfg = ElevenConfig(api_key="x", voice_id="v", model_id="eleven_v3", seed=42)
    synth = make_synth("elevenlabs", cfg=cfg)

    long_text = ("가나다라마바사. " * 500).strip()  # > V3_CHAR_LIMIT
    expected_chunks = chunk_text(long_text)
    assert len(expected_chunks) >= 2  # 실제로 여러 조각이어야 유의미한 테스트

    audio = synth(long_text)
    assert len(calls) == len(expected_chunks)
    assert len(audio) == 100 * len(expected_chunks)


def test_elevenlabs_synth_single_call_for_short_text(monkeypatch):
    calls = []
    monkeypatch.setattr(
        tts,
        "synthesize_elevenlabs",
        lambda text, cfg, **kw: (calls.append(text) or _dummy_mp3(100), "rid"),
    )
    cfg = ElevenConfig(api_key="x", voice_id="v", model_id="eleven_v3", seed=42)
    synth = make_synth("elevenlabs", cfg=cfg)
    synth("[warm] 짧은 문장이에요.")
    assert len(calls) == 1
    assert "[warm]" in calls[0]  # 태그가 v3 로 전달됨
