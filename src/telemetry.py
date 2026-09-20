import asyncio
import json
import os
import time
from datetime import UTC, datetime
from typing import Any


class Telemetry:
    """Appends one JSON line per request and per turn to the base directory's log."""

    def __init__(self, path: str | None = None, **base: Any) -> None:
        self.path = path
        self._base = base

    @classmethod
    def for_deployment(cls, base_dir: str | None, deployment: str) -> Telemetry:
        """A writer under the base directory, or a no-op without one."""
        if not base_dir:
            return cls()
        return cls(os.path.join(base_dir, "telemetry.jsonl"), deployment=deployment)

    def scoped(self, **base: Any) -> Telemetry:
        """A writer that adds `base` to every record."""
        return Telemetry(self.path, **self._base, **base)

    def start(self, **fields: Any) -> TimedRecord:
        """Begin timing a record that is written when it finishes."""
        return TimedRecord(self, fields)

    def record(self, **fields: Any) -> dict[str, Any]:
        """Append the row to the log, if there is one, and return it."""
        row = {"ts": datetime.now(UTC).isoformat(), **self._base, **fields}
        if self.path:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "a") as file:
                file.write(json.dumps(row) + "\n")
        return row


class TimedRecord:
    """A record in progress, written with its status and duration on completion."""

    def __init__(self, telemetry: Telemetry, fields: dict[str, Any]) -> None:
        self._telemetry = telemetry
        self._fields = {"ts": datetime.now(UTC).isoformat(), **fields}
        self._started = time.monotonic()
        self._attempts = 1

    def retried(self) -> None:
        self._attempts += 1

    def ok(self, **fields: Any) -> dict[str, Any]:
        return self._finish("ok", **fields)

    def fail(self, err: BaseException) -> dict[str, Any]:
        status = "cancelled" if isinstance(err, asyncio.CancelledError) else "error"
        message = f"{type(err).__name__}: {err}" if str(err) else type(err).__name__
        return self._finish(status, error=message)

    def _finish(self, status: str, **fields: Any) -> dict[str, Any]:
        duration_ms = round((time.monotonic() - self._started) * 1000)
        return self._telemetry.record(
            **self._fields,
            status=status,
            duration_ms=duration_ms,
            **({"attempts": self._attempts} if self._attempts > 1 else {}),
            **fields,
        )
