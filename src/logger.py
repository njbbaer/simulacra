import io
from typing import Any

from ruamel.yaml.scalarstring import LiteralScalarString

from .yaml_config import yaml


class Logger:
    def __init__(self, filepath: str) -> None:
        self.filepath = filepath

    def log(self, parameters: dict[str, Any], content: Any, response: str) -> None:
        buffer = io.StringIO()
        yaml.dump(
            {
                "parameters": parameters,
                "content": self._format_text(content),
                "response": LiteralScalarString(response),
            },
            buffer,
        )
        with open(self.filepath, "w") as file:
            file.write(buffer.getvalue())

    @staticmethod
    def _format_text(data: Any) -> Any:
        if isinstance(data, dict):
            return {
                key: Logger._format_value(key, value) for key, value in data.items()
            }
        elif isinstance(data, list):
            return [Logger._format_text(item) for item in data]
        else:
            return data

    @staticmethod
    def _format_value(key: str, value: Any) -> Any:
        # Convert text fields to multi-line strings
        if key == "text" and isinstance(value, str):
            return LiteralScalarString(value)

        # Truncate long URLs
        if key == "url" and isinstance(value, str):
            return value[:256] + "..." if len(value) > 256 else value

        return Logger._format_text(value)
