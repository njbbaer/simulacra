import os

import jinja2


def resolve_vars(vars, base_path):
    vars = _dereference_vars(vars, base_path)
    return _render_vars(vars)


def _dereference_vars(vars, base_path):
    dereferenced_vars = vars.copy()
    for key, value in vars.items():
        if isinstance(value, str) and value.startswith("file:"):
            file_path = value.split("file:", 1)[1]
            full_path = os.path.join(base_path, file_path)
            with open(full_path) as file:
                dereferenced_vars[key] = file.read()
    return dereferenced_vars


def _render_vars(vars):
    MAX_ITERATIONS = 10

    for _ in range(MAX_ITERATIONS):
        rendered_vars = _render_vars_recursive(vars)
        if rendered_vars == vars:
            break
        vars = rendered_vars
    else:
        raise RuntimeError("Too many iterations resolving vars. Circular reference?")
    return rendered_vars


def _render_vars_recursive(vars, obj=None):
    if obj is None:
        obj = vars

    if isinstance(obj, dict):
        return {key: _render_vars_recursive(vars, value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [_render_vars_recursive(vars, item) for item in obj]
    elif isinstance(obj, str):
        return jinja2.Template(obj, trim_blocks=True, lstrip_blocks=True).render(vars)
    else:
        return obj
