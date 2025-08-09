import re

from .types import ScaffoldConfig


class ResponseScaffold:
    def __init__(self, content: str, config: ScaffoldConfig) -> None:
        self.original_content = content.strip()
        self.config = config
        self._validate_content()

    def get_transformed_content(self) -> str:
        """Return the transformed response content by removing specified tags and renaming others."""

        content = self.original_content

        for tag in self.config.delete_tags:
            pattern = rf"<{re.escape(tag)}(?:\s[^>]*)?>.*?</{re.escape(tag)}>"
            content = re.sub(pattern, "", content, flags=re.DOTALL)

        for old_tag, new_tag in self.config.rename_tags.items():
            content = content.replace(f"<{old_tag}>", f"<{new_tag}>")
            content = content.replace(f"</{old_tag}>", f"</{new_tag}>")

        return re.sub(r"\n{3,}", "\n\n", content).strip()

    def extract(self, tag_name: str | None = None) -> str:
        target_tag = tag_name or self.config.output_tag

        if not target_tag:
            return re.sub(
                r"<[^>]*>.*?</[^>]*>", "", self.original_content, flags=re.DOTALL
            ).strip()

        pattern = rf"<{re.escape(target_tag)}(?:\s[^>]*)?>(?P<content>.*?)</{re.escape(target_tag)}>"
        match = re.search(pattern, self.original_content, flags=re.DOTALL)

        if not match:
            raise ValueError(
                f"Output tag '{target_tag}' not found in processed content"
            )

        return match.group("content").strip()

    def _validate_content(self) -> None:
        missing_tags = [
            tag
            for tag in self.config.require_tags
            if not re.search(rf"<{re.escape(tag)}\b", self.original_content)
        ]
        if missing_tags:
            raise ValueError(
                f"Missing required tags: {', '.join(sorted(missing_tags))}"
            )
