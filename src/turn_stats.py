import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

WINDOW_LABELS = {"five_hour": "5-hour", "seven_day": "Weekly"}


@dataclass
class TurnStats:
    """A turn's action, wall time, and the telemetry row of each of its requests."""

    action: str
    duration_ms: int = 0
    requests: list[dict[str, Any]] = field(default_factory=list)

    @property
    def cost(self) -> float:
        return sum(request["cost"] for request in self.requests)

    @property
    def plan_cost(self) -> float:
        return sum(request["plan_cost"] for request in self.requests)

    @property
    def plan_usage(self) -> dict[str, dict[str, Any]] | None:
        """Return the plan utilization reported by the latest request with one."""
        for request in reversed(self.requests):
            if request.get("plan_usage"):
                return request["plan_usage"]
        return None


def format_stats(
    turn: TurnStats | None,
    conversation_id: int,
    messages: int,
    cost: float,
    plan_cost: float,
    now: float | None = None,
) -> str:
    """Return the /stats message in Telegram Markdown."""
    sections = []
    if turn and turn.requests:
        sections.append(
            _join(
                [
                    f"*Turn* · {turn.action} · {_seconds(turn.duration_ms)}",
                    _cost(turn.cost, turn.plan_cost, 3),
                ]
            )
        )
        stages = dict.fromkeys(request["stage"] for request in turn.requests)
        sections += [_stage_section(turn, stage) for stage in stages]
    sections.append(
        f"*Conversation* · #{conversation_id} · {messages} messages · "
        + _cost(cost, plan_cost, 2)
    )
    if turn and turn.plan_usage:
        sections.append(_plan_section(turn.plan_usage, now or time.time()))
    return "\n\n".join(sections)


def _stage_section(turn: TurnStats, stage: str) -> str:
    """The stage's heading, then one line per request with what varies between them."""
    requests = sorted(
        (request for request in turn.requests if request["stage"] == stage),
        key=lambda request: (request["candidate"] or "", request["draft"] or 0),
    )
    provider = _shared(request["provider"] for request in requests)
    prompt = _shared(_prompt(request) for request in requests)
    title = "*" + stage.replace("_", "-").capitalize() + "*"
    model = requests[0]["model"].rsplit("/", 1)[-1]
    lines = [_join([title, model, provider, prompt])]
    for request in requests:
        attempts = request.get("attempts", 1)
        lines.append(
            _join(
                [
                    request["candidate"],
                    f"Draft {request['draft']}" if request["draft"] else None,
                    _seconds(request["duration_ms"]),
                    None if prompt else _prompt(request),
                    _completion(request),
                    f"{attempts} attempts" if attempts > 1 else None,
                    None if provider else request["provider"],
                    _cost(request["cost"], request["plan_cost"], 3),
                ]
            )
        )
    return "\n".join(lines)


def _plan_section(plan_usage: dict[str, dict[str, Any]], now: float) -> str:
    """The heading, then each window's utilization and time until it resets."""
    lines = ["*Plan*"]
    for name, window in plan_usage.items():
        label = WINDOW_LABELS.get(name, name)
        resets_at = window["resets_at"]
        if resets_at is not None and resets_at <= now:
            lines.append(_join([label, "reset since last request"]))
            continue
        lines.append(
            _join(
                [
                    label,
                    f"{window['utilization']:.0%}",
                    f"resets in {_duration(resets_at - now)}" if resets_at else None,
                ]
            )
        )
    return "\n".join(lines)


def _shared[T](values: Iterable[T]) -> T | None:
    """The one value every item has, or None if they differ."""
    distinct = set(values)
    return next(iter(distinct)) if len(distinct) == 1 else None


def _join(parts: Iterable[str | None]) -> str:
    return " · ".join(part for part in parts if part)


def _cost(cost: float, plan_cost: float, digits: int) -> str:
    """Return the money spent and the plan-covered value, omitting a zero plan."""
    return _join(
        [
            f"${cost:.{digits}f}" if cost or not plan_cost else None,
            f"plan ${plan_cost:.{digits}f}" if plan_cost else None,
        ]
    )


def _prompt(request: dict[str, Any]) -> str:
    text = f"{_tokens(request['prompt_tokens'])} prompt"
    if request["cached_tokens"]:
        text += f", {request['cached_tokens'] / request['prompt_tokens']:.0%} cached"
    return text


def _completion(request: dict[str, Any]) -> str:
    text = f"{_tokens(request['completion_tokens'])} tokens"
    if request["reasoning_tokens"]:
        text += f", {_tokens(request['reasoning_tokens'])} reasoning"
    return text


def _duration(seconds: float) -> str:
    days, minutes = divmod(int(seconds // 60), 24 * 60)
    hours, minutes = divmod(minutes, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _seconds(duration_ms: int) -> str:
    return f"{duration_ms / 1000:.1f}s"


def _tokens(count: int) -> str:
    return f"{count / 1000:.1f}k" if count > 999 else str(count)
