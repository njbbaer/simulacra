import base64
import copy
import os
import re
import unicodedata
from io import BytesIO

import backoff
import pdfplumber
import trafilatura
from curl_cffi.requests import AsyncSession
from curl_cffi.requests.errors import RequestsError


@backoff.on_exception(backoff.expo, RequestsError, max_tries=3)
async def extract_url_content(text: str | None) -> tuple[str | None, str | None]:
    if not text:
        return text, None
    pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    match = re.search(pattern, text)
    if not match:
        return text, None
    url = match.group(0)

    async with AsyncSession(impersonate="chrome124") as client:
        response = await client.get(url, allow_redirects=True, timeout=30)
    response.raise_for_status()

    content = trafilatura.extract(response.text)
    if not content:
        raise ValueError("Failed to extract content from URL")
    stripped = text.replace(url, "").strip() or None
    return stripped, content


def parse_pdf(content: bytes) -> str:
    binary_data = BytesIO(content)
    with pdfplumber.open(binary_data) as pdf:
        text = "\n".join(page.extract_text() for page in pdf.pages)
        normalized = unicodedata.normalize("NFKD", text)
        return "".join(c for c in normalized if c.isprintable() or c in "\n\r\t ")


def make_base64_loader(base_dir: str):
    def load_base64(local_path: str) -> str:
        full_path = os.path.abspath(os.path.join(base_dir, local_path))
        with open(full_path, "rb") as file:
            return base64.b64encode(file.read()).decode("utf-8")

    return load_base64


def merge_dicts(dict1: dict, dict2: dict) -> dict:
    result = copy.deepcopy(dict1)
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


def parse_value(value: str) -> bool | int | float | str:
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value
