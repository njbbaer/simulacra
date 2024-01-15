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
            return jinja2.Template(file.read())

    def _build_chat_messages(self):
        template = self._load_chat_template()
        rendered_vars = self._render_vars(self.context.vars)
        rendered_str = template.render(
            **rendered_vars,
            messages=self.context.current_messages,
        )
        return yaml.safe_load(rendered_str)

    def _render_vars(self, vars):
        for _ in range(10):
            rendered_vars = self._render_vars_recursive(vars)
            if rendered_vars == vars:
                break
            vars = rendered_vars
        else:
            raise RuntimeError("Too many iterations")
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
            return jinja2.Template(obj).render(vars)
        else:
            raise ValueError(f"Unknown type: {type(obj)}")
