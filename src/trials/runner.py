import asyncio
import random
import string
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..context import Context

ALIASES = string.ascii_uppercase


@dataclass(frozen=True)
class Stage:
    """A named stage of a turn, with candidates under `scope` or at the root."""

    name: str
    scope: str | None = None

    def request_key(self, alias: str | None) -> str:
        return self.name if alias is None else f"{self.name}_{alias}"


@dataclass
class TrialRun[T]:
    """The result of a stage, plus every candidate output when there are any."""

    result: T
    selected: str | None = None
    outputs: dict[str, T] = field(default_factory=dict)

    @property
    def candidates(self) -> dict[str, T]:
        """Every output by alias, or just the result when the stage ran no trial."""
        return self.outputs or {ALIASES[0]: self.result}


async def run[T](
    context: Context,
    stage: Stage,
    execute: Callable[[Context, str | None], Awaitable[T]],
) -> TrialRun[T]:
    """Run `execute` once per candidate and select one at random.

    Runs it once against the unmodified context if no candidates are configured.
    """
    candidates = _candidates(context, stage.scope)
    if not candidates:
        return TrialRun(await execute(context, None))

    aliases = list(ALIASES[: len(candidates)])
    results = await asyncio.gather(
        *(
            execute(context.with_overrides(_scoped(stage.scope, candidate)), alias)
            for alias, candidate in zip(aliases, candidates, strict=True)
        )
    )
    outputs = dict(zip(aliases, results, strict=True))
    selected = random.choice(aliases)
    return TrialRun(outputs[selected], selected, outputs)


def _candidates(context: Context, scope: str | None) -> list[dict]:
    data = context.resolved_data
    block = (data.get(scope) or {}) if scope else data
    return block.get("candidates") or []


def _scoped(scope: str | None, overrides: dict) -> dict:
    overrides = {k: v for k, v in overrides.items() if k != "candidates"}
    return {scope: overrides} if scope else overrides
