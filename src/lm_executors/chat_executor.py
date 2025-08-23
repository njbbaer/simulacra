import copy
import os
from typing import Any, Dict, List

import jinja2
import yaml

from ..api_client import OpenRouterAPIClient
from ..chat_completion import ChatCompletion


class ChatExecutor:
    TEMPLATE_PATH = "src/lm_executors/chat_executor_template.j2"

    def __init__(self, context) -> None:
        self.context = context

    async def execute(self, params: Dict[str, Any] | None = None) -> ChatCompletion:
        client = OpenRouterAPIClient()

        merged_params = {**self.context.api_params}
        if params:
            merged_params.update(params)

        completion = await client.request_completion(
            messages=self._build_messages(),
            parameters=merged_params,
        )

        self.context.increment_cost(completion.cost)
        return completion

    def _build_messages(self) -> List[Dict[str, Any]]:
        resolved_vars = self._resolve_vars()
        resolved_vars["messages"] = self.context.conversation_messages
        with open(self.TEMPLATE_PATH) as file:
            template = jinja2.Template(
                file.read(), trim_blocks=True, lstrip_blocks=True
            )
        rendered_str = template.render(resolved_vars)
        return yaml.safe_load(rendered_str)

    def _resolve_vars(self) -> Dict[str, Any]:
        """
        Resolves nested Jinja templates within the context variables.
        It iteratively renders templates using the state from the previous pass
        until no more changes occur, handling interdependencies.
        """
        env = jinja2.Environment(trim_blocks=True, lstrip_blocks=True, autoescape=False)
        resolved_vars = self._template_vars()
        max_passes = 10  # Safety limit

        # Use a container to hold the current state so nested functions can reference it
        context_container = [resolved_vars]

        for _ in range(max_passes):
            previous_vars_state = copy.deepcopy(resolved_vars)
            context_container[0] = resolved_vars

            def load_file(filepath: str) -> str:
                full_path = os.path.abspath(os.path.join(self.context.dir, filepath))
                with open(full_path) as f:
                    content = f.read()
                    template = env.from_string(content)
                    return template.render(**context_container[0])

            env.globals["load"] = load_file

            def resolve_recursive_pass(obj: Any) -> Any:
                if isinstance(obj, dict):
                    return {k: resolve_recursive_pass(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [resolve_recursive_pass(i) for i in obj]
                elif isinstance(obj, str):
                    if "{{" in obj and "}}" in obj:
                        template = env.from_string(obj)
                        return template.render(**context_container[0])
                    else:
                        return obj
                return obj

            resolved_vars = resolve_recursive_pass(context_container[0])

            if resolved_vars == previous_vars_state:
                return resolved_vars

        raise RuntimeError("Variable resolution did not converge")

    def _template_vars(self) -> Dict[str, Any]:
        return {
            **copy.deepcopy(self.context.vars),
            "facts": self.context.conversation_facts,
            "model": self.context.model,
        }
