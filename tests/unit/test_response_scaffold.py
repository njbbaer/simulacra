import pytest

from src.response_scaffold import ResponseScaffold
from src.types import ScaffoldConfig


def test_deletes_tags():
    config = ScaffoldConfig(delete_tags={"secret"})
    content = "before <secret>hidden</secret> after"
    scaffold = ResponseScaffold(content, config)
    assert scaffold.transformed_content == "before  after"


def test_renames_tags():
    config = ScaffoldConfig(rename_tags={"old": "new"})
    content = "<old>content</old>"
    scaffold = ResponseScaffold(content, config)
    assert scaffold.transformed_content == "<new>content</new>"


def test_raises_when_required_tag_missing():
    config = ScaffoldConfig(require_tags={"response"})
    with pytest.raises(ValueError, match="Missing required tags: response"):
        ResponseScaffold("no tags here", config)


def test_extracts_tag_content():
    content = "<outer><inner>value</inner></outer>"
    scaffold = ResponseScaffold(content, ScaffoldConfig())
    assert scaffold.extract("inner") == "value"


def test_returns_display_tag_content():
    config = ScaffoldConfig(display_tag="response")
    content = "<thinking>ignore</thinking><response>show this</response>"
    scaffold = ResponseScaffold(content, config)
    assert scaffold.display == "show this"
