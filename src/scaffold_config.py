from dataclasses import dataclass, field
from typing import Any


@dataclass
class Pattern:
    pattern: str
    replacement: str | None = None
    notify: str | None = None


@dataclass
class ScaffoldConfig:
    require_tags: set[str] = field(default_factory=set)
    delete_tags: set[str] = field(default_factory=set)
    rename_tags: dict[str, str] = field(default_factory=dict)
    patterns: list[Pattern] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScaffoldConfig":
        raw_patterns = data.get("patterns", [])
        patterns = [
            Pattern(
                pattern=p["pattern"],
                replacement=p.get("replacement"),
                notify=p.get("notify"),
            )
            for p in raw_patterns
        ]
        return cls(
            require_tags=set(data.get("require_tags", [])),
            delete_tags=set(data.get("delete_tags", [])),
            rename_tags=data.get("rename_tags", {}),
            patterns=patterns,
        )
