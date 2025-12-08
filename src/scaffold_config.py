from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScaffoldConfig:
    require_tags: set[str] = field(default_factory=set)
    delete_tags: set[str] = field(default_factory=set)
    rename_tags: dict[str, str] = field(default_factory=dict)
    replace_patterns: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScaffoldConfig":
        return cls(
            require_tags=set(data.get("require_tags", [])),
            delete_tags=set(data.get("delete_tags", [])),
            rename_tags=data.get("rename_tags", {}),
            replace_patterns=data.get("replace_patterns", {}),
        )
