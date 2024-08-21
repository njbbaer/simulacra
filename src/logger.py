import io
from datetime import datetime

from ruamel.yaml.scalarstring import LiteralScalarString

from .yaml_config import yaml


class Logger:
    def __init__(self, filepath):
        self.filepath = filepath

    def log(self, parameters, content, response):
        buffer = io.StringIO()
        yaml.dump(
            [
                {
                    "timestamp": self._current_timestamp(),
                    "parameters": parameters,
                    "content": self._format_text(content),
                    "response": LiteralScalarString(response),
                }
            ],
            buffer,
        )
        with open(self.filepath, "a") as file:
            file.write(buffer.getvalue())

    @staticmethod
    def _current_timestamp():
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _format_text(data):
        if isinstance(data, dict):
            return {
                k: LiteralScalarString(v) if k == "text" else Logger._format_text(v)
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [Logger._format_text(item) for item in data]
        else:
            return data
