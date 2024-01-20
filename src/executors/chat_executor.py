import os

import jinja2
import yaml

from .executor import Executor


class ChatExecutor(Executor):
    async def execute(self):
        return await self._generate_chat_completion(
            self._build_chat_messages(),
            {
                "model": "gpt-4-vision-preview",
                "max_tokens": 1000,
            },
        )

    def _load_chat_template(self):
        with open("src/executors/chat_template.yml") as file:
            return jinja2.Template(file.read(), trim_blocks=True, lstrip_blocks=True)

    def _build_chat_messages(self):
        template = self._load_chat_template()
        dereferenced_vars = self._dereference_vars(self.context.vars)
        rendered_vars = self._render_vars(
            {
                **dereferenced_vars,
                "messages": self.context.current_messages,
                "facts": self.context.current_conversation_facts,
            }
        )
        rendered_str = template.render(rendered_vars)
        return yaml.safe_load(rendered_str)

    def _dereference_vars(self, vars):
        dereferenced_vars = vars.copy()
        for key, value in vars.items():
            if isinstance(value, str) and value.startswith("file:"):
                file_path = value.split("file:", 1)[1]
                full_path = os.path.join(self.context.parent_dir, file_path)
                with open(full_path) as file:
                    dereferenced_vars[key] = file.read()
        return dereferenced_vars

    def _render_vars(self, vars):
        MAX_ITERATIONS = 10

        for _ in range(MAX_ITERATIONS):
            rendered_vars = self._render_vars_recursive(vars)
            if rendered_vars == vars:
                break
            vars = rendered_vars
        else:
            raise RuntimeError(
                "Too many iterations resolving vars. Circular reference?"
            )
        return rendered_vars

    def _render_vars_recursive(self, vars, obj=None):
        if obj is None:
            obj = vars

        if isinstance(obj, dict):
            return {
                key: self._render_vars_recursive(vars, value)
                for key, value in obj.items()
            }
        elif isinstance(obj, list):
            return [self._render_vars_recursive(vars, item) for item in obj]
        elif isinstance(obj, str):
            return jinja2.Template(obj, trim_blocks=True, lstrip_blocks=True).render(
                vars
            )
        else:
            return obj
