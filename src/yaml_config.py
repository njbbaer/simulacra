from ruamel.yaml import YAML
from ruamel.yaml.representer import RoundTripRepresenter


class NonAliasingRTRepresenter(RoundTripRepresenter):
    def ignore_aliases(self, _):
        return True


yaml = YAML()

# Disable automatic creation of aliases
yaml.Representer = NonAliasingRTRepresenter

# Increase indentation for lists
yaml.indent(mapping=2, sequence=4, offset=2)
