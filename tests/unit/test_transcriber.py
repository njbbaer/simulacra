import base64
from unittest.mock import AsyncMock, patch

import pytest

from src.transcriber import TRANSCRIPTION_MODEL, transcribe


def _mock_fetch(response):
    return patch(
        "src.transcriber.fetch_transcription",
        new_callable=AsyncMock,
        return_value=response,
    )


@pytest.mark.asyncio
async def test_sends_audio_and_returns_text_and_cost():
    response = {"text": " Hello there. ", "usage": {"cost": 0.0008}}
    with _mock_fetch(response) as fetch:
        text, cost = await transcribe(b"voice")
    body = fetch.call_args.args[0]
    assert body["model"] == TRANSCRIPTION_MODEL
    assert body["input_audio"] == {
        "data": base64.b64encode(b"voice").decode(),
        "format": "ogg",
    }
    assert (text, cost) == ("Hello there.", 0.0008)


@pytest.mark.asyncio
async def test_empty_transcript_raises():
    with _mock_fetch({"text": "  "}), pytest.raises(ValueError, match="No speech"):
        await transcribe(b"silence")
