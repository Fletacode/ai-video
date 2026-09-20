"""ElevenLabs Sound Effects 로 징글/오프닝 음원 생성 CLI.

대본의 `(효과음 N초)` 마커가 참조하는 음원 자산을 1회 생성해 저장한다.
파이프라인이 마커의 N초에 맞춰 반복/컷으로 길이를 조정하므로 기본 8초면 충분하다.
(TTS 가 아니라 별도 Sound Effects API — 초당 40 크레딧, 0.1~30초 지정 가능.)

  uv run -m slide_narrator.sfx                                   # 기본 경쾌한 징글 8초 → assets/jingle.mp3
  uv run -m slide_narrator.sfx --preset opening                  # 오프닝 음악 → assets/opening.mp3
  uv run -m slide_narrator.sfx --prompt "..." --seconds 10 --out assets/ending.mp3
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from slide_narrator.tts import _read_env_value

_ROOT = Path(__file__).resolve().parents[2]

# 프리셋: jingle(전환/앤딩 징글), opening(영상 맨 처음 오프닝 음악)
PRESETS = {
    "jingle": {
        "prompt": (
            "Short upbeat cheerful educational jingle, bright marimba and ukulele, "
            "light percussion, clean ending, no vocals"
        ),
        "seconds": 8.0,
        "out": _ROOT / "assets" / "jingle.mp3",
    },
    "opening": {
        "prompt": (
            "Warm welcoming educational intro theme, bright piano and soft strings, "
            "gentle build-up, cheerful and inviting, clean ending, no vocals"
        ),
        "seconds": 10.0,
        "out": _ROOT / "assets" / "opening.mp3",
    },
}
DEFAULT_PRESET = "jingle"


def generate_sound_effect(prompt: str, seconds: float, api_key: str) -> bytes:
    """Sound Effects API 로 mp3 bytes 를 생성한다."""
    from elevenlabs.client import ElevenLabs

    client = ElevenLabs(api_key=api_key)
    stream = client.text_to_sound_effects.convert(
        text=prompt,
        duration_seconds=seconds,
        output_format="mp3_44100_128",
    )
    return b"".join(stream)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="ElevenLabs Sound Effects 징글/오프닝 음원 생성")
    p.add_argument(
        "--preset", choices=sorted(PRESETS), default=DEFAULT_PRESET,
        help="음원 종류별 기본 prompt/seconds/out 프리셋 (개별 옵션으로 덮어쓰기 가능)",
    )
    p.add_argument("--prompt", default=None)
    p.add_argument("--seconds", type=float, default=None)
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args(argv)
    preset = PRESETS[args.preset]
    if args.prompt is None:
        args.prompt = preset["prompt"]
    if args.seconds is None:
        args.seconds = preset["seconds"]
    if args.out is None:
        args.out = preset["out"]

    api_key = _read_env_value("ELEVENLABS_API_KEY")
    if not api_key:
        print("ELEVENLABS_API_KEY 가 필요합니다(.env)", file=sys.stderr)
        return 1

    try:
        data = generate_sound_effect(args.prompt, args.seconds, api_key)
    except Exception as e:  # ApiError 등
        if "missing_permissions" in str(e) or "sound_generation" in str(e):
            print(
                "❌ API 키에 sound_generation 권한이 없습니다.\n"
                "   ElevenLabs 대시보드 → API Keys → 해당 키 → permissions 에서\n"
                "   'Sound Effects'(sound_generation) 를 켜거나, 권한 제한 없는 키를 쓰세요.\n"
                "   대안: 준비된 음원을 assets/jingle.mp3 에 직접 두면 파이프라인이 사용합니다.",
                file=sys.stderr,
            )
            return 1
        raise
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(data)
    print(f"✅ {args.out} ({args.seconds:.1f}초 요청, {len(data)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
