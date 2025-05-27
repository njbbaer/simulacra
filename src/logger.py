import io
from typing import Any, Dict

from ruamel.yaml.scalarstring import LiteralScalarString

from .yaml_config import yaml


class Logger:
    def __init__(self, filepath: str) -> None:
        self.filepath = filepath

    def log(self, parameters: Dict[str, Any], content: Any, response: str) -> None:
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
                k: LiteralScalarString(v) if k == "text" else Logger._format_text(v)
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [Logger._format_text(item) for item in data]
        else:
            return data
