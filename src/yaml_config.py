import re
from typing import IO, Any

import yaml as yaml_lib
from ruamel.yaml import YAML
from ruamel.yaml.representer import RoundTripRepresenter

LITERAL_MIN_LENGTH = 80


class NonAliasingRTRepresenter(RoundTripRepresenter):
    def ignore_aliases(self, _: Any) -> bool:
        return True

    def represent_str(self, data: str) -> Any:
        style = "|" if "\n" in data or len(data) > LITERAL_MIN_LENGTH else None
        return self.represent_scalar("tag:yaml.org,2002:str", data, style=style)


NonAliasingRTRepresenter.add_representer(str, NonAliasingRTRepresenter.represent_str)

yaml = YAML()

# Disable aliases and render multiline strings as literal blocks
yaml.Representer = NonAliasingRTRepresenter

# Increase indentation for lists
yaml.indent(mapping=2, sequence=4, offset=2)


class _FastLoader(yaml_lib.CSafeLoader):
    """Parses with libyaml, resolving plain scalars by the YAML 1.2 core schema."""


_FastLoader.yaml_implicit_resolvers = {
    first: [
        (tag, regexp)
        for tag, regexp in resolvers
        if tag.removeprefix("tag:yaml.org,2002:")
        not in {"bool", "int", "float", "timestamp"}
    ]
    for first, resolvers in yaml_lib.CSafeLoader.yaml_implicit_resolvers.items()
}
_FastLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"),
    list("tTfF"),
)
_FastLoader.add_implicit_resolver(
    "tag:yaml.org,2002:int",
    re.compile(r"^[-+]?(?:0|[1-9][0-9]*)$"),
    list("-+0123456789"),
)
_FastLoader.add_implicit_resolver(
    "tag:yaml.org,2002:float",
    re.compile(
        r"^[-+]?(?:\.[0-9]+|[0-9]+\.[0-9]*|[0-9]+(?=[eE]))(?:[eE][-+]?[0-9]+)?$"
        r"|^[-+]?\.(?:inf|Inf|INF)$|^\.(?:nan|NaN|NAN)$"
    ),
    list("-+.0123456789"),
)


def load_fast(stream: IO[str]) -> Any:
    """Load plain data about twenty times faster than the round-trip loader."""
    return yaml_lib.load(stream, Loader=_FastLoader)
