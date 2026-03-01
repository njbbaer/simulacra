from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.api_client import fetch_completion


def _mock_response(json_data, status_code=200):
    return httpx.Response(
        status_code,
        json=json_data,
        request=httpx.Request("POST", "http://test"),
    )


def _patch_httpx(response):
    mock_client = AsyncMock()
    mock_client.post.return_value = response
    return patch(
        "src.api_client.httpx.AsyncClient",
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_client),
            __aexit__=AsyncMock(return_value=False),
        ),
    )


@pytest.mark.asyncio
async def test_returns_response_data():
    data = {"choices": [{"message": {"content": "hi"}}], "usage": {}}
    with _patch_httpx(_mock_response(data)):
        result = await fetch_completion({"messages": []})
    assert result == data


@pytest.mark.asyncio
async def test_raises_on_api_error():
    data = {"error": {"message": "invalid model", "code": 400}}
    with (
        _patch_httpx(_mock_response(data)),
        pytest.raises(RuntimeError, match="invalid model"),
    ):
        await fetch_completion({"messages": []})


@pytest.mark.asyncio
async def test_raises_on_http_error():
    with (
        _patch_httpx(_mock_response({}, status_code=500)),
        pytest.raises(httpx.HTTPStatusError),
    ):
        await fetch_completion({"messages": []})
