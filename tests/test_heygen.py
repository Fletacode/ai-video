"""heygen 업로드 전처리(mp3 변환)·응답 파싱·한도 검사 (네트워크 없음)."""

import pytest
from pydub import AudioSegment

from slide_narrator.heygen import (
    MAX_UPLOAD_BYTES,
    ensure_mp3,
    parse_upload_result,
    upload_asset,
)


def test_ensure_mp3_passthrough_for_mp3(tmp_path):
    src = tmp_path / "a.mp3"
    AudioSegment.silent(duration=300).export(str(src), format="mp3")
    assert ensure_mp3(src, out_dir=tmp_path / "out") == src
    assert not (tmp_path / "out").exists()  # 변환 없음


def test_ensure_mp3_converts_wav(tmp_path):
    src = tmp_path / "a.wav"
    AudioSegment.silent(duration=300).export(str(src), format="wav")
    out = ensure_mp3(src, out_dir=tmp_path / "out")
    assert out == tmp_path / "out" / "a.mp3"
    assert out.exists()
    assert src.exists()  # 원본 불변
    assert len(AudioSegment.from_file(str(out))) == pytest.approx(300, abs=100)


def test_parse_upload_result_v3_data_shape():
    resp = {"data": {"asset_id": "aid-1", "url": "https://x", "name": "full.mp3"}}
    r = parse_upload_result(resp)
    assert r == {"asset_id": "aid-1", "url": "https://x", "name": "full.mp3"}


def test_parse_upload_result_flat_id_fallback():
    assert parse_upload_result({"id": "aid-2"})["asset_id"] == "aid-2"


def test_upload_asset_rejects_over_32mb(tmp_path):
    big = tmp_path / "big.mp3"
    big.write_bytes(b"\x00" * (MAX_UPLOAD_BYTES + 1))
    with pytest.raises(RuntimeError, match="32MB"):
        upload_asset(big, api_key="k")
