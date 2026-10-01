import json
import os
import random
from collections.abc import Iterable

from ..conversation_files import ConversationFiles
from .replay import Turn, assistant_turns


def sample_turns(
    characters_dir: str,
    quotas: dict[str, int],
    seed: int,
    path: str,
    *,
    since: dict[str, int] | None = None,
    exclude: Iterable[str] = (),
    min_index: int = 3,
) -> list[Turn]:
    """Draw quotas[character] turns with a logged draft, or reload them from path.

    Turns come from conversations numbered since[character] or later, at
    min_index or later, and not among the excluded turn IDs. A selection is
    saved to path, and reloading raises if it was drawn with other arguments.
    The exclusions aren't compared, since the lists they come from grow."""
    args = {"quotas": quotas, "seed": seed, "since": since or {}, "min": min_index}
    if os.path.exists(path):
        with open(path) as file:
            saved = json.load(file)
        if saved["args"] != args:
            raise ValueError(f"{path} was drawn with {saved['args']}")
        return [Turn(t["log"], t["index"]) for t in saved["turns"]]

    excluded = set(exclude)
    rng = random.Random(seed)
    chosen: list[tuple[str, int]] = []
    for character, quota in quotas.items():
        pool = sorted(
            (turn.log, turn.index)
            for log in _logs(characters_dir, character, (since or {}).get(character, 0))
            for turn in assistant_turns(log)
            if turn.index >= min_index and turn.drafts and turn.id not in excluded
        )
        if len(pool) < quota:
            raise ValueError(f"{character} has {len(pool)} turns, short of {quota}")
        rng.shuffle(pool)
        chosen += pool[:quota]

    with open(path, "w") as file:
        turns = [{"log": log, "index": index} for log, index in chosen]
        json.dump({"args": args, "turns": turns}, file, indent=1)
    return [Turn(log, index) for log, index in chosen]


def _logs(characters_dir: str, character: str, since: int) -> list[str]:
    directory = os.path.join(characters_dir, character, "conversations")
    return [
        os.path.join(directory, conv.filename)
        for conv in ConversationFiles(directory, character).list()
        if conv.id >= since and "sync-conflict" not in conv.filename
    ]
