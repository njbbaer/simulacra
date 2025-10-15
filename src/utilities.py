import base64
import unicodedata
from io import BytesIO

import pdfplumber


def parse_pdf(content: bytes) -> str:
    binary_data = BytesIO(content)
    with pdfplumber.open(binary_data) as pdf:
        text = "\n".join(page.extract_text() for page in pdf.pages)
        normalized = unicodedata.normalize("NFKD", text)
        clean_text = "".join(c for c in normalized if c.isprintable() or c in "\n\r\t ")
        return clean_text


def load_base64(file_path: str) -> str:
    with open(file_path, "rb") as file:
        encoded_string = base64.b64encode(file.read()).decode("utf-8")
    return encoded_string
