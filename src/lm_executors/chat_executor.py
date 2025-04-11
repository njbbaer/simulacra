import os

import jinja2
import yaml

from ..api_client import OpenRouterAPIClient


class ChatExecutor:
    TEMPLATE_PATH = "src/lm_executors/chat_executor_template.j2"

    def __init__(self, context):
        self.context = context

    async def execute(self):
        client = OpenRouterAPIClient()

        params = {"max_tokens": 8192}
        if self.context.model is not None:
            params["model"] = self.context.model

        completion = await client.request_completion(
            messages=self._build_messages(),
            parameters=params,
            pricing=self.context.pricing,
        )

        self.context.increment_cost(completion.cost)
        return completion

    def _build_messages(self):
        resolved_vars = self._resolve_vars()
        resolved_vars["messages"] = self.context.conversation_messages
        with open(self.TEMPLATE_PATH) as file:
            template = jinja2.Template(
                file.read(), trim_blocks=True, lstrip_blocks=True
            )
        rendered_str = template.render(resolved_vars)
        return yaml.safe_load(rendered_str)

    def _resolve_vars(self):
        template_vars = self._template_vars()
        env = jinja2.Environment(trim_blocks=True, lstrip_blocks=True, autoescape=False)

        def load_file(filepath):
            full_path = os.path.abspath(os.path.join(self.context.dir, filepath))
            with open(full_path) as f:
                content = f.read()
                template = env.from_string(content)
                return template.render(**template_vars)

        env.globals["load"] = load_file

        def resolve_recursive(obj):
            if isinstance(obj, dict):
                return {k: resolve_recursive(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [resolve_recursive(i) for i in obj]
            elif isinstance(obj, str):
                template = env.from_string(obj)
                return template.render(**template_vars)
            return obj

        return resolve_recursive(template_vars)

    def _template_vars(self):
        return {
            **self.context.vars,
            "facts": self.context.conversation_facts,
            "model": self.context.model,
        }
