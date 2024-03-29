import jinja2
import yaml

from ..api_client import ApiClient
from ..chat_completion import ChatCompletion
from ..resolve_vars import resolve_vars


class ChatExecutor:
    TEMPLATE_PATH = "src/executors/chat_executor_template.yml"

    def __init__(self, context):
        self.context = context

    async def execute(self):
        client = ApiClient(
            base_url=self.context.api_url,
            api_key=self.context.api_key,
            instruction_template=self.context.instruction_template,
        )

        params = {"max_tokens": 1000}
        if self.context.model is not None:
            params["model"] = self.context.model

        completion = await ChatCompletion.generate(
            client, self._build_messages(), params
        )

        self.context.increment_cost(completion.cost)
        return completion

    def _build_messages(self):
        vars = resolve_vars(
            {
                **self.context.vars,
                "facts": self.context.conversation_facts,
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
