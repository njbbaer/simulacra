import io
from datetime import datetime
from ruamel.yaml.scalarstring import LiteralScalarString

from .yaml_config import yaml


class Logger:
    def __init__(self, filepath):
        self.filepath = filepath

    def log(self, parameters, messages, response):
        buffer = io.StringIO()
        yaml.dump(
            [
                {
                    "timestamp": self._current_timestamp(),
                    "parameters": parameters,
                    "messages": self._format_messages(messages),
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
    def _format_messages(messages):
        return [
            {**msg, "content": LiteralScalarString(msg["content"])} for msg in messages
        ]
