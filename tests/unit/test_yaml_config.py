import io

from src.yaml_config import yaml


def _dump(data) -> str:
    buffer = io.StringIO()
    yaml.dump(data, buffer)
    return buffer.getvalue()


def test_only_multiline_strings_dump_as_literal_blocks():
    assert _dump({"text": "one\ntwo"}) == "text: |-\n  one\n  two\n"
    assert _dump({"text": "one"}) == "text: one\n"
