import os
from typing import TYPE_CHECKING, Any

from ..yaml_config import yaml

if TYPE_CHECKING:
    from ..context import Context


class TrialLog:
    """Writes the trial log file, rebuilding it from the conversation each
    time so that records for removed messages are dropped."""

    def __init__(self, context: Context) -> None:
        self._context = context

    def next_id(self) -> int:
        # Ephemeral contexts write no log, so the id is never used
        if self._context.is_ephemeral:
            return 0
        return max(self._read_records(), default=0) + 1

    def delete(self) -> None:
        """Drop the log, for when the conversation is emptied but kept."""
        if self._context.is_ephemeral:
            return
        if not os.path.isdir(self._context.trials_dir):
            return
        if os.path.exists(self._path):
            os.remove(self._path)

    def write(self, record: dict[str, Any] | None = None) -> None:
        if self._context.is_ephemeral:
            return
        if record is None and not os.path.isdir(self._context.trials_dir):
            return
        records = self._read_records()
        if record is None and not records:
            return
        if record is not None:
            records[record["id"]] = record
        data = {
            "conversation_id": self._context.conversation_id,
            "messages": self._build_messages(records),
        }
        os.makedirs(self._context.trials_dir, exist_ok=True)
        with open(self._path, "w") as file:
            yaml.dump(data, file)

    def _build_messages(self, records: dict[int, Any]) -> list[dict[str, Any]]:
        messages = []
        for message in self._context.conversation_messages:
            trial_id = (message.metadata or {}).get("trial")
            entry: dict[str, Any] = {"role": message.role}
            if trial_id in records:
                entry["trial"] = records[trial_id]
            elif message.content:
                entry["content"] = message.content
            else:
                continue
            messages.append(entry)
        return messages

    def _read_records(self) -> dict[int, Any]:
        if not os.path.exists(self._path):
            return {}
        with open(self._path) as file:
            data = yaml.load(file) or {}
        return {
            message["trial"]["id"]: message["trial"]
            for message in data.get("messages", [])
            if "trial" in message
        }

    @property
    def _path(self) -> str:
        filename = f"{self._context.context_name}_{self._context.conversation_id}.yml"
        return os.path.join(self._context.trials_dir, filename)
