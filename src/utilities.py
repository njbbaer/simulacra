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
