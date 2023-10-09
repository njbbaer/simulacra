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
                    "content": self._format_content(content),
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
    def _format_content(content):
        if isinstance(content, list):
            return [
                {**msg, "content": LiteralScalarString(msg["content"])}
                for msg in content
            ]
        else:
            return LiteralScalarString(content)
