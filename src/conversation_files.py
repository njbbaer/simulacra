import os
import re
from collections import namedtuple

ConversationFile = namedtuple("ConversationFile", ["filename", "id", "name"])


class ConversationFiles:
    def __init__(self, conversations_dir: str, character_name: str):
        self._dir = conversations_dir
        self._character = character_name.lower()
        self._pattern = re.compile(rf"^{self._character}_(\d+)(?:_(.+))?\.yml$")

    def list(self) -> list[ConversationFile]:
        return [
            ConversationFile(f, int(m.group(1)), m.group(2))
            for f in os.listdir(self._dir)
            if (m := self._pattern.match(f))
        ]

    def find(self, identifier: str) -> ConversationFile:
        """Find by ID (if numeric) or name. Raises ValueError if not found."""
        if identifier.isdigit():
            conv = self._find_by_id(int(identifier))
            if not conv:
                raise ValueError(f"No conversation with ID '{identifier}'")
        else:
            conv = self._find_by_name(identifier)
            if not conv:
                raise ValueError(f"No conversation named '{identifier}'")
        return conv

    def _find_by_id(self, conv_id: int) -> ConversationFile | None:
        for conv in self.list():
            if conv.id == conv_id:
                return conv
        return None

    def _find_by_name(self, name: str) -> ConversationFile | None:
        name_lower = name.lower()
        matches = [c for c in self.list() if c.name and c.name.lower() == name_lower]
        if not matches:
            return None
        return max(matches, key=lambda c: c.id)

    def next_id(self) -> int:
        return max((conv.id for conv in self.list()), default=0) + 1

    def generate_filename(self, conv_id: int, name: str | None = None) -> str:
        if name:
            return f"{self._character}_{conv_id}_{self.sanitize_name(name)}.yml"
        return f"{self._character}_{conv_id}.yml"

    def sanitize_name(self, name: str) -> str:
        sanitized = re.sub(r"[^a-z0-9_]", "", name.lower().replace(" ", "_"))
        if not sanitized:
            raise ValueError("Name must contain alphanumeric characters")
        return sanitized

    def rename(self, old_filename: str, new_name: str) -> tuple[str, str]:
        """Rename a conversation file. Returns (new_filename, sanitized_name)."""
        conv = self.parse_filename(old_filename)
        if not conv:
            raise ValueError(f"Invalid filename: {old_filename}")
        sanitized = self.sanitize_name(new_name)
        new_filename = self.generate_filename(conv.id, new_name)
        os.rename(
            os.path.join(self._dir, old_filename),
            os.path.join(self._dir, new_filename),
        )
        return (new_filename, sanitized)

    def parse_filename(self, filename: str) -> ConversationFile | None:
        if m := self._pattern.match(filename):
            return ConversationFile(filename, int(m.group(1)), m.group(2))
        return None
