from ruamel.yaml import YAML
from ruamel.yaml.representer import RoundTripRepresenter


# Disable automatic creation of aliases
class NonAliasingRTRepresenter(RoundTripRepresenter):
    def ignore_aliases(self, _):
        return True


yaml = YAML()
yaml.Representer = NonAliasingRTRepresenter
