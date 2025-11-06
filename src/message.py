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
        self._role = role
        self._content = content
        self._image = image
        self._metadata = metadata

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        return cls(
            role=str(data["role"]),
            content=str(data["content"]),
            image=str(data["image"]) if data.get("image") else None,
            metadata=data.get("metadata"),
        )

    @property
    def role(self) -> str:
        return self._role

    @property
    def content(self) -> str:
        return self._content

    @property
    def image(self) -> str | None:
        return self._image

    @property
    def metadata(self) -> dict[str, Any] | None:
        return self._metadata

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self._role,
            "content": LiteralScalarString(self._content),
            **({"image": self._image} if self._image else {}),
            **({"metadata": self._metadata} if self._metadata else {}),
        }
