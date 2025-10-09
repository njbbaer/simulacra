import unicodedata
from io import BytesIO

import httpx
import pdfplumber


def parse_pdf(content: bytes) -> str:
    binary_data = BytesIO(content)
    with pdfplumber.open(binary_data) as pdf:
        text = "\n".join(page.extract_text() for page in pdf.pages)
        normalized = unicodedata.normalize("NFKD", text)
        clean_text = "".join(c for c in normalized if c.isprintable() or c in "\n\r\t ")
        return clean_text


async def rehost_file_to_catbox(file_url: str) -> str:
    async with httpx.AsyncClient() as client:
        photo_response = await client.get(file_url)
        photo_response.raise_for_status()

        upload_response = await client.post(
            "https://litterbox.catbox.moe/resources/internals/api.php",
            data={"reqtype": "fileupload", "time": "72h"},
            files={"fileToUpload": ("", photo_response.content)},
        )
        upload_response.raise_for_status()

    return upload_response.text.strip()
