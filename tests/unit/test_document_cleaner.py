from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.document_cleaner import clean_document


def _mock_llm(content: str):
    response = {"choices": [{"message": {"content": content}}]}
    return patch(
        "src.document_cleaner.fetch_completion",
        new_callable=AsyncMock,
        return_value=response,
    )


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
async def test_clean_document_strips_content_tags():
    with _mock_llm("<content>cleaned</content>"):
        result = await clean_document("messy text", "clean it")
    assert result == "cleaned"


@pytest.mark.asyncio
async def test_clean_document_raises_on_http_error():
    with (
        patch(
            "src.document_cleaner.fetch_completion",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectTimeout(""),
        ),
        pytest.raises(ValueError, match="Document cleanup: ConnectTimeout"),
    ):
        await clean_document("text", "clean it")
