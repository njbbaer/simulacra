import json
import re
from typing import Any

from ..agent_sdk_client import fetch_agent_sdk_completion, is_agent_sdk_model
from ..api_client import fetch_completion
from ..chat_completion import ChatCompletion
from ..response_transform import ResponseFormatError
from ..telemetry import Telemetry
from ..turn_stats import TurnStats
from .replay import Result, _hash


async def complete(
    messages: list[dict[str, Any]],
    model: str,
    effort: str | None = None,
    *,
    stage: str = "complete",
) -> Result:
    """Send messages to the model through the production clients.

    The result's prompts hash the system message under `stage`."""
    body: dict[str, Any] = {"messages": messages, "model": model}
    if effort:
        body["reasoning"] = {"effort": effort}
    sdk = is_agent_sdk_model(model)
    fetch = fetch_agent_sdk_completion if sdk else fetch_completion
    record = Telemetry().start(kind="request", stage=stage, model=model)
    completion = ChatCompletion(await fetch(body))
    row = record.ok(**completion.request_fields())
    system = next((m["content"] for m in messages if m["role"] == "system"), None)
    return Result(
        completion.content,
        completion.content,
        [],
        None,
        TurnStats(stage, row["duration_ms"], [row]),
        {stage: _hash(system)},
    )


def parse_tag(text: str, tag: str, *, as_json: bool = False) -> Any:
    """Return the first <tag> block's contents, or raise ResponseFormatError."""
    match = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.DOTALL)
    if not match:
        raise ResponseFormatError(f"No <{tag}> block")
    if not as_json:
        return match.group(1).strip()
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as err:
        raise ResponseFormatError(f"Bad JSON in <{tag}>: {err}") from err
