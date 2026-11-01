import base64

from .api_client import fetch_transcription

TRANSCRIPTION_MODEL = "microsoft/mai-transcribe-2"


async def transcribe(audio: bytes, audio_format: str = "ogg") -> tuple[str, float]:
    """Return the audio's transcript and the cost of transcribing it."""
    data = await fetch_transcription(
        {
            "model": TRANSCRIPTION_MODEL,
            "input_audio": {
                "data": base64.b64encode(audio).decode(),
                "format": audio_format,
            },
        }
    )
    text = (data.get("text") or "").strip()
    if not text:
        raise ValueError("No speech found in the voice message")
    return text, (data.get("usage") or {}).get("cost") or 0.0
