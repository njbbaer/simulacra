import io
import os
from typing import Any

from .utilities import PROJECT_ROOT
from .yaml_config import yaml


class RequestRecorder:
    """Logs the exchanges of a single turn for inspection."""

    FILEPATH = os.path.join(PROJECT_ROOT, "last_request.yml")
    URL_MAX_LENGTH = 80

    def __init__(self, filepath: str = FILEPATH) -> None:
        self.filepath = filepath

    def reset(self) -> None:
        """Drop the previous turn's log."""
        if os.path.exists(self.filepath):
            os.remove(self.filepath)

    def record(self, request: Any, response: Any, key: str) -> None:
        log = self._read()
        log[key] = {
            "request": self._normalize(request),
            "response": self._normalize(response),
        }
        buffer = io.StringIO()
        yaml.dump(log, buffer)
        with open(self.filepath, "w") as file:
            file.write(buffer.getvalue())

    def _read(self) -> dict:
        if not os.path.exists(self.filepath):
            return {}
        with open(self.filepath) as file:
            log = yaml.load(file)
        return log if isinstance(log, dict) else {}

    @classmethod
    def _normalize(cls, data: Any, key: str | None = None) -> Any:
        """Convert to plain types, truncating long URLs."""
        if isinstance(data, dict):
            return {k: cls._normalize(v, k) for k, v in data.items()}
        if isinstance(data, list):
            return [cls._normalize(item) for item in data]
        if isinstance(data, str) and key == "url" and len(data) > cls.URL_MAX_LENGTH:
            return data[: cls.URL_MAX_LENGTH] + "..."
        return data
