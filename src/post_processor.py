import logging
import os
import re

import httpx


async def post_process_response(
    transformed_content: str,
    prompt: str | None,
) -> str:
    """Post-process display content via LLM, splicing result back with tags."""
    if not prompt:
        return transformed_content

    display = _strip_all_tags(transformed_content)
    if not display:
        return transformed_content

    try:
        processed = await _quick_completion(display, prompt)
        return _splice_display(transformed_content, processed)
    except httpx.HTTPError:
        logging.exception("Post-processing failed")
        return transformed_content


async def _quick_completion(user_content: str, system_prompt: str) -> str:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "openai/gpt-oss-120b",
                "provider": {"sort": "latency"},
                "temperature": 0.0,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
            },
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


def _strip_all_tags(content: str) -> str:
    return re.sub(r"<[^>]+>.*?</[^>]+>", "", content, flags=re.DOTALL).strip()


def _splice_display(transformed_content: str, new_display: str) -> str:
    """Replace content after the last closing tag with new_display."""
    match = list(re.finditer(r"</[^>]+>", transformed_content))
    if not match:
        return new_display

    last_tag_end = match[-1].end()
    return transformed_content[:last_tag_end] + "\n\n" + new_display.strip()
