import hashlib
import json
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

type Edit = tuple[str, str, str]

SNAPSHOT_RECORD = "snapshot.json"


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

    def transcript(self) -> str:
        """Return the messages before this turn as `NAME:` and text blocks.

        Names come from the character config; empty messages are skipped."""
        character, user = _names(self.character_dir)
        blocks = []
        for message in self.conversation().messages:
            if text := message.display_text:
                speaker = character if message.role == "assistant" else user
                blocks.append(f"{speaker.upper()}:\n{text}")
        return "\n\n".join(blocks)


def assistant_turns(log: str) -> list[Turn]:
    """Return a Turn for each assistant message in the log."""
    messages = _load(log).messages
    return [Turn(log, i) for i, m in enumerate(messages) if m.role == "assistant"]


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
        return {
            "content": self.content,
            "display": self.display,
            "drafts": self.drafts,
            "notes": self.notes,
            "prompts": self.prompts,
            **_stats_dict(self.stats),
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
    prompts: dict[str, str | None] = {}
    for result in results:
        prompts.update({k: v for k, v in result.prompts.items() if v})
    last = results[-1]
    return Result(
        last.content, last.display, last.drafts, last.notes, _merge(results), prompts
    )


def totals(*results: Result) -> dict[str, Any]:
    """Return the summed request stats of the results, without their outputs."""
    return _stats_dict(_merge(results))


def take_snapshot(turns: Iterable[Turn], dest: str, edits: Iterable[Edit] = ()) -> str:
    """Copy the turns' character files and shared/ into dest, then apply the edits.

    Each edit is (path within dest, old text, new text), and the old text must
    appear exactly once. Conversations are left out, and images are linked
    rather than copied. An existing dest is reused if it was taken with the
    same edits and holds every turn's character."""
    edit_list = [list(edit) for edit in edits]
    character_dirs = {turn.character_dir for turn in turns}
    if os.path.exists(dest):
        record = os.path.join(dest, SNAPSHOT_RECORD)
        if not os.path.exists(record):
            raise ValueError(f"{dest} has no record of its edits")
        with open(record) as file:
            recorded = json.load(file)["edits"]
        if recorded != edit_list:
            raise ValueError(f"{dest} was taken with other edits: {recorded}")
        for source in character_dirs:
            name = os.path.basename(source)
            if not os.path.isdir(os.path.join(dest, "characters", name)):
                raise ValueError(f"{dest} has no character {name}")
        return dest
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
    for path, old, new in edit_list:
        _replace_once(os.path.join(staging, path), old, new)
    with open(os.path.join(staging, SNAPSHOT_RECORD), "w") as file:
        json.dump({"edits": edit_list}, file, indent=1)
    os.rename(staging, dest)
    return dest


def _replace_once(path: str, old: str, new: str) -> None:
    with open(path) as file:
        text = file.read()
    count = text.count(old)
    if count != 1:
        raise ValueError(f"{path} has {count} copies of {old!r}, not one")
    with open(path, "w") as file:
        file.write(text.replace(old, new))


def _merge(results: Iterable[Result]) -> TurnStats:
    results = list(results)
    return TurnStats(
        "replay",
        sum(r.stats.duration_ms for r in results),
        [request for r in results for request in r.stats.requests],
    )


def _stats_dict(stats: TurnStats) -> dict[str, Any]:
    requests = stats.requests
    return {
        "duration_ms": stats.duration_ms,
        "cost": stats.cost,
        "plan_cost": stats.plan_cost,
        "plan_usage": stats.plan_usage,
        "prompt_tokens": sum(r["prompt_tokens"] for r in requests),
        "cached_tokens": sum(r["cached_tokens"] for r in requests),
        "requests": requests,
    }


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


@cache
def _names(character_dir: str) -> tuple[str, str]:
    """Return the character's and the user's names from the character config."""
    context = Context(character_dir, ephemeral=True)
    return context.character_name, context.resolved_data["user_name"]
