from typing import Any

from ruamel.yaml.scalarstring import LiteralScalarString


class Message:
    def __init__(
        self,
        role: str,
        content: str,
        image: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.role = role
        self.content = content
        self.image = image
        self.metadata = metadata

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        return cls(
            role=str(data["role"]),
            content=str(data["content"]),
            image=str(data["image"]) if data.get("image") else None,
            metadata=data.get("metadata"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": LiteralScalarString(self.content),
            **({"image": self.image} if self.image else {}),
            **({"metadata": self.metadata} if self.metadata else {}),
        }
