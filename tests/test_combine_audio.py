"""combine_audio: 세그먼트 mp3 들을 하나로 합쳐 전체 나레이션 mp3 를 만든다."""

from pydub import AudioSegment

from slide_narrator.tts import combine_audio


def test_combine_audio_sums_durations(tmp_path):
    a, b = tmp_path / "a.mp3", tmp_path / "b.mp3"
    AudioSegment.silent(duration=1000).export(str(a), format="mp3")
    AudioSegment.silent(duration=2000).export(str(b), format="mp3")

    out = tmp_path / "full.mp3"
    dur = combine_audio([a, b], out)

    assert out.exists()
    # mp3 인코더 지연/패딩 오차 허용
    assert abs(dur - 3.0) < 0.3
