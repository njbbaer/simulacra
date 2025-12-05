from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScaffoldConfig:
    response_tag: str | None = None
    require_tags: set[str] = field(default_factory=set)
    delete_tags: set[str] = field(default_factory=set)
    rename_tags: dict[str, str] = field(default_factory=dict)
    output_tag: str | None = None
    replace_patterns: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScaffoldConfig":
        return cls(
            response_tag=data.get("response_tag"),
            require_tags=set(data.get("require_tags", [])),
            delete_tags=set(data.get("delete_tags", [])),
            rename_tags=data.get("rename_tags", {}),
            output_tag=data.get("output_tag"),
            replace_patterns=data.get("replace_patterns", {}),
        )
