# v3 대본 작성 가이드 (AUTHORING_GUIDE)

이 문서는 **Phase A**의 운영 매뉴얼입니다. 대상 독자는 **Claude Code**(에이전트)입니다.
코드는 LLM 을 호출하지 않습니다 — 대본을 작성하는 "에이전트"가 바로 이 가이드를 따르는 Claude Code 입니다.

## 입력
- 렌더된 슬라이드 이미지: `build/slides/<과>/slide_NN.png`
  (먼저 `python -m slide_narrator.prep --pdf docs/<과>/<과>.pdf` 실행)
- 원본 대본: `docs/<과>/<name>_나레이션대본.md` (과별 자료는 `docs/<과>/` 폴더에 모여 있다.
  예: `docs/1-1/`, `docs/6-5/`). **원본 포맷은 문서마다 다르다**:
  - 슬라이드 헤더: `**[n]**` (connect-ppt 계열) 또는 맨몸 `[n]` (예: 6-5).
    어느 쪽이든 **출력(v3 대본)은 항상 `**[n]**`** 로 통일한다.
  - 쉼 표기: `(N초동안 쉼,공백)` (legacy) 또는 `-N초-` / `-N초/` (예: 6-5). 변환 방법은 §5.
  - 음악 연출 메모: `배경음악 1 (7초) ~~~ '경쾌하게'`, `앤딩 음악 2 (8초) ~~~` 같은 줄이
    본문에 섞여 있을 수 있다 — **낭독하지 않는다.** 대신 해당 세그먼트 **끝**(인트로 음악이면 시작)에
    `(효과음 N초)` 마커로 변환한다(N = 메모의 초). 음악·효과음은 **오디오 태그로 표현할 수 없고**
    (음성 외 태그 금지, 부록 지침), Phase B 가 음원을 N초에 맞춰 삽입한다:
    **영상 맨 처음의 오프닝 음악**(첫 슬라이드에서 나레이션보다 앞에 둔 마커)은 `--opening`
    음원(기본 `assets/opening.mp3`), 나머지(전환/앤딩)는 `--jingle` 음원(기본 `assets/jingle.mp3`).
    음원은 `uv run -m slide_narrator.sfx`(징글) / `uv run -m slide_narrator.sfx --preset opening`
    (오프닝)으로 한 번씩 생성해 둔다.
  - 세그먼트 사이에 슬라이드 원문(어휘 목록·문제 지문 등)이 붙어 있을 수 있다 —
    슬라이드 내용 대조용 참고 자료이지 나레이션이 아니다.

## 출력
- v3 대본: `docs/<과>/<name>_나레이션대본.v3.md` ([`SCRIPT_FORMAT.md`](SCRIPT_FORMAT.md) 규격,
  원본 대본과 같은 과 폴더에 둔다)

## 절차

### 1. 규격 숙지
[`SCRIPT_FORMAT.md`](SCRIPT_FORMAT.md) 를 먼저 읽는다. 특히 오디오 태그 어휘,
쉼 태그(`[short pause]`/`[long pause]`/`[pause]`),
속도 태그(`[slows down]`/`[deliberate]`) 사용법을 확인한다.
(eleven_v3 는 실제 무음도, 숫자 배속 설정도 지원하지 않으므로 쉼·속도 모두 태그로 표현된다.)

### 2. 슬라이드 + 원본 함께 읽기
슬라이드 `slide_NN.png` 를 **실제로 보고**(Read 도구가 PNG 를 이미지로 렌더),
대응하는 `**[n]**` 원본 나레이션을 읽는다. 슬라이드의 시각 정보(제목·불릿·정답 표시 등)를
근거로 자연스러운 말하기 대본을 만든다.

### 3. 구어체 자연화
- 문어체 → 구어체: 종결어미를 `-요/-어요/-예요` 중심으로. 예: "학습합니다" → "배워볼 거예요".
- 긴 문어체 문장은 **호흡 단위**로 나눈다(한 문장이 너무 길면 끊어 읽기 좋게).
- 자연스러운 연결어(자,/그럼/네,/자 그러면) 를 적절히 넣는다.
- **의미는 절대 바꾸지 않는다.** 특히 교육 자료의 **정답/어휘/예문은 원문 그대로** 유지한다.

### 4. 오디오 태그 배치
- [`SCRIPT_FORMAT.md`](SCRIPT_FORMAT.md) 의 권장 어휘를 **기본**으로 하되, 대화·슬라이드 맥락에
  맞는 유사 태그를 골라도 된다(아래 **부록: Audio Tag Enhancer 지침** 준수).
- 슬라이드 의도에 맞춰 sparse 하게: 도입=`[warm]`, 정답 공개=`[excited]`, 질문=`[curious]`, 정정=`[serious]`.
- 수식할 구절 바로 앞(또는 바로 뒤)에. 호흡 그룹당 감정 태그 1개.
- **속도(템포) 태그 — 기본 템포보다 느리게 유도한다.** 청자가 한국어 학습자라 v3 기본 낭독은
  빠른 편이므로, 느린 템포를 기본 방침으로 한다:
  - `[slows down]` : 느린 템포로 전환. **각 세그먼트(슬라이드) 첫머리에 1개** 둔다.
    슬라이드마다 v3 요청이 분리되어 앞 요청의 지시가 이어지지 않으므로 세그먼트마다 새로 준다.
  - `[deliberate]` : 또박또박 신중하게. 어휘 낭독·예문·정답 문장 등
    **학습자가 따라 읽는 구간** 바로 앞에 둔다.
  - 감정 태그와 겹치면 나란히 써도 된다. 예: `[slows down] [warm] 자, 이번 시간에는요…`
  - ⚠️ 속도 태그는 배속 옵션이 아니라 v3 가 문맥으로 해석하는 지시다(eleven_v3 는 숫자
    `speed` 설정 미문서화). 효과는 보이스에 따라 다르므로 elevenlabs 렌더로 실제 템포를
    확인하고 필요하면 배치를 조정한다.

### 5. 쉼 처리 — 기계적 치환이 아니라 맥락 기반 배치
- eleven_v3 는 실제 무음을 지원하지 않으므로 쉼은 **오디오 태그**로 표현한다:
  `[short pause]`(짧게), `[long pause]`(길게), `[pause]`(가벼운 호흡).
- **원본의 쉼 마커(`(N초동안 쉼,공백)`, `-N초-` 등)를 단순히 `[pause]` 로 치환하지 말 것.**
  대신 **대화 내용과 슬라이드를 함께 보고**, 그 지점에서 무엇을 하는지 판단해
  **맥락에 맞는 쉼 태그를 창의적으로** 배치한다.
  - 정답 공개 직전 긴장/뜸 → `[long pause]`
  - 예문·단어를 따라 읽을 시간 → 문맥상 필요한 만큼 `[short pause]` / `[long pause]`
  - 문장 사이 자연스러운 호흡 → `[short pause]` 또는 `[pause]`
- **세그먼트 시작·끝에는 쉼 태그를 기본으로 둔다**(슬라이드가 하드 컷으로 전환되므로 여유를 준다):
  - 시작: 속도 태그 뒤, 첫 문장 앞에 `[short pause]`. 예: `[slows down] [short pause] [warm] 자, …`
    (원본이 세그먼트 첫머리에 `-2초-` 같은 쉼 마커를 두는 관행을 살린 것.)
  - 끝: 마지막 문장 뒤에 `[short pause]`, 내용을 정리하고 넘어가는 자리면 `[long pause]`.
  - ⚠️ 맨 앞·맨 뒤의 쉼 태그는 v3 가 문맥으로 해석해 효과가 약하거나 무시될 수 있다.
    렌더 후 전환이 급하게 느껴지면 Phase B 에서 무음 패딩(코드)으로 보강하는 편이 확실하다.
- **원본 쉼 표기는 두 계열이 있다.** 둘 다 같은 원칙(맥락 기반 배치)으로 변환한다:
  - `(N초동안 쉼,공백)` — connect-ppt 계열 legacy 마커.
  - `-N초-` / `-N초/` — 6-5 계열. 쓰임새별 해석:
    - 줄 단독 `-1초-`, `-2초-` : 문장 사이 호흡/전환 → 맥락에 맞게 `[pause]`/`[short pause]`/`[long pause]`.
    - 단어 뒤 `고추 -5초-` : 학습자가 **따라 읽는 시간** → `[long pause]`.
      v3 쉼은 초 단위 길이가 보장되지 않으므로, 긴 대기(3~5초)가 의도라면
      §7 방식대로 해당 단어를 **한 번 더 반복**해 시간을 채우는 편이 낫다.
    - 목록 구분 `고추 -3초/ 딸기 -3초/` : 단어마다 따라 읽기 간격 → 각 단어 뒤 `[long pause]`.
- ⚠️ **`-N초-` 마커는 파서가 인식하지 못한다.** legacy `(N초동안 쉼,공백)` 과 달리 자동 변환
  fallback 이 없어서, v3 대본에 남기면 **TTS 가 "-5초-" 를 글자 그대로 읽는다.**
  Phase A 에서 전부 쉼 태그로 변환하고, 완성본에 `-N초` 패턴이 남지 않았는지 확인한다(§8).
- **창의성은 발휘하되 내용(정답·어휘·예문·의미)은 절대 바꾸지 않는다.** 쉼·태그·강조는
  전달 방식만 다듬는 것이며 내용 편집이 아니다.
- (참고) legacy `(N초동안 쉼,공백)` 마커를 그대로 두면 코드가 `1초→[short pause]`,
  `2초→[long pause]` 로 자동 변환하지만, 이는 **하위호환 fallback** 일 뿐 권장 방식이 아니다.
  가능하면 맥락에 맞는 쉼 태그를 직접 쓴다. **이 fallback 은 `-N초-` 계열에는 적용되지 않는다.**
- 세부 태그 부여 원칙은 아래 **부록: Audio Tag Enhancer 지침**을 따른다.

### 6. 1:1 매핑 유지
- `**[n]**` 헤더는 슬라이드 1장당 정확히 1개. **개수·순서를 PDF 페이지와 일치**시킨다.
- 슬라이드를 합치거나 나누지 않는다.

### 7. 길이 가이드
- **전체 영상 길이는 25분 이상**이어야 한다(**필수 요건**). 슬라이드 58장 기준 평균 **~26초/장**.
  대본이 짧으면 이 기준을 못 채우므로 각 슬라이드 나레이션을 **충분히 채운다.**
- 슬라이드 1장은 권장 **20~45초**. 표지·전환 슬라이드는 짧아도 되지만(**≥3초**), 내용 슬라이드는
  넉넉히 설명해 전체 합이 25분을 넘게 한다. **2초 미만**의 너무 짧은 슬라이드는 금지.
- **자연스럽게 늘리는 방법(의미·정답 불변, 무의미한 패딩 금지):**
  - 예문·정답을 **실제로 소리 내어 읽고**, 따라 읽을 시간을 쉼 태그(`[long pause]` 등)로 준 뒤 **한 번 더** 반복한다.
  - 슬라이드의 시각 정보(불릿, 보기 선택지 ①②③, 그림 등)를 **하나씩 짚어** 설명한다.
  - 문제 풀이에서 **왜 그 답인지**, 필요하면 **왜 오답이 틀렸는지**를 짧게 덧붙인다.
  - 도입/마무리에 앞뒤 내용을 **요약·연결**하는 한두 문장을 넣는다.
  - ⚠️ 단, **정답·어휘·예문은 원문 그대로**. 늘리는 건 설명·반복·쉼이지 **내용 변경이 아니다.**
- 한 세그먼트 텍스트가 매우 길면(약 3000자 접근) 문장을 나눠 자연스럽게. (코드가 자동 청킹하지만
  경계 프로소디를 위해 미리 문장 단위로 끊는 편이 낫다.)

### 8. 자가 점검 체크리스트
- [ ] `**[n]**` 헤더 개수 == `build/slides/<과>/slide_*.png` 개수
- [ ] 태그는 권장 어휘를 기본으로, 맥락에 맞게 사용(부록 지침 준수)
- [ ] 각 세그먼트 첫머리에 `[slows down]` 배치, 따라 읽기 구간 앞에 `[deliberate]` 배치(§4 속도 태그)
- [ ] 각 세그먼트 시작·끝에 쉼 태그 배치(§5 — 시작 `[short pause]`, 끝 `[short pause]`/`[long pause]`)
- [ ] 모든 대괄호가 짝이 맞음(열고 닫힘)
- [ ] 정답·예문 등 핵심 정보가 원문과 동일(창의성은 전달 방식에만)
- [ ] 쉼은 맥락에 맞는 태그(`[short pause]`/`[long pause]`/`[pause]`)로 배치(기계적 치환 아님)
- [ ] 원본 쉼 마커가 결과물에 남아 있지 않음 — 특히 `-N초-` 는 fallback 이 없어 글자 그대로 낭독된다.
      `grep -nE -- '-[0-9]+초' docs/<과>/<name>_나레이션대본.v3.md` 가 무결과인지 확인
- [ ] 음악 연출 메모(`배경음악 …`, `앤딩 음악 …`)가 나레이션 텍스트에 남지 않고
      `(효과음 N초)` 마커로 변환됨 — 마커는 **세그먼트 시작 또는 끝에만**(본문 중간 금지)
- [ ] **전체 길이 ≥ 25분** — Phase B 렌더 후 파이프라인 로그의 `[srt] … (총 mm:ss)`
      또는 `build/script.srt` 마지막 타임코드로 확인. 미달이면 §7 방법으로 대본을 보강한다.


---

## 부록: Audio Tag Enhancer 지침 (원문)

> 아래는 오디오 태그를 **맥락에 맞게 창의적으로** 부여하기 위한 원문 지침이다.
> §4(태그 배치)·§5(쉼 처리)를 수행할 때 이 원칙을 따른다. 단, 본 프로젝트에서는
> §3(구어체 자연화)에서 이미 구어체로 다듬은 텍스트 위에 태그를 얹으며,
> 그 이후로는 **원문(정답·어휘·예문·의미)을 바꾸지 않는다**는 뜻으로 해석한다.

# Instructions

## 1. Role and Goal

You are an AI assistant specializing in enhancing dialogue text for speech generation.

Your **PRIMARY GOAL** is to dynamically integrate **audio tags** (e.g., [laughing], [sighs]) into dialogue, making it more expressive and engaging for auditory experiences, while **STRICTLY** preserving the original text and meaning.

It is imperative that you follow these system instructions to the fullest.

## 2. Core Directives

Follow these directives meticulously to ensure high-quality output.

### Positive Imperatives (DO):

* DO integrate **audio tags** from the "Audio Tags" list (or similar contextually appropriate **audio tags**) to add expression, emotion, and realism to the dialogue. These tags MUST describe something auditory.
* DO ensure that all **audio tags** are contextually appropriate and genuinely enhance the emotion or subtext of the dialogue line they are associated with.
* DO strive for a diverse range of emotional expressions (e.g., energetic, relaxed, casual, surprised, thoughtful) across the dialogue, reflecting the nuances of human conversation.
* DO place **audio tags** strategically to maximize impact, typically immediately before the dialogue segment they modify or immediately after. (e.g., [annoyed] This is hard. or This is hard. [sighs]).
* DO ensure **audio tags** contribute to the enjoyment and engagement of spoken dialogue.

### Negative Imperatives (DO NOT):

* DO NOT alter, add, or remove any words from the original dialogue text itself. Your role is to *prepend* **audio tags**, not to *edit* the speech. **This also applies to any narrative text provided; you must *never* place original text inside brackets or modify it in any way.**
* DO NOT create **audio tags** from existing narrative descriptions. **Audio tags** are *new additions* for expression, not reformatting of the original text. (e.g., if the text says "He laughed loudly," do not change it to "[laughing loudly] He laughed." Instead, add a tag if appropriate, e.g., "He laughed loudly [chuckles].")
* DO NOT use tags such as [standing], [grinning], [pacing], [music].
* DO NOT use tags for anything other than the voice such as music or sound effects.
* DO NOT invent new dialogue lines.
* DO NOT select **audio tags** that contradict or alter the original meaning or intent of the dialogue.
* DO NOT introduce or imply any sensitive topics, including but not limited to: politics, religion, child exploitation, profanity, hate speech, or other NSFW content.

## 3. Workflow

1. **Analyze Dialogue**: Carefully read and understand the mood, context, and emotional tone of **EACH** line of dialogue provided in the input.
2. **Select Tag(s)**: Based on your analysis, choose one or more suitable **audio tags**. Ensure they are relevant to the dialogue's specific emotions and dynamics.
3. **Integrate Tag(s)**: Place the selected **audio tag(s)** in square brackets strategically before or after the relevant dialogue segment, or at a natural pause if it enhances clarity.
4. **Add Emphasis:** You cannot change the text at all, but you can add emphasis by making some words capital, adding a question mark or adding an exclamation mark where it makes sense, or adding ellipses as well too.
5. **Verify Appropriateness**: Review the enhanced dialogue to confirm:
    * The **audio tag** fits naturally.
    * It enhances meaning without altering it.
    * It adheres to all Core Directives.

## 4. Output Format

* Present ONLY the enhanced dialogue text in a conversational format.
* **Audio tags** **MUST** be enclosed in square brackets (e.g., [laughing]).
* The output should maintain the narrative flow of the original dialogue.

## 5. Audio Tags (Non-Exhaustive)

Use these as a guide. You can infer similar, contextually appropriate **audio tags**.

**Directions:**
* [happy]
* [sad]
* [excited]
* [angry]
* [whisper]
* [annoyed]
* [appalled]
* [thoughtful]
* [surprised]
* *(and similar emotional/delivery directions)*

**Non-verbal:**
* [laughing]
* [chuckles]
* [sighs]
* [clears throat]
* [short pause]
* [long pause]
* [exhales sharply]
* [inhales deeply]
* *(and similar non-verbal sounds)*

## 6. Examples of Enhancement

**Input**:
"Are you serious? I can't believe you did that!"

**Enhanced Output**:
"[appalled] Are you serious? [sighs] I can't believe you did that!"

---

**Input**:
"That's amazing, I didn't know you could sing!"

**Enhanced Output**:
"[laughing] That's amazing, [singing] I didn't know you could sing!"

---

**Input**:
"I guess you're right. It's just... difficult."

**Enhanced Output**:
"I guess you're right. [sighs] It's just... [muttering] difficult."

# Instructions Summary

1. Add audio tags from the audio tags list. These must describe something auditory but only for the voice.
2. Enhance emphasis without altering meaning or text.
3. Reply ONLY with the enhanced text.
