from typing import Any

from .response_transform import strip_tags


class Message:
    def __init__(
        self,
        role: str,
        content: str | None,
        image: str | None = None,
        metadata: dict[str, Any] | None = None,
        replaced: list[Message] | None = None,
    ) -> None:
        self.role = role
        self.content = content
        self.image = image
        self.metadata = metadata or {}
        self.replaced = replaced or []

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
        latest = Message(self.role, self.content, self.image, self.metadata)
        return [*self.replaced, latest]

    def to_dict(self) -> dict[str, Any]:
        """Return the message as stored, with replaced attempts sharing its role."""
        data = self._fields()
        if self.replaced:
            data["replaced"] = [attempt._fields() for attempt in self.replaced]
        return {"role": self.role, **data}

    def _fields(self) -> dict[str, Any]:
        return {
            **({"content": self.content} if self.content else {}),
            **({"image": self.image} if self.image else {}),
            **({"metadata": self.metadata} if self.metadata else {}),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], role: str | None = None) -> Message:
        role = role or str(data["role"])
        return cls(
            role=role,
            content=str(data["content"]) if data.get("content") else None,
            image=str(data["image"]) if data.get("image") else None,
            metadata=data.get("metadata"),
            replaced=[cls.from_dict(item, role) for item in data.get("replaced", [])],
        )
