import os

import jinja2


def resolve_vars(vars, base_path):
    MAX_ITERATIONS = 10

    for _ in range(MAX_ITERATIONS):
        resolved_vars = _resolve_vars_recursive(vars, base_path, vars)
        if resolved_vars == vars:
            return resolved_vars
        vars = resolved_vars

    raise RuntimeError("Too many iterations resolving vars. Circular reference?")


def _resolve_vars_recursive(obj, base_path, context):
    if isinstance(obj, dict):
        return {
            key: _resolve_vars_recursive(value, base_path, context)
            for key, value in obj.items()
        }
    elif isinstance(obj, list):
        return [_resolve_vars_recursive(item, base_path, context) for item in obj]
    elif isinstance(obj, str):
        if obj.startswith("file:"):
            file_path = obj.split("file:", 1)[1]
            full_path = os.path.join(base_path, file_path)
            with open(full_path) as file:
                return file.read()
        return jinja2.Template(obj, trim_blocks=True, lstrip_blocks=True).render(
            context
        )
    else:
        return obj
