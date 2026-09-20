"""HeyGen 에셋 업로드 CLI.

나레이션 음성을 HeyGen 에셋으로 업로드한다. **HeyGen 업로드는 mp3 포맷이어야 하므로**,
입력이 mp3 가 아니면(wav/m4a/mp4 등) 먼저 mp3 로 변환한 뒤 업로드한다
(변환본은 build/heygen/ 에 저장, ffmpeg 필요).

  POST https://api.heygen.com/v3/assets  (multipart, X-Api-Key, 파일당 최대 32MB)

  uv run -m slide_narrator.heygen                                  # 기본: build/audio/full_elevenlabs.mp3
  uv run -m slide_narrator.heygen build/audio/seg_01.mp3 build/audio/seg_02.mp3
  uv run -m slide_narrator.heygen narration.wav --bitrate 192k     # mp3 변환 후 업로드

API 키는 HEYGEN_API_KEY — slide-narrator/.env → ../connect-ppt/.env → ../redub/.env
→ 환경변수 순으로 읽는다(tts._read_env_value 재사용).
(../connect-ppt/src/connect_ppt/heygen.py 의 v3 업로드를 이식·확장)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

import requests

from slide_narrator.tts import _read_env_value

_ROOT = Path(__file__).resolve().parents[2]

ASSETS_URL = "https://api.heygen.com/v3/assets"
MAX_UPLOAD_BYTES = 32 * 1024 * 1024  # HeyGen 에셋 업로드 한도(32MB)
DEFAULT_FILE = _ROOT / "build" / "audio" / "full_elevenlabs.mp3"
CONVERT_DIR = _ROOT / "build" / "heygen"
DEFAULT_BITRATE = "192k"


def load_api_key() -> str:
    key = _read_env_value("HEYGEN_API_KEY")
    if not key:
        raise RuntimeError("HEYGEN_API_KEY 미설정 (.env 또는 환경변수에 설정하세요)")
    return key


def ensure_mp3(
    path: Path, *, bitrate: str = DEFAULT_BITRATE, out_dir: Path = CONVERT_DIR
) -> Path:
    """HeyGen 업로드 전제인 mp3 를 보장한다.

    이미 .mp3 면 그대로 반환하고, 아니면 out_dir/<stem>.mp3 로 변환해(원본 불변)
    변환본 경로를 반환한다. 영상(mp4 등)을 주면 오디오 트랙만 추출된다.
    """
    if path.suffix.lower() == ".mp3":
        return path
    from pydub import AudioSegment  # ffmpeg 필요

    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{path.stem}.mp3"
    AudioSegment.from_file(str(path)).export(str(out), format="mp3", bitrate=bitrate)
    return out


def parse_upload_result(resp: dict) -> dict:
    """업로드 응답에서 asset_id/url/name 을 견고하게 추출한다."""
    inner = resp.get("data", resp)
    return {
        "asset_id": inner.get("asset_id") or inner.get("id") or "",
        "url": inner.get("url", ""),
        "name": inner.get("name", ""),
    }


def upload_asset(file_path: Path, api_key: Optional[str] = None) -> dict:
    """mp3 파일 하나를 HeyGen 에셋으로 업로드하고 파싱된 결과를 반환한다."""
    if api_key is None:
        api_key = load_api_key()
    size = file_path.stat().st_size
    if size > MAX_UPLOAD_BYTES:
        raise RuntimeError(
            f"{file_path.name} 이 {size / 1e6:.1f}MB 로 HeyGen 한도(32MB)를 초과합니다. "
            f"--bitrate 를 낮추거나 파일을 나눠 업로드하세요."
        )
    with open(file_path, "rb") as f:
        resp = requests.post(
            ASSETS_URL,
            headers={"X-Api-Key": api_key},
            files={"file": (file_path.name, f, "audio/mpeg")},
            timeout=300,
        )
    if resp.status_code != 200:
        raise RuntimeError(f"HeyGen 업로드 실패: {resp.status_code} {resp.text}")
    return parse_upload_result(resp.json())


def upload(
    paths: List[Path], *, bitrate: str = DEFAULT_BITRATE, api_key: Optional[str] = None
) -> List[dict]:
    """파일들을 (필요 시 mp3 변환 후) 순서대로 업로드하고 결과 리스트를 반환한다."""
    if api_key is None:
        api_key = load_api_key()
    results = []
    for p in paths:
        mp3 = ensure_mp3(p, bitrate=bitrate)
        if mp3 != p:
            print(f"[convert] {p} → {mp3}")
        r = upload_asset(mp3, api_key=api_key)
        print(f"[upload] {mp3.name} → asset_id={r['asset_id']}")
        results.append(r)
    return results


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="나레이션 음성을 HeyGen 에셋으로 업로드(mp3 아니면 변환 후 업로드)"
    )
    p.add_argument(
        "files", nargs="*", type=Path, default=None,
        help=f"업로드할 음성 파일들 (기본: {DEFAULT_FILE.relative_to(_ROOT)})",
    )
    p.add_argument(
        "--bitrate", default=DEFAULT_BITRATE,
        help=f"mp3 변환 시 비트레이트 (기본 {DEFAULT_BITRATE})",
    )
    args = p.parse_args(argv)
    files = args.files or [DEFAULT_FILE]

    missing = [f for f in files if not f.exists()]
    if missing:
        print(f"❌ 파일 없음: {', '.join(map(str, missing))}", file=sys.stderr)
        return 1
    try:
        results = upload(files, bitrate=args.bitrate)
    except RuntimeError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1
    print(f"\n✅ {len(results)}개 업로드 완료")
    for r in results:
        print(f"   {r['name'] or '(이름 없음)'}: {r['asset_id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
