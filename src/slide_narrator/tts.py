"""TTS 합성 + 쉼(무음) 삽입 + v3 문자수 한도 청킹.

- gTTS(ko) / ElevenLabs(eleven_v3 전제) 를 동일한 `synth(text) -> AudioSegment`
  인터페이스로 감싼다.
- 세그먼트의 TextRun/Pause 런을 순서대로 이어 붙여 세그먼트 오디오를 만든다.
  Pause 는 실제 무음(AudioSegment.silent)으로 삽입한다.
- 오디오 태그([warm] 등)는 텍스트 그대로 v3 로 전달된다(별도 파라미터 아님).
- 긴 TextRun 은 v3 요청 한도(V3_CHAR_LIMIT) 이하로 청킹하되, 같은 seed 로 합성해
  청크 간 톤 일관성을 유지한다.

(connect-ppt/src/connect_ppt/tts.py 에서 이식·확장)
"""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Callable, List, Optional

from pydub import AudioSegment

from slide_narrator.parse_script import Pause, Segment, Sfx, TextRun

# .env 우선순위: slide-narrator/.env → connect-ppt/.env → redub/.env → 환경변수
_PKG_ROOT = Path(__file__).resolve().parents[2]
_ENV_PATHS = [
    _PKG_ROOT / ".env",
    _PKG_ROOT.parent / "connect-ppt" / ".env",
    _PKG_ROOT.parent / "redub" / ".env",
]

DEFAULT_TTS_MODEL = "eleven_v3"
DEFAULT_LANG = "ko"
# eleven_v3 등 스티칭 미지원 모델에서 세그먼트/청크 간 톤 일관성을 위한 기본 seed.
# ELEVENLABS_SEED 환경변수로 override 가능.
DEFAULT_ELEVEN_SEED = 42
# eleven_v3 요청당 문자수 소프트 상한(하드 리밋 아래로 여유). 초과 시 청킹.
V3_CHAR_LIMIT = 3000


@dataclass
class ElevenConfig:
    api_key: str
    voice_id: str
    model_id: str
    seed: Optional[int] = None


def _read_env_value(key: str) -> str:
    val = os.environ.get(key)
    if val:
        return val.strip()
    for env_path in _ENV_PATHS:
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith(f"{key}="):
                    return line.split("=", 1)[1].strip()
    return ""


def load_eleven_cfg() -> ElevenConfig:
    """ElevenLabs 설정을 읽는다. sts(음성변환) 모델이면 TTS 기본 모델로 보정."""
    env_model = _read_env_value("ELEVENLABS_MODEL_ID")
    if not env_model or "sts" in env_model.lower():
        model_id = DEFAULT_TTS_MODEL
    else:
        model_id = env_model
    seed_raw = _read_env_value("ELEVENLABS_SEED")
    try:
        seed = int(seed_raw) if seed_raw else DEFAULT_ELEVEN_SEED
    except ValueError:
        seed = DEFAULT_ELEVEN_SEED
    cfg = ElevenConfig(
        api_key=_read_env_value("ELEVENLABS_API_KEY"),
        voice_id=_read_env_value("ELEVENLABS_VOICE_ID"),
        model_id=model_id,
        seed=seed,
    )
    missing = [
        name
        for name, v in (
            ("ELEVENLABS_API_KEY", cfg.api_key),
            ("ELEVENLABS_VOICE_ID", cfg.voice_id),
        )
        if not v
    ]
    if missing:
        raise RuntimeError(
            f"ElevenLabs 설정 누락: {', '.join(missing)} "
            f"({_ENV_PATHS[0]} 또는 환경변수에 설정하세요)"
        )
    return cfg


# ---- v3 문자수 한도 청킹 --------------------------------------------------

_TAG_RE = re.compile(r"\[[^\[\]\n]+\]")
_SENT_SPLIT = re.compile(r"(?<=[.?!。！？])\s+")


def _tokenize_atoms(text: str) -> List[str]:
    """텍스트를 원자 토큰 리스트로 나눈다: [태그] 는 통째로, 나머지는 공백 단위 단어."""
    atoms: List[str] = []
    pos = 0
    for m in _TAG_RE.finditer(text):
        atoms.extend(text[pos : m.start()].split())
        atoms.append(m.group(0))
        pos = m.end()
    atoms.extend(text[pos:].split())
    return atoms


def _pack(units: List[str], limit: int) -> List[str]:
    """units 를 limit 이하 청크로 그리디 결합(단어 사이 공백 1개로 재조립)."""
    chunks: List[str] = []
    cur = ""
    for u in units:
        candidate = u if not cur else f"{cur} {u}"
        if len(candidate) <= limit:
            cur = candidate
            continue
        if cur:
            chunks.append(cur)
            cur = ""
        if len(u) <= limit:
            cur = u
            continue
        # 단일 unit 이 한도 초과 → 더 작은 원자(단어/태그)로 재분할
        atoms = _tokenize_atoms(u)
        if len(atoms) > 1:
            chunks.extend(_pack(atoms, limit))
        else:
            # 공백 없는 초장문 단일 토큰 → 강제 컷(현실적으로 발생하지 않음)
            for j in range(0, len(u), limit):
                chunks.append(u[j : j + limit])
    if cur:
        chunks.append(cur)
    return chunks


def chunk_text(text: str, limit: int = V3_CHAR_LIMIT) -> List[str]:
    """긴 텍스트를 v3 요청 한도 이하 조각으로 나눈다.

    - 한도 이하면 그대로 [text] 반환(대부분의 슬라이드).
    - 초과하면 문장 경계 우선으로 나누고, 필요 시 단어 경계로 재분할한다.
    - [태그] 는 절대 조각 경계로 쪼개지 않는다(원자 토큰으로 취급).
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]
    return _pack(_SENT_SPLIT.split(text), limit)


# ---- 저수준 합성 (bytes) -------------------------------------------------


def synthesize_gtts(text: str, lang: str = DEFAULT_LANG) -> bytes:
    """gTTS 로 mp3 bytes 반환(API 키 불필요, 미리보기용)."""
    from gtts import gTTS

    tts = gTTS(text=text, lang=lang)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        tts.save(tmp_path)
        return Path(tmp_path).read_bytes()
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def synthesize_elevenlabs(
    text: str,
    cfg: ElevenConfig,
    *,
    previous_request_ids: Optional[List[str]] = None,
    previous_text: Optional[str] = None,
    seed: Optional[int] = None,
) -> "tuple[bytes, str]":
    """ElevenLabs SDK 로 (mp3 bytes, request-id) 반환.

    - 오디오 태그([warm] 등)는 text 에 그대로 담겨 전달된다(별도 파라미터 아님).
    - eleven_v3: request-id 스티칭·previous_text/next_text 모두 미지원(400).
      seed(결정론적 샘플링)만으로 톤 일관성을 확보한다.
    - 비-v3 모델: previous_request_ids/previous_text 로 연속성 유지.
    """
    from elevenlabs import VoiceSettings
    from elevenlabs.client import ElevenLabs

    client = ElevenLabs(api_key=cfg.api_key)
    convert_kwargs = dict(
        voice_id=cfg.voice_id,
        text=text,
        model_id=cfg.model_id,
        output_format="mp3_44100_128",
        voice_settings=VoiceSettings(
            stability=0.5,
            similarity_boost=0.75,
            style=0.0,
            use_speaker_boost=True,
        ),
    )
    # seed: 결정론적 샘플링으로 톤 일관성(모든 모델 지원, v3 포함).
    if seed is not None:
        convert_kwargs["seed"] = seed
    # eleven_v3 계열은 request-id 스티칭과 previous_text/next_text 모두 미지원(400).
    supports_stitching = not cfg.model_id.startswith("eleven_v3")
    if supports_stitching:
        if previous_text:
            convert_kwargs["previous_text"] = previous_text
        if previous_request_ids:
            convert_kwargs["previous_request_ids"] = previous_request_ids
    with client.text_to_speech.with_raw_response.convert(**convert_kwargs) as response:
        rid = response._response.headers.get("request-id", "")
        audio = b"".join(chunk for chunk in response.data)
    return audio, rid


# ---- synth 팩토리 (text -> AudioSegment) ---------------------------------

Synth = Callable[[str], AudioSegment]


def make_synth(
    engine: str, cfg: Optional[ElevenConfig] = None, lang: str = DEFAULT_LANG
) -> Synth:
    """엔진별 synth 함수를 만든다. ElevenLabs 는 청킹 + seed 로 톤 일관성을 유지."""
    if engine == "gtts":
        def synth(text: str) -> AudioSegment:
            data = synthesize_gtts(text, lang=lang)
            return AudioSegment.from_file(BytesIO(data), format="mp3")

        return synth

    if engine == "elevenlabs":
        if cfg is None:
            cfg = load_eleven_cfg()
        prev_ids: List[str] = []  # 비-v3 모델용 request-id 문맥
        prev_text = ""            # 비-v3 모델용 텍스트 연속성 문맥

        def synth(text: str) -> AudioSegment:
            nonlocal prev_text
            out = AudioSegment.silent(duration=0)
            # 긴 텍스트는 v3 한도 이하로 청킹. 같은 seed → 청크 간 톤 일관성.
            for piece in chunk_text(text):
                data, rid = synthesize_elevenlabs(
                    piece,
                    cfg,
                    previous_request_ids=prev_ids[-3:],  # v3 에선 내부에서 무시됨
                    previous_text=prev_text or None,      # v3 에선 내부에서 무시됨
                    seed=cfg.seed,
                )
                if rid:
                    prev_ids.append(rid)
                prev_text = piece
                out += AudioSegment.from_file(BytesIO(data), format="mp3")
            return out

        return synth

    raise ValueError(f"지원하지 않는 엔진: {engine}")


# ---- 세그먼트 오디오 조립 -------------------------------------------------


def fit_jingle(asset: AudioSegment, seconds: float) -> AudioSegment:
    """징글 음원을 정확히 seconds 길이로 맞춘다(짧으면 반복, 길면 컷 후 페이드아웃)."""
    ms = max(0, int(seconds * 1000))
    if ms == 0 or len(asset) == 0:
        return AudioSegment.silent(duration=ms)
    out = asset
    while len(out) < ms:
        out += asset
    out = out[:ms]
    return out.fade_out(min(800, max(1, ms // 4)))


def build_segment_audio(
    segment: Segment,
    synth: Synth,
    *,
    default_silent_sec: float = 6.0,
    bgm: Optional[AudioSegment] = None,
    jingle: Optional[AudioSegment] = None,
    opening: Optional[AudioSegment] = None,
    is_opening_segment: bool = False,
) -> AudioSegment:
    """세그먼트 런을 순서대로 합성/무음/징글로 이어 붙인다.

    무음 세그먼트(배경음악만)는 default_silent_sec 길이의 무음. bgm 이 있으면 덧입힌다.
    Sfx 런(`(효과음 N초)`)은 jingle 음원을 N초에 맞춰 삽입한다(음원 없으면 N초 무음).
    단, 영상 맨 처음의 오프닝 음악 — is_opening_segment=True 인 세그먼트에서
    나레이션(TextRun)보다 앞에 오는 Sfx — 은 jingle 대신 opening 음원을 쓴다
    (opening 이 없으면 jingle 로 폴백).
    """
    has_sfx = any(isinstance(r, Sfx) for r in segment.runs)
    if segment.is_silent and not has_sfx:
        audio = AudioSegment.silent(duration=int(default_silent_sec * 1000))
        if bgm is not None:
            audio = audio.overlay(bgm[: len(audio)])
        return audio

    audio = AudioSegment.silent(duration=0)
    before_narration = True
    for run in segment.runs:
        if isinstance(run, TextRun):
            before_narration = False
            audio += synth(run.text)
        elif isinstance(run, Pause):
            audio += AudioSegment.silent(duration=int(run.seconds * 1000))
        elif isinstance(run, Sfx):
            asset = jingle
            if is_opening_segment and before_narration and opening is not None:
                asset = opening
            if asset is not None:
                audio += fit_jingle(asset, run.seconds)
            else:
                audio += AudioSegment.silent(duration=int(run.seconds * 1000))
    return audio


def combine_audio(paths: "List[Path]", out_path: Path) -> float:
    """세그먼트 mp3 들을 순서대로 이어붙여 out_path(mp3)로 저장하고 길이(초)를 반환."""
    combined = AudioSegment.silent(duration=0)
    for p in paths:
        combined += AudioSegment.from_file(str(p))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    combined.export(str(out_path), format="mp3")
    return len(combined) / 1000.0


def synthesize_segment(
    segment: Segment,
    synth: Synth,
    out_path: Path,
    *,
    default_silent_sec: float = 6.0,
    bgm: Optional[AudioSegment] = None,
    jingle: Optional[AudioSegment] = None,
    opening: Optional[AudioSegment] = None,
    is_opening_segment: bool = False,
) -> float:
    """세그먼트 오디오를 만들어 out_path(mp3)로 저장하고 길이(초)를 반환."""
    audio = build_segment_audio(
        segment, synth, default_silent_sec=default_silent_sec, bgm=bgm, jingle=jingle,
        opening=opening, is_opening_segment=is_opening_segment,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    audio.export(str(out_path), format="mp3")
    return len(audio) / 1000.0
