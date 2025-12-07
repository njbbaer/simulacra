import copy
import os
from typing import Any

import jinja2


class TemplateResolver:
    def __init__(self, base_dir: str) -> None:
        self._base_dir = base_dir
        self._env = jinja2.Environment(
            trim_blocks=True, lstrip_blocks=True, autoescape=False
        )

    def resolve(
        self, data: dict[str, Any], extra_vars: dict[str, Any]
    ) -> dict[str, Any]:
        """Resolve all Jinja templates in data using iterative passes."""
        resolved = {**copy.deepcopy(data), **extra_vars}
        context = [resolved]  # Mutable wrapper for closure access

        for _ in range(10):
            previous = copy.deepcopy(resolved)
            context[0] = resolved
            self._env.globals["load"] = self._make_loader(context)
            resolved = self._resolve_recursive(resolved, context)
            if resolved == previous:
                return resolved

        raise RuntimeError("Template resolution did not converge")

    def _resolve_recursive(self, obj: Any, context: list[dict]) -> Any:
        if isinstance(obj, dict):
            return {k: self._resolve_recursive(v, context) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._resolve_recursive(i, context) for i in obj]
        if isinstance(obj, str) and "{{" in obj and "}}" in obj:
            template = self._env.from_string(obj)
            return template.render(**context[0])
        return obj

    def _make_loader(self, context: list[dict]):
        def load(filepath: str) -> str:
            full_path = os.path.abspath(os.path.join(self._base_dir, filepath))
            with open(full_path) as f:
                content = f.read()
            template = self._env.from_string(content)
            return template.render(**context[0])

        return load
