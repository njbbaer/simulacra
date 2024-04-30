import jinja2
import yaml

from ..api_client import ApiClient
from ..chat_completion import ChatCompletion


class TitleExecutor:
    TEMPLATE_PATH = "src/lm_executors/title_executor_template.yml"
    MODEL = "anthropic/claude-3-sonnet:beta"

    def __init__(self, context):
        self.context = context

    async def execute(self):
        client = ApiClient("openrouter")
        completion = await ChatCompletion.generate(
            client, self._build_messages(), {"model": self.MODEL}
        )
        return completion

    def _build_messages(self):
        vars = self.context.vars
        vars["messages"] = self.context.conversation_messages
        with open(self.TEMPLATE_PATH) as file:
            template = jinja2.Template(
                file.read(), trim_blocks=True, lstrip_blocks=True
            )
        rendered_str = template.render(vars)
        return yaml.safe_load(rendered_str)
