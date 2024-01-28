import jinja2
import yaml

from ..resolve_vars import resolve_vars
from .executor import Executor


class ChatExecutor(Executor):
    TEMPLATE_PATH = "src/executors/chat_executor_template.yml"

    async def execute(self):
        return await self._generate_chat_completion(
            self._build_chat_messages(),
            {
                "model": "gpt-4-vision-preview",
                "max_tokens": 1000,
            },
        )

    def _build_chat_messages(self):
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
