import jinja2
import yaml

from ..api_client import OpenRouterAPIClient
from ..resolve_vars import resolve_vars


class ChatExecutor:
    TEMPLATE_PATH = "src/lm_executors/chat_executor_template.j2"

    def __init__(self, context):
        self.context = context

    async def execute(self):
        client = OpenRouterAPIClient()

        params = {"max_tokens": 1024}
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
        vars = resolve_vars(
            {
                **self.context.vars,
                **self._extra_template_vars(),
            },
            self.context.dir,
        )
        vars["messages"] = self.context.conversation_messages
        with open(self.TEMPLATE_PATH) as file:
            template = jinja2.Template(
                file.read(), trim_blocks=True, lstrip_blocks=True
            )
        rendered_str = template.render(vars)
        return yaml.safe_load(rendered_str)

    def _extra_template_vars(self):
        return {
            "facts": self.context.conversation_facts,
            "model": self.context.model,
        }
