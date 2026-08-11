import pytest

from src.response_transform import Pattern, strip_tags, transform_response


def test_raises_when_required_tag_missing():
    with pytest.raises(ValueError, match="Missing required tags: response"):
        transform_response("no tags here", required_tags={"response"})


def test_raises_when_unexpected_tag_present():
    content = "<draft>leaked</draft>\n<response>ok</response>"
    with pytest.raises(ValueError, match="Unexpected tags: draft"):
        transform_response(content, required_tags={"response"})


def test_accepts_content_with_exactly_the_required_tags():
    content = "<thinking>hm</thinking>\n<response>ok</response>\nspoken"
    result = transform_response(content, required_tags={"thinking", "response"})
    assert result == content


def test_display_returns_content_outside_tags():
    content = "<thinking>ignore</thinking>show this<response>also ignore</response>"
    assert strip_tags(content) == "show this"


def test_apply_patterns():
    pattern = Pattern(pattern=r"foo\s+bar", replacement="baz")
    result = transform_response("before foo   bar after", patterns=[pattern])
    assert result == "before baz after"


def test_strip_tags_with_no_tags():
    assert strip_tags("plain text") == "plain text"
