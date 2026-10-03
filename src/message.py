from typing import Any

from .response_transform import strip_tags


class Message:
    def __init__(
        self,
        role: str,
        content: str | None,
        image: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.role = role
        self.content = content
        self.image = image
        self.metadata = metadata or {}

    @property
    def display_text(self) -> str:
        return strip_tags(self.content or "")

    @property
    def generated(self) -> bool:
        """Whether this is a response or scene, which a retry can replace."""
        return self.role == "assistant" or bool(self.metadata.get("scene"))

    @property
    def attempts(self) -> list[Message]:
        """Every attempt at this message, oldest first, ending with this one."""
        replaced = self.metadata.get("replaced", [])
        earlier = [Message.from_dict(data) for data in replaced]
        metadata = {k: v for k, v in self.metadata.items() if k != "replaced"}
        return [*earlier, Message(self.role, self.content, self.image, metadata)]

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            **({"content": self.content} if self.content else {}),
            **({"image": self.image} if self.image else {}),
            **({"metadata": self.metadata} if self.metadata else {}),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Message:
        return cls(
            role=str(data["role"]),
            content=str(data["content"]) if data.get("content") else None,
            image=str(data["image"]) if data.get("image") else None,
            metadata=data.get("metadata"),
        )
