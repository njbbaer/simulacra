import copy
import os
from typing import Any

from jinja2.nativetypes import NativeEnvironment

from .yaml_config import yaml


class TemplateResolver:
    def __init__(self, base_dir: str) -> None:
        self._base_dir = base_dir
        self._env = NativeEnvironment(
            trim_blocks=True, lstrip_blocks=True, autoescape=False
        )
        self._env.globals["load"] = self._load_file
        self._variables: dict[str, Any] = {}

    def resolve(
        self, data: dict[str, Any], extra_vars: dict[str, Any]
    ) -> dict[str, Any]:
        """Resolve all Jinja templates in data using iterative passes."""
        self._variables = {**copy.deepcopy(data), **extra_vars}

        for _ in range(10):
            self._variables, changed = self._resolve_value(self._variables)
            if not changed:
                return self._variables

        raise RuntimeError("Template resolution did not converge")

    def _resolve_value(self, obj: Any) -> tuple[Any, bool]:
        if isinstance(obj, dict):
            changed = False
            result: dict[str, Any] = {}
            for k, v in obj.items():
                new_v, v_changed = self._resolve_value(v)
                result[k] = new_v
                changed = changed or v_changed
            return result, changed
        if isinstance(obj, list):
            changed = False
            items: list[Any] = []
            for item in obj:
                new_item, item_changed = self._resolve_value(item)
                items.append(new_item)
                changed = changed or item_changed
            return items, changed
        if isinstance(obj, str) and "{{" in obj and "}}" in obj:
            rendered = self._env.from_string(obj).render(**self._variables)
            return rendered, rendered != obj
        return obj, False

    def _load_file(self, filepath: str) -> str | Any:
        full_path = os.path.abspath(os.path.join(self._base_dir, filepath))
        with open(full_path) as f:
            if filepath.endswith((".yml", ".yaml")):
                return yaml.load(f)
            content = f.read()
        return self._env.from_string(content).render(**self._variables)
