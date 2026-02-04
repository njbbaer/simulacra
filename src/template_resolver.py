import copy
import os
import re
from typing import Any

from jinja2 import TemplateSyntaxError
from jinja2.nativetypes import NativeEnvironment

from .yaml_config import yaml


class TemplateResolver:
    def __init__(self, base_dir: str) -> None:
        self._base_dir = base_dir
        self._env = NativeEnvironment(
            trim_blocks=True, lstrip_blocks=True, autoescape=False
        )
        self._env.globals["load_string"] = self._load_string
        self._env.globals["load_yaml"] = self._load_yaml
        self._env.globals["load_section"] = self._load_section
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

    def _load_string(self, filepath: str) -> str:
        full_path = self._full_path(filepath)
        with open(full_path) as f:
            content = f.read()
        try:
            rendered = self._env.from_string(content).render(**self._variables)
        except TemplateSyntaxError as e:
            raise TemplateSyntaxError(
                f"{e.message}\n({full_path}, line {e.lineno})", e.lineno
            ) from e
        return re.sub(r"\n{3,}", "\n\n", rendered)

    def _load_yaml(self, filepath: str) -> Any:
        with open(self._full_path(filepath)) as f:
            return yaml.load(f)

    def _load_section(self, filepath: str | None) -> str:
        if not filepath:
            raise ValueError("load_section is missing a filepath")
        content = self._load_string(filepath)
        return content if content.strip() + "\n\n---" else ""

    def _full_path(self, filepath: str) -> str:
        return os.path.abspath(os.path.join(self._base_dir, filepath))
