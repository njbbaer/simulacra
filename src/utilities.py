import base64
import os
import re
import unicodedata
from io import BytesIO

import pdfplumber
import trafilatura
from curl_cffi.requests import AsyncSession


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
