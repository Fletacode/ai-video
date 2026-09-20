# CLAUDE.md — slide-narrator

이 저장소에서 작업하는 Claude Code 를 위한 안내.

## 프로젝트 개요

슬라이드(PDF) + 기존 대본 → **v3 최적화 대본** → eleven_v3 TTS → 슬라이드 1:1 자동 전환 영상.

**두 단계**로 나뉜다:

- **Phase A (작성)** — *네가(Claude Code) 한다.* 슬라이드 이미지와 원본 대본을 보고
  [`docs/AUTHORING_GUIDE.md`](docs/AUTHORING_GUIDE.md) + [`docs/SCRIPT_FORMAT.md`](docs/SCRIPT_FORMAT.md)
  를 따라 v3 대본(`docs/<과>/<name>.v3.md`)을 작성한다.
- **Phase B (렌더)** — *코드가 한다.* 작성된 대본을 파싱 → TTS → 영상/자막.

**docs/ 구조**: 과별 자료는 `docs/<과>/`(예: `docs/1-1/`, `docs/6-5/`)에 PDF·원본 대본·v3 대본을
묶어서 두고, 공용 가이드(`SCRIPT_FORMAT.md`, `AUTHORING_GUIDE.md`)만 `docs/` 루트에 둔다.
새 과를 추가할 때도 같은 규칙을 따른다.

## 절대 규칙

- **코드는 어떤 LLM/Anthropic API 도 호출하지 않는다.** 대본을 만드는 "에이전트"는 이 가이드를
  따르는 Claude Code(사람이 대화로 구동)다. 자동 생성 API 호출을 코드에 넣지 말 것.
- 대본 작성 시 **교육 자료의 정답·어휘·예문은 원문 그대로** 유지(구어체화는 하되 의미 불변).

## 작성 작업 시 읽는 순서
1. [`docs/SCRIPT_FORMAT.md`](docs/SCRIPT_FORMAT.md) (포맷 규격)
2. [`docs/AUTHORING_GUIDE.md`](docs/AUTHORING_GUIDE.md) (작성 절차)
3. `python -m slide_narrator.prep --pdf docs/<과>/<과>.pdf` 로 슬라이드 렌더
4. `build/slides/<과>/slide_NN.png` 를 보고 원본 대본과 대조하며 작성

## 명령어

```bash
uv sync                                                # 환경 구성 (또는 uv venv + uv pip install)
uv run -m slide_narrator.prep --pdf docs/1-1/1-1.pdf   # Phase A 준비(슬라이드 렌더)
uv run -m slide_narrator.pipeline --engine gtts        # Phase B 미리보기 → build/preview.mp4
uv run -m slide_narrator.pipeline --engine elevenlabs  # Phase B 최종(v3) → build/final.mp4
uv run -m slide_narrator.sfx                           # 징글 음원 생성 → assets/jingle.mp3 (1회)
uv run -m slide_narrator.sfx --preset opening          # 오프닝 음원 생성 → assets/opening.mp3 (1회)
uv run -m slide_narrator.heygen                        # HeyGen 에셋 업로드 (mp3 아니면 자동 변환)
uv run pytest -q                                       # 테스트
```

**Phase B 슬라이드(과) 선택**: `--pdf` + `--script` 를 같은 과의 파일 쌍으로 지정한다.
슬라이드는 `--pdf` 에서 **과별 폴더** `build/slides/<과>/`(PDF 파일명 기준)로 렌더·캐시되며,
PDF 내용·zoom 이 바뀌면 자동으로 다시 렌더된다. PDF 페이지 수와 대본의
`**[n]**` 헤더 수가 1:1 이어야 한다.

```bash
uv run -m slide_narrator.pipeline --engine gtts \
    --pdf docs/6-5/6-5.pdf --script docs/6-5/6-5_나레이션대본.v3.md
```

## 환경 (.env)
- `.env` 우선순위: `slide-narrator/.env` → `../connect-ppt/.env` → `../redub/.env` → 환경변수.
- 키: `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, `ELEVENLABS_MODEL_ID=eleven_v3`, `ELEVENLABS_SEED`(선택),
  `HEYGEN_API_KEY`(HeyGen 업로드 시).
- **eleven_v3 전제**: v3 는 request 스티칭·`previous_text`/`next_text`·SSML `<break>` 미지원(400/무시).
  코드는 v3 에서 이를 자동으로 끄고 `seed` 로만 톤 일관성을 유지한다. 오디오 태그는 텍스트로 전달된다.
- **쉼 처리**: 실제 무음이 아니라 v3 인라인 쉼 태그(`[short pause]`/`[long pause]`/`[pause]`)로 표현한다.
  세그먼트 본문은 쉼 태그를 포함한 단일 텍스트로 합성되어 **슬라이드당 v3 요청 1회**다.
  legacy `(N초동안 쉼,공백)` 은 파서가 쉼 태그로 자동 변환(1초→short, 2초→long)한다.
- **효과음(징글·오프닝)**: 대본의 `(효과음 N초)` 마커 위치에 `--jingle` 음원(기본 `assets/jingle.mp3`)을
  N초로 맞춰(반복/컷+페이드아웃) 삽입한다. 단 **영상 맨 처음의 오프닝 음악**(첫 세그먼트에서
  나레이션보다 앞에 오는 마커)은 `--opening` 음원(기본 `assets/opening.mp3`)을 쓴다 —
  오프닝 음원이 없으면 징글로 대체. 음원이 둘 다 없으면 N초 무음. v3 태그로 음악을 만들지 않는다.
  음원 생성은 `slide_narrator.sfx`(ElevenLabs Sound Effects, 초당 40크레딧) — `--preset jingle|opening`.

## 코드 지도 (`src/slide_narrator/`)
| 모듈 | 역할 |
|---|---|
| `parse_script.py` | v3 대본 → Segment(세그먼트당 단일 TextRun). 쉼 마커→인라인 쉼 태그, `(효과음 N초)`→Sfx 런, 태그는 TTS엔 보존·자막엔 제거 |
| `tts.py` | gTTS/eleven_v3 합성(슬라이드당 1회), 쉼=v3 태그(텍스트 전달), Sfx=징글/오프닝 삽입(`fit_jingle`, 첫 세그먼트 선행 Sfx 는 opening), v3 문자수 청킹(`chunk_text`) |
| `sfx.py` | ElevenLabs Sound Effects 로 징글/오프닝 음원 생성 CLI (`--preset jingle\|opening`) |
| `slides.py` | PDF → 슬라이드 PNG (PyMuPDF, 흰 여백 제거) |
| `video.py` | 이미지+오디오 → MP4 (ffmpeg, 측정 길이만큼 정지 후 concat) |
| `srt.py` | 세그먼트+길이 → SRT (clean_text 사용) |
| `prep.py` | Phase A: 작성용 슬라이드 렌더 CLI |
| `pipeline.py` | Phase B: 파싱→TTS→영상→SRT 오케스트레이터 CLI |
| `heygen.py` | 나레이션 음성 HeyGen 에셋 업로드 CLI (`/v3/assets`, **mp3 필수 — 아니면 자동 변환**, 32MB 한도) |

## 재사용 출처
`slides.py`/`video.py`/`srt.py`/`tts.py`/`parse_script.py` 는 `../connect-ppt` 에서 이식했다.
동기화 원리(측정된 오디오 길이만큼 슬라이드 정지, 1:1 하드 컷)는 동일하다.
