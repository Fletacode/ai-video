# slide-narrator

슬라이드(PDF) + 기존 대본을 **Claude Code 에이전트**가 보고, eleven_v3 로 자연스럽게 읽히도록
**새 대본 포맷**을 작성한 뒤, 코드가 **v3 TTS → 생성된 음성 길이에 맞춰 슬라이드가 전환되는
영상**을 만든다.

## 두 단계

```
원본 대본(.md) ─┐
                ├─► [Phase A] Claude Code 가 슬라이드를 보고 v3 대본(.v3.md) 작성
슬라이드(PDF) ──┘        (docs/SCRIPT_FORMAT.md + docs/AUTHORING_GUIDE.md 규격)
                                    │
                                    ▼
              [Phase B] 코드: v3 대본 파싱 → eleven_v3 TTS(쉼=무음, 태그=v3 전달)
                        → 세그먼트별 오디오 길이 측정 → 슬라이드 1:1 전환 영상 + SRT
                                    │
                                    ▼
                     build/final.mp4  +  build/script.srt
```

- **동기화**: 슬라이드 1장 = 세그먼트 1개. 각 세그먼트 오디오를 **먼저 합성해 길이를 재고**,
  그 길이만큼 슬라이드를 정지시킨 뒤 다음 장으로 하드 컷한다(측정 후 렌더 → 어긋나지 않음).
- **오디오 파일**: 슬라이드마다 `build/audio/seg_NN.mp3` 1개(내부적으로 v3 호출은 여러 번일 수 있음).

## 설치

```bash
uv sync            # 또는: uv venv --python 3.11 && uv pip install -e .
# 시스템 의존성: ffmpeg
```

`.env` 설정(없으면 `../connect-ppt/.env` → `../redub/.env` fallback):
```
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=...
ELEVENLABS_MODEL_ID=eleven_v3
ELEVENLABS_SEED=42
HEYGEN_API_KEY=...        # HeyGen 업로드 사용 시
```

## 사용법

### Phase A — v3 대본 작성 (Claude Code)
```bash
uv run -m slide_narrator.prep --pdf docs/1-1/1-1.pdf    # 슬라이드를 build/slides/1-1/ 로 렌더
```
그런 다음 이 폴더에서 **Claude Code** 를 열고 [`docs/AUTHORING_GUIDE.md`](docs/AUTHORING_GUIDE.md)
를 따라 `docs/1-1/1-1_나레이션대본.v3.md` 를 작성한다.

### 효과음(징글·오프닝) 준비 — 선택, 최초 1회
대본의 `(효과음 N초)` 마커에 삽입될 음원을 만든다. **영상 맨 처음(첫 슬라이드, 나레이션 앞)의
마커는 오프닝 음악**으로 `assets/opening.mp3` 가, 나머지(전환/앤딩)는 `assets/jingle.mp3` 가 쓰인다:
```bash
uv run -m slide_narrator.sfx                          # 기본: 경쾌한 징글 8초 → assets/jingle.mp3
uv run -m slide_narrator.sfx --preset opening         # 오프닝 음악 10초 → assets/opening.mp3
uv run -m slide_narrator.sfx --prompt "soft calm outro chime" --seconds 10 --out assets/ending.mp3
```
- ElevenLabs **Sound Effects API** 를 사용한다(초당 40크레딧, 0.1~30초 지정 가능).
  API 키에 `sound_generation` 권한이 필요하다(대시보드 → API Keys → permissions → Sound Effects).
- 파이프라인이 마커의 N초에 맞춰 길이를 조정하므로(짧으면 반복, 길면 컷+페이드아웃)
  기본 한 개씩이면 충분하다.
- 생성 대신 준비된 mp3 를 `assets/jingle.mp3` / `assets/opening.mp3` 에 직접 두어도 된다.
  오프닝 음원이 없으면 징글로 대체되고, 징글도 없으면 마커 자리는 N초 무음이 된다(경고 출력).

### Phase B — 영상 렌더 (코드)

**슬라이드(과) 선택**: `--pdf` 와 `--script` 를 **같은 과의 파일 쌍**으로 지정한다
(`docs/<과>/` 폴더에 과별로 모여 있다). 슬라이드는 `--pdf` 에서 **과별 폴더**
`build/slides/<과>/`(PDF 파일명 기준)로 렌더·캐시되고, PDF 내용·zoom 이 바뀌면 자동으로
다시 렌더된다. PDF 페이지 수와 대본의 `**[n]**` 헤더 수가 1:1 이어야 한다.

```bash
# 미리보기 (gTTS, 무료·빠름) → build/preview.mp4
uv run -m slide_narrator.pipeline --engine gtts \
    --pdf docs/1-1/1-1.pdf --script docs/1-1/1-1_나레이션대본.v3.md

# 다른 과(예: 6-5) 렌더
uv run -m slide_narrator.pipeline --engine gtts \
    --pdf docs/6-5/6-5.pdf --script docs/6-5/6-5_나레이션대본.v3.md

# 최종 (eleven_v3) → build/final.mp4 + build/audio/full_elevenlabs.mp3
uv run -m slide_narrator.pipeline --engine elevenlabs \
    --pdf docs/6-5/6-5.pdf --script docs/6-5/6-5_나레이션대본.v3.md
```

옵션: `--limit N`(앞 N개만 빠른 확인), `--zoom`(렌더 배율), `--no-trim`(여백 제거 끄기),
`--default-silent-sec`(무음 슬라이드 길이), `--bgm`(무음 슬라이드 배경음악),
`--jingle`(`(효과음 N초)` 마커용 음원, 기본 `assets/jingle.mp3`),
`--opening`(첫 슬라이드 오프닝 음원, 기본 `assets/opening.mp3`, 없으면 징글로 대체).

### HeyGen 업로드 — 나레이션 음성을 에셋으로 올리기

렌더된 나레이션 음성을 HeyGen 에셋(`POST /v3/assets`)으로 업로드한다.
**HeyGen 업로드는 mp3 포맷이어야 한다** — 입력이 mp3 가 아니면(wav/m4a/mp4 등)
자동으로 mp3 로 변환한 뒤 업로드한다(변환본은 `build/heygen/` 에 저장, 원본 불변).

```bash
uv run -m slide_narrator.heygen                          # 기본: build/audio/full_elevenlabs.mp3
uv run -m slide_narrator.heygen build/audio/seg_01.mp3 build/audio/seg_02.mp3   # 여러 파일
uv run -m slide_narrator.heygen narration.wav --bitrate 192k   # mp3 변환 후 업로드
```

- 성공 시 파일별 `asset_id` 를 출력한다(HeyGen 아바타 영상 생성 등에 사용).
- `HEYGEN_API_KEY` 가 필요하다(.env fallback 체인에서 읽음 — 위 [설치](#설치) 참고).
- 파일당 **32MB 한도** — 초과하면 업로드 전에 에러로 알려준다. `--bitrate` 를 낮추거나
  세그먼트(`seg_NN.mp3`) 단위로 나눠 올리면 된다.

## 산출물 (`build/`)
```
build/
├── slides/<과>/slide_NN.png  # 렌더된 슬라이드 (과별 폴더, PDF 바뀌면 자동 재렌더)
├── audio/seg_NN.mp3          # 슬라이드별 오디오 (쉼=실제 무음)
├── audio/full_<engine>.mp3   # 전체 나레이션 합본
├── script.srt                # 자막(오디오 태그 제거된 clean text)
├── preview.mp4 / final.mp4   # 슬라이드 1:1 전환 영상
└── parts/part_NN.mp4         # 세그먼트별 영상 조각
```

## 문서 (`docs/`)
```
docs/
├── SCRIPT_FORMAT.md      # 대본 포맷 규격 (공용)
├── AUTHORING_GUIDE.md    # 작성 가이드 (공용)
├── 1-1/                  # 과별 폴더: PDF + 원본 대본 + v3 대본
│   ├── 1-1.pdf
│   ├── 1-1_나레이션대본.md
│   └── 1-1_나레이션대본.v3.md
└── 6-5/
    ├── 6-5.pdf
    ├── 6-5_나레이션대본.md
    └── 6-5_나레이션대본.v3.md
```
- [`docs/SCRIPT_FORMAT.md`](docs/SCRIPT_FORMAT.md) — 대본 포맷 규격
- [`docs/AUTHORING_GUIDE.md`](docs/AUTHORING_GUIDE.md) — 작성 가이드
- [`CLAUDE.md`](CLAUDE.md) — 에이전트/개발 안내

## 테스트
```bash
uv run pytest -q
```
