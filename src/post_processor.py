import os
import re

import httpx

from .response_transform import strip_tags


async def clean_document(text: str, prompt: str | None) -> str:
    """Clean extracted document text via LLM before adding to context."""
    if not prompt:
        return text
    return await _quick_completion(text, prompt, request_timeout=60)


async def post_process_response(
    tagged_content: str,
    prompt: str | None,
) -> str:
    """Post-process display content via LLM, splicing result back with tags."""
    if not prompt:
        return tagged_content

    plain_text = strip_tags(tagged_content)
    if not plain_text:
        return tagged_content

    result = await _quick_completion(plain_text, prompt)
    return _splice_display(tagged_content, result)


async def _quick_completion(
    user_content: str, system_prompt: str, request_timeout: float = 10
) -> str:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    try:
        async with httpx.AsyncClient(timeout=request_timeout) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "openai/gpt-oss-120b",
                    "provider": {"sort": "latency"},
                    "temperature": 0.0,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": f"<content>{user_content}</content>",
                        },
                    ],
                },
            )
            response.raise_for_status()
    except httpx.HTTPError as e:
        msg = str(e) or type(e).__name__
        raise ValueError(f"Post-processor: {msg}") from e
    content = response.json()["choices"][0]["message"]["content"]
    return _strip_content_tags(content)


def _strip_content_tags(text: str) -> str:
    return re.sub(
        r"^<content>(.*)</content>$", r"\1", text.strip(), flags=re.DOTALL
    ).strip()


def _splice_display(tagged_content: str, new_content: str) -> str:
    """Replace content after the last closing tag with new content."""
    match = list(re.finditer(r"</[^>]+>", tagged_content))
    if not match:
        return new_content

    last_tag_end = match[-1].end()
    return tagged_content[:last_tag_end] + "\n\n" + new_content.strip()
