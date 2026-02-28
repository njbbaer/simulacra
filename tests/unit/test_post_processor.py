from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.post_processor import clean_document, post_process_response


@contextmanager
def _mock_llm(content: str):
    response = httpx.Response(
        200,
        json={"choices": [{"message": {"content": content}}]},
        request=httpx.Request("POST", "http://test"),
    )
    mock_post = AsyncMock(return_value=response)
    with patch("src.post_processor.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(
            return_value=AsyncMock(post=mock_post)
        )
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        yield


@pytest.mark.asyncio
async def test_clean_document_skips_without_prompt():
    result = await clean_document("raw text", None)
    assert result == "raw text"


@pytest.mark.asyncio
async def test_clean_document_calls_llm():
    with _mock_llm("cleaned"):
        result = await clean_document("messy text", "clean it")
    assert result == "cleaned"


@pytest.mark.asyncio
async def test_clean_document_raises_on_http_error():
    with patch("src.post_processor.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.post.side_effect = httpx.ConnectTimeout("")
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(ValueError, match="Post-processor: ConnectTimeout"):
            await clean_document("text", "clean it")


@pytest.mark.asyncio
async def test_post_process_response_skips_without_prompt():
    result = await post_process_response("<tag>x</tag>text", None)
    assert result == "<tag>x</tag>text"


@pytest.mark.asyncio
async def test_post_process_response_skips_when_no_plain_text():
    result = await post_process_response("<tag>x</tag>", "prompt")
    assert result == "<tag>x</tag>"


@pytest.mark.asyncio
async def test_post_process_response_splices_result():
    with _mock_llm("processed"):
        result = await post_process_response("<tag>x</tag>original", "fix it")
    assert result == "<tag>x</tag>\n\nprocessed"
