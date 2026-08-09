import io
import os
from typing import Any

from ruamel.yaml.scalarstring import LiteralScalarString

from .yaml_config import yaml


class RequestRecorder:
    URL_MAX_LENGTH = 80
    LITERAL_MIN_LENGTH = 80
    PRIMARY_KEY = "chat"

    def __init__(self, filepath: str) -> None:
        self.filepath = filepath

    def record(self, request: Any, response: Any, key: str = PRIMARY_KEY) -> None:
        """Log an exchange, the primary one starting a fresh log for the turn."""
        log = {} if key == self.PRIMARY_KEY else self._read()
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
        """Convert to plain types, truncating long URLs and blocking long strings."""
        if isinstance(data, dict):
            return {k: cls._normalize(v, k) for k, v in data.items()}
        if isinstance(data, list):
            return [cls._normalize(item) for item in data]
        if isinstance(data, str):
            if key == "url" and len(data) > cls.URL_MAX_LENGTH:
                return data[: cls.URL_MAX_LENGTH] + "..."
            if len(data) > cls.LITERAL_MIN_LENGTH:
                return LiteralScalarString(data)
        return data
