import hashlib
import os
import shutil
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache
from typing import Any

from .. import trials
from ..context import Context
from ..conversation import Conversation
from ..generator import Generator
from ..message import Message
from ..telemetry import Telemetry
from ..turn_stats import TurnStats
from ..utilities import merge_dicts


@dataclass(frozen=True)
class Turn:
    """An assistant message in a log, replayed from the messages before it."""

    log: str
    index: int

    def __post_init__(self) -> None:
        messages = _load(self.log).messages
        if not 0 <= self.index < len(messages):
            raise IndexError(f"{self.id} is out of range")
        if messages[self.index].role != "assistant":
            raise ValueError(f"{self.id} is not an assistant message")

    @property
    def id(self) -> str:
        return f"{os.path.splitext(os.path.basename(self.log))[0]}:{self.index}"

    @property
    def character_dir(self) -> str:
        return os.path.dirname(os.path.dirname(os.path.abspath(self.log)))

    @property
    def logged(self) -> Message:
        return _load(self.log).messages[self.index]

    @property
    def drafts(self) -> list[str]:
        """Return the logged drafts the editor saw, or [] if none were logged."""
        metadata = self.logged.metadata
        if "drafts" in metadata:
            return list(metadata["drafts"])
        return [metadata["draft"]] if "draft" in metadata else []

    def conversation(self) -> Conversation:
        """Return an in-memory copy of the conversation up to this turn."""
        source = _load(self.log)
        conversation = Conversation()
        conversation.vars = dict(source.vars)
        conversation.memories = list(source.memories)
        conversation.messages = source.messages[: self.index]
        return conversation


@dataclass
class Result:
    """A replay's output, with its request stats and prompt hashes."""

    content: str
    display: str
    drafts: list[str]
    notes: str | None
    stats: TurnStats
    prompts: dict[str, str | None]

    def to_dict(self) -> dict[str, Any]:
        requests = self.stats.requests
        return {
            "content": self.content,
            "display": self.display,
            "drafts": self.drafts,
            "notes": self.notes,
            "prompts": self.prompts,
            "duration_ms": self.stats.duration_ms,
            "cost": self.stats.cost,
            "plan_cost": self.stats.plan_cost,
            "plan_usage": self.stats.plan_usage,
            "prompt_tokens": sum(r["prompt_tokens"] for r in requests),
            "cached_tokens": sum(r["cached_tokens"] for r in requests),
            "requests": requests,
        }


async def replay(
    turn: Turn,
    overrides: dict[str, Any] | None = None,
    *,
    drafts: list[str] | None = None,
    snapshot: str | None = None,
) -> Result:
    """Regenerate the turn through the production generator.

    Given drafts, only the editor runs on them. Given a snapshot directory,
    character files and templates come from it instead of the live ones."""
    character_dir = turn.character_dir
    if snapshot:
        name = os.path.basename(character_dir)
        character_dir = os.path.join(snapshot, "characters", name)
    context = Context(
        character_dir,
        overrides=overrides,
        ephemeral=True,
        conversation=turn.conversation(),
    )
    generator = Generator(trials.TrialLog(context), Telemetry(), record_requests=False)
    generation = await generator.generate(context, action="replay", drafts=drafts)
    assert generator.last_turn is not None
    return Result(
        generation.content,
        generation.display,
        generation.drafts,
        generation.editor_notes,
        generator.last_turn,
        _prompt_hashes(context),
    )


async def draft(
    turn: Turn,
    overrides: dict[str, Any] | None = None,
    *,
    snapshot: str | None = None,
) -> Result:
    """Generate one draft for the turn without the editor."""
    no_editor = {"post_process": {"prompt": None}}
    return await replay(
        turn, merge_dicts(overrides or {}, no_editor), snapshot=snapshot
    )


def combine(*results: Result) -> Result:
    """Return the last result, with the stats and prompts of all of them."""
    stats = TurnStats(
        "replay",
        sum(r.stats.duration_ms for r in results),
        [request for r in results for request in r.stats.requests],
    )
    prompts: dict[str, str | None] = {}
    for result in results:
        prompts.update({k: v for k, v in result.prompts.items() if v})
    last = results[-1]
    return Result(last.content, last.display, last.drafts, last.notes, stats, prompts)


def take_snapshot(turns: Iterable[Turn], dest: str) -> str:
    """Copy the turns' character files and shared/ into dest, unless it exists.

    Conversations are left out, and images are linked rather than copied."""
    if os.path.exists(dest):
        return dest
    character_dirs = {turn.character_dir for turn in turns}
    roots = {os.path.dirname(os.path.dirname(d)) for d in character_dirs}
    if len(roots) != 1:
        raise ValueError(f"Turns come from more than one content root: {roots}")
    (root,) = roots
    staging = f"{dest}.partial"
    shutil.rmtree(staging, ignore_errors=True)
    shutil.copytree(os.path.join(root, "shared"), os.path.join(staging, "shared"))
    skipped = shutil.ignore_patterns("conversations", "trials", "images")
    for source in character_dirs:
        target = os.path.join(staging, "characters", os.path.basename(source))
        shutil.copytree(source, target, ignore=skipped)
        images = os.path.join(source, "images")
        if os.path.isdir(images):
            os.symlink(images, os.path.join(target, "images"))
    os.rename(staging, dest)
    return dest


def _prompt_hashes(context: Context) -> dict[str, str | None]:
    data = context.resolved_data
    return {
        "system": _hash(data.get("system_prompt")),
        "reinforcement": _hash(data.get("reinforcement_prompt")),
        "editor": _hash(context.post_process_prompt),
    }


def _hash(text: str | None) -> str | None:
    return hashlib.sha256(text.encode()).hexdigest()[:8] if text else None


@cache
def _load(log: str) -> Conversation:
    return Conversation(log)
