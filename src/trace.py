import io
import json
from typing import Any

from ruamel.yaml.scalarstring import LiteralScalarString

from .yaml_config import yaml


class Trace:
    def __init__(self, filepath: str) -> None:
        self.filepath = filepath

    def record(self, parameters: dict[str, Any], content: Any, response: str) -> None:
        buffer = io.StringIO()
        yaml.dump(
            {
                "api_params": self._normalize_data(parameters),
                "content": self._format_text(content),
                "response": LiteralScalarString(response),
            },
            buffer,
        )
        with open(self.filepath, "w") as file:
            file.write(buffer.getvalue())

    @staticmethod
    def _normalize_data(data: Any) -> Any:
        """Normalize data by removing YAML metadata (e.g. comments)."""
        return json.loads(json.dumps(data))

    @staticmethod
    def _format_text(data: Any) -> Any:
        if isinstance(data, dict):
            return {key: Trace._format_value(key, value) for key, value in data.items()}
        if isinstance(data, list):
            return [Trace._format_text(item) for item in data]
        return data

    @staticmethod
    def _format_value(key: str, value: Any) -> Any:
        if key == "text" and isinstance(value, str):
            return LiteralScalarString(value)

        if key == "url" and isinstance(value, str):
            return value[:256] + "..." if len(value) > 256 else value

        return Trace._format_text(value)
