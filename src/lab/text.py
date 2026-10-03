import re
from typing import Any

from ..response_transform import strip_tags


def sections(content: str) -> dict[str, str]:
    """Return a response's thoughts, playwright's note, and spoken line."""

    def block(tag: str) -> str:
        match = re.search(rf"<{tag}>(.*?)</{tag}>", content, re.DOTALL)
        return match.group(1).strip() if match else ""

    return {
        "thoughts": block("character"),
        "note": block("playwright"),
        "spoken": strip_tags(content),
    }


def segments(spoken: str) -> list[dict[str, Any]]:
    """Split a spoken line into stage directions, paragraph breaks, and sentences.

    Sentences are numbered from 1 in `n`, skipping stage directions, which is
    how his sentence marks number them."""
    out: list[dict[str, Any]] = []
    for part in re.split(r"(\([^)]*\))", spoken):
        if not part.strip():
            if "\n\n" in part:
                out.append({"kind": "break"})
            continue
        if part.startswith("("):
            out.append({"kind": "stage", "text": part})
            continue
        for chunk in re.split(r"(\n\s*\n)", part):
            if not chunk.strip():
                if "\n" in chunk:
                    out.append({"kind": "break"})
                continue
            for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z\"'])", chunk.strip()):
                out.append({"kind": "sentence", "text": sentence.strip()})
    n = 0
    for segment in out:
        if segment["kind"] == "sentence":
            n += 1
            segment["n"] = n
    return out


def sentences(spoken: str) -> list[str]:
    """Return the spoken sentences in order, so sentence n is at index n - 1."""
    return [s["text"] for s in segments(spoken) if s["kind"] == "sentence"]


def speech(spoken: str) -> str:
    """Return the spoken line without its stage directions, on one line."""
    return re.sub(r"\s+", " ", re.sub(r"\([^)]*\)", " ", spoken)).strip()
