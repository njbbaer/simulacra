from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.utilities import (
    extract_url_content,
    make_base64_loader,
    merge_dicts,
    parse_pdf,
    parse_value,
)


class TestMergeDicts:
    def test_flat_merge(self):
        assert merge_dicts({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}

    def test_overwrites_non_dict_values(self):
        assert merge_dicts({"a": 1}, {"a": 2}) == {"a": 2}

    def test_deep_merges_nested_dicts(self):
        result = merge_dicts({"a": {"x": 1, "y": 2}}, {"a": {"y": 3, "z": 4}})
        assert result == {"a": {"x": 1, "y": 3, "z": 4}}

    def test_overwrites_dict_with_non_dict(self):
        assert merge_dicts({"a": {"x": 1}}, {"a": "flat"}) == {"a": "flat"}

    def test_does_not_mutate_originals(self):
        d1 = {"a": {"x": 1}}
        d2 = {"a": {"y": 2}}
        merge_dicts(d1, d2)
        assert d1 == {"a": {"x": 1}}
        assert d2 == {"a": {"y": 2}}


class TestParseValue:
    def test_true(self):
        assert parse_value("true") is True
        assert parse_value("True") is True

    def test_false(self):
        assert parse_value("false") is False
        assert parse_value("FALSE") is False

    def test_int(self):
        assert parse_value("42") == 42
        assert isinstance(parse_value("42"), int)

    def test_float(self):
        assert parse_value("3.14") == pytest.approx(3.14)
        assert isinstance(parse_value("3.14"), float)

    def test_string(self):
        assert parse_value("hello") == "hello"


class TestExtractUrlContent:
    @pytest.fixture()
    def _mock_fetch(self):
        response = MagicMock(text="<html>web text</html>")
        session = AsyncMock()
        session.__aenter__.return_value.get.return_value = response
        with (
            patch("src.utilities.AsyncSession", return_value=session),
            patch("src.utilities.trafilatura.extract", return_value="web text"),
        ):
            yield

    @pytest.mark.asyncio
    async def test_no_url_returns_original(self):
        assert await extract_url_content("just text") == ("just text", None)

    @pytest.mark.asyncio
    async def test_none_returns_none(self):
        assert await extract_url_content(None) == (None, None)

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_mock_fetch")
    async def test_extracts_content_and_strips_url(self):
        text, content = await extract_url_content("see https://example.com please")
        assert text == "see please"
        assert content == "web text"

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_mock_fetch")
    async def test_url_only_returns_none_text(self):
        text, content = await extract_url_content("https://example.com")
        assert text is None
        assert content == "web text"


class TestParsePdf:
    def test_extracts_and_normalizes_text(self):
        page = MagicMock(extract_text=MagicMock(return_value="of\ufb01ce"))
        pdf = MagicMock(pages=[page])
        ctx = MagicMock(
            __enter__=MagicMock(return_value=pdf),
            __exit__=MagicMock(return_value=False),
        )
        with patch("src.utilities.pdfplumber.open", return_value=ctx):
            result = parse_pdf(b"fake")
        assert result == "office"


class TestMakeBase64Loader:
    def test_loads_and_encodes_file(self, fs):
        fs.create_file("/data/image.png", contents=b"\x89PNG")
        loader = make_base64_loader("/data")
        assert loader("image.png") == "iVBORw=="
