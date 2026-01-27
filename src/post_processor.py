import os
import re

import httpx

from . import notifications


async def post_process_response(
    tagged_content: str,
    prompt: str | None,
) -> str:
    """Post-process display content via LLM, splicing result back with tags."""
    if not prompt:
        return tagged_content

    plain_text = _strip_all_tags(tagged_content)
    if not plain_text:
        return tagged_content

    try:
        result = await _quick_completion(plain_text, prompt)
        return _splice_display(tagged_content, result)
    except httpx.HTTPError:
        notifications.send("Post-processing failed")
        return tagged_content


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
                    {"role": "user", "content": f"<content>{user_content}</content>"},
                ],
            },
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return _strip_content_tags(content)


def _strip_all_tags(tagged_content: str) -> str:
    return re.sub(r"<[^>]+>.*?</[^>]+>", "", tagged_content, flags=re.DOTALL).strip()


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
