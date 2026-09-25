import copy
import os
import re
from typing import Any

from jinja2 import TemplateSyntaxError
from jinja2.nativetypes import NativeEnvironment


class TemplateResolver:
    def __init__(self, base_dir: str, search_dirs: list[str] | None = None) -> None:
        self._base_dir = base_dir
        self._search_dirs = search_dirs or []
        self._dir_stack = [base_dir]
        self._env = NativeEnvironment(
            trim_blocks=True, lstrip_blocks=True, autoescape=False
        )
        self._env.globals["load_string"] = self._load_string
        self._env.globals["load_section"] = self._load_section
        self._variables: dict[str, Any] = {}

    def resolve(
        self, data: dict[str, Any], extra_vars: dict[str, Any]
    ) -> dict[str, Any]:
        """Resolve all Jinja templates in data using iterative passes."""
        self._variables = {**copy.deepcopy(data), **extra_vars}

        for _ in range(10):
            resolved = self._resolve_value(self._variables)
            if resolved == self._variables:
                return resolved
            self._variables = resolved

        raise RuntimeError("Template resolution did not converge")

    def _resolve_value(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: self._resolve_value(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._resolve_value(item) for item in obj]
        if isinstance(obj, str) and "{{" in obj and "}}" in obj:
            return self._env.from_string(obj).render(**self._variables)
        return obj

    def _load_string(self, filepath: str) -> str:
        full_path = self._full_path(filepath)
        with open(full_path) as f:
            content = f.read()
        self._dir_stack.append(os.path.dirname(full_path))
        try:
            rendered = self._env.from_string(content).render(**self._variables)
        except TemplateSyntaxError as e:
            raise TemplateSyntaxError(
                f"{e.message}\n({full_path}, line {e.lineno})", e.lineno
            ) from e
        finally:
            self._dir_stack.pop()
        # NativeEnvironment renders templates with no output as None
        return re.sub(r"\n{3,}", "\n\n", rendered or "")

    def _load_section(self, filepath: str | None) -> str:
        if not filepath:
            raise ValueError("load_section is missing a filepath")
        content = self._load_string(filepath)
        return content.strip() + "\n\n---" if content.strip() else ""

    def _full_path(self, filepath: str) -> str:
        path = os.path.join(self._current_dir, filepath)
        if not os.path.exists(path):
            for search_dir in self._search_dirs:
                candidate = os.path.join(search_dir, filepath)
                if os.path.exists(candidate):
                    return os.path.abspath(candidate)
        return os.path.abspath(path)

    @property
    def _current_dir(self) -> str:
        return self._dir_stack[-1]
