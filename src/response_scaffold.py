import re

from . import notifications
from .scaffold_config import ScaffoldConfig


class ResponseScaffold:
    def __init__(self, content: str, config: ScaffoldConfig) -> None:
        self.original_content = content.strip()
        self.config = config
        self.transformed_content = self._transform()

    @property
    def display(self) -> str:
        return self._strip_all_tags(self.transformed_content)

    def extract(self, tag_name: str | None = None) -> str:
        if not tag_name:
            return self._strip_all_tags(self.transformed_content)

        content = self._extract_tag_content(tag_name, self.transformed_content)
        if content is None:
            raise ValueError(f"Tag '{tag_name}' not found in response")

        return content

    def _transform(self) -> str:
        content = self._apply_replace_patterns(self.original_content)
        self._validate_required_tags(content)

        for tag in self.config.delete_tags:
            content = self._remove_tag(tag, content)

        for old_tag, new_tag in self.config.rename_tags.items():
            content = self._rename_tag(old_tag, new_tag, content)

        return re.sub(r"\n{3,}", "\n\n", content).strip()

    def _apply_replace_patterns(self, content: str) -> str:
        for rp in self.config.replace_patterns:
            if rp.notify and re.search(rp.pattern, content, flags=re.DOTALL):
                notifications.send(rp.notify)
            content = re.sub(rp.pattern, rp.replacement, content, flags=re.DOTALL)
        return content

    def _validate_required_tags(self, content: str) -> None:
        missing_tags = [
            tag for tag in self.config.require_tags if not self._has_tag(tag, content)
        ]
        if missing_tags:
            tag_list = ", ".join(sorted(missing_tags))
            raise ValueError(f"Missing required tags: {tag_list}")

    @staticmethod
    def _has_tag(tag: str, content: str) -> bool:
        return bool(
            re.search(rf"<{re.escape(tag)}\b", content)
            and re.search(rf"</{re.escape(tag)}>", content)
        )

    @staticmethod
    def _remove_tag(tag: str, content: str) -> str:
        pattern = rf"<{re.escape(tag)}(?:\s[^>]*)?>.*?</{re.escape(tag)}>"
        return re.sub(pattern, "", content, flags=re.DOTALL)

    @staticmethod
    def _rename_tag(old_tag: str, new_tag: str, content: str) -> str:
        content = content.replace(f"<{old_tag}>", f"<{new_tag}>")
        return content.replace(f"</{old_tag}>", f"</{new_tag}>")

    @staticmethod
    def _extract_tag_content(tag: str, content: str) -> str | None:
        pattern = rf"<{re.escape(tag)}(?:\s[^>]*)?>(?P<content>.*?)</{re.escape(tag)}>"
        match = re.search(pattern, content, flags=re.DOTALL)
        return match.group("content").strip() if match else None

    @staticmethod
    def _strip_all_tags(content: str) -> str:
        return re.sub(r"<[^>]*>.*?</[^>]*>", "", content, flags=re.DOTALL).strip()
