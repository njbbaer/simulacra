import re
from dataclasses import dataclass

from . import notifications


@dataclass
class Pattern:
    pattern: str
    replacement: str | None = None
    notify: str | None = None


def transform_response(
    content: str,
    patterns: list[Pattern] | None = None,
    required_tags: set[str] | None = None,
) -> str:
    content = content.strip()
    if patterns:
        content = _apply_patterns(content, patterns)
    if required_tags:
        _validate_required_tags(content, required_tags)
    return re.sub(r"\n{3,}", "\n\n", content).strip()


def strip_tags(content: str) -> str:
    return re.sub(r"<[^>]+>.*?</[^>]+>", "", content, flags=re.DOTALL).strip()


def extract_tag(content: str, tag: str) -> str:
    pattern = rf"<{re.escape(tag)}(?:\s[^>]*)?>(?P<content>.*?)</{re.escape(tag)}>"
    match = re.search(pattern, content, flags=re.DOTALL)
    if match is None:
        raise ValueError(f"Tag '{tag}' not found in response")
    return match.group("content").strip()


def _apply_patterns(content: str, patterns: list[Pattern]) -> str:
    for p in patterns:
        if re.search(p.pattern, content, flags=re.DOTALL):
            if p.notify:
                notifications.send(p.notify)
            if p.replacement is not None:
                content = re.sub(p.pattern, p.replacement, content, flags=re.DOTALL)
    return content


def _validate_required_tags(content: str, required_tags: set[str]) -> None:
    missing = [tag for tag in required_tags if not _has_tag(tag, content)]
    if missing:
        raise ValueError(f"Missing required tags: {', '.join(sorted(missing))}")


def _has_tag(tag: str, content: str) -> bool:
    return bool(
        re.search(rf"<{re.escape(tag)}\b", content)
        and re.search(rf"</{re.escape(tag)}>", content)
    )
