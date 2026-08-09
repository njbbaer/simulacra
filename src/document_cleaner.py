import re

import httpx

from .api_client import fetch_completion


async def clean_document(text: str, prompt: str | None) -> str:
    """Clean extracted document text via LLM before adding to context."""
    if not prompt:
        return text

    body = {
        "model": "openai/gpt-oss-120b",
        "provider": {"sort": "throughput"},
        "temperature": 0.0,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"<content>{text}</content>"},
        ],
    }
    try:
        data = await fetch_completion(body, request_timeout=60)
    except (httpx.HTTPError, RuntimeError) as e:
        msg = str(e) or type(e).__name__
        raise ValueError(f"Document cleanup: {msg}") from e
    return _strip_content_tags(data["choices"][0]["message"]["content"])


def _strip_content_tags(text: str) -> str:
    return re.sub(
        r"^<content>(.*)</content>$", r"\1", text.strip(), flags=re.DOTALL
    ).strip()
