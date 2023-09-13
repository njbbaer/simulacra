import os
from datetime import datetime
from ruamel.yaml.scalarstring import LiteralScalarString

from src.yaml_config import yaml


class Logger:
    def __init__(self, filepath):
        self.filepath = filepath
        self._load()

    def record(self, messages, parameters):
        self.log.append({
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'parameters': parameters,
            'messages': messages,
        })
        self._save()

    def attach_response(self, response):
        self.log[-1]['response'] = LiteralScalarString(response)
        self._save()

    def _load(self):
        if os.path.exists(self.filepath):
            with open(self.filepath, 'r') as file:
                self.log = yaml.load(file)
        else:
            self.log = []

    def _save(self):
        with open(self.filepath, 'w') as file:
            yaml.dump(self.log, file)
