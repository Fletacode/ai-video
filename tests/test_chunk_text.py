"""chunk_text: v3 문자수 한도 청킹(순수 함수, 네트워크 없음)."""

from slide_narrator.tts import V3_CHAR_LIMIT, chunk_text


def _no_split_tags(chunks):
    # 각 조각의 대괄호는 균형이 맞아야 한다(= 태그가 경계로 쪼개지지 않음)
    return all(c.count("[") == c.count("]") for c in chunks)


def test_short_text_unchanged():
    assert chunk_text("짧은 문장이에요.") == ["짧은 문장이에요."]


def test_empty_text():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_long_text_each_chunk_within_limit():
    text = ("가나다라마바사아자차. " * 500).strip()
    assert len(text) > V3_CHAR_LIMIT
    chunks = chunk_text(text)
    assert len(chunks) >= 2
    assert all(len(c) <= V3_CHAR_LIMIT for c in chunks)


def test_char_order_preserved():
    text = ("한국어 문장입니다. " * 400).strip()
    chunks = chunk_text(text)
    # 공백을 무시하면 문자 순서가 그대로 보존되어야 한다
    assert "".join(chunks).replace(" ", "") == text.replace(" ", "")


def test_prefers_sentence_boundaries():
    # 각 20자 남짓 문장 여러 개, 작은 한도 → 문장 끝(.)에서 끊겨야 한다
    text = " ".join(["이것은 하나의 짧은 예시 문장입니다." for _ in range(20)])
    chunks = chunk_text(text, limit=60)
    assert len(chunks) >= 2
    # 마지막을 제외한 대부분의 조각이 문장부호로 끝난다
    assert all(c.rstrip().endswith(".") for c in chunks)


def test_tag_with_space_not_split():
    text = "[long pause] " + ("가" * 50)
    chunks = chunk_text(text, limit=20)
    assert _no_split_tags(chunks)
    # 공백 포함 태그가 한 조각 안에 통째로 남아야 한다
    assert any("[long pause]" in c for c in chunks)


def test_tags_never_split_in_long_text():
    unit = "[excited] 정말 재미있는 이야기예요. [pause] 계속 들어보세요. "
    text = (unit * 300).strip()
    chunks = chunk_text(text)
    assert len(chunks) >= 2
    assert _no_split_tags(chunks)
