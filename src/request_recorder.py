import io
from typing import Any

from ruamel.yaml.scalarstring import LiteralScalarString

from .yaml_config import yaml


class RequestRecorder:
    URL_MAX_LENGTH = 80
    LITERAL_MIN_LENGTH = 80

    def __init__(self, filepath: str) -> None:
        self.filepath = filepath

    def record(self, request: Any, response: Any) -> None:
        buffer = io.StringIO()
        yaml.dump(
            {
                "request": self._normalize(request),
                "response": self._normalize(response),
            },
            buffer,
        )
        with open(self.filepath, "w") as file:
            file.write(buffer.getvalue())

    @classmethod
    def _normalize(cls, data: Any, key: str | None = None) -> Any:
        """Convert to plain types and render multiline strings as YAML blocks."""
        if isinstance(data, dict):
            return {k: cls._normalize(v, k) for k, v in data.items()}
        if isinstance(data, list):
            return [cls._normalize(item) for item in data]
        if isinstance(data, str):
            if key == "url" and len(data) > cls.URL_MAX_LENGTH:
                return data[: cls.URL_MAX_LENGTH] + "..."
            if "\n" in data or len(data) > cls.LITERAL_MIN_LENGTH:
                return LiteralScalarString(data)
        return data
