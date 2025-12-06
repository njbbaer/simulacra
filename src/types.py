from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScaffoldConfig:
    display_tag: str | None = None
    require_tags: set[str] = field(default_factory=set)
    delete_tags: set[str] = field(default_factory=set)
    rename_tags: dict[str, str] = field(default_factory=dict)
    replace_patterns: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScaffoldConfig":
        return cls(
            display_tag=data.get("display_tag"),
            require_tags=set(data.get("require_tags", [])),
            delete_tags=set(data.get("delete_tags", [])),
            rename_tags=data.get("rename_tags", {}),
            replace_patterns=data.get("replace_patterns", {}),
        )
