"""slide-narrator: 슬라이드 + 대본 → v3 TTS → 슬라이드 자동 전환 영상.

두 단계로 구성된다:
- Phase A (작성): Claude Code 가 슬라이드 이미지 + 기존 대본을 보고 v3 최적화 대본을 작성.
  (docs/SCRIPT_FORMAT.md, docs/AUTHORING_GUIDE.md 가이드를 따른다. 코드는 LLM 을 호출하지 않는다.)
- Phase B (렌더): 작성된 v3 대본을 파싱 → eleven_v3 TTS → 슬라이드 1:1 동기화 영상 + SRT.
"""
