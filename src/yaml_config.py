from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.representer import RoundTripRepresenter


class NonAliasingRTRepresenter(RoundTripRepresenter):
    def ignore_aliases(self, _: Any) -> bool:
        return True

    def represent_str(self, data: str) -> Any:
        style = "|" if "\n" in data else None
        return self.represent_scalar("tag:yaml.org,2002:str", data, style=style)


NonAliasingRTRepresenter.add_representer(str, NonAliasingRTRepresenter.represent_str)

yaml = YAML()

# Disable aliases and render multiline strings as literal blocks
yaml.Representer = NonAliasingRTRepresenter

# Increase indentation for lists
yaml.indent(mapping=2, sequence=4, offset=2)
