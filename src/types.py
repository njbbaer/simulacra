from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Set


@dataclass
class ScaffoldConfig:
    require_tags: Set[str] = field(default_factory=set)
    delete_tags: Set[str] = field(default_factory=set)
    rename_tags: Dict[str, str] = field(default_factory=dict)
    output_tag: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScaffoldConfig":
        return cls(
            require_tags=set(data.get("require_tags", [])),
            delete_tags=set(data.get("delete_tags", [])),
            rename_tags=data.get("rename_tags", {}),
            output_tag=data.get("output_tag"),
        )
