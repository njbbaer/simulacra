import io

from src.yaml_config import load_fast, yaml


def _dump(data) -> str:
    buffer = io.StringIO()
    yaml.dump(data, buffer)
    return buffer.getvalue()


def test_only_multiline_strings_dump_as_literal_blocks():
    assert _dump({"text": "one\ntwo"}) == "text: |-\n  one\n  two\n"
    assert _dump({"text": "one"}) == "text: one\n"


def test_fast_loader_resolves_scalars_like_the_round_trip_loader():
    text = "a: yes\nb: No\nc: 1e-05\nd: 2026-10-23\ne: 10:30\nf: true\ng: 3\n"
    assert load_fast(io.StringIO(text)) == {
        "a": "yes",
        "b": "No",
        "c": 1e-05,
        "d": "2026-10-23",
        "e": "10:30",
        "f": True,
        "g": 3,
    }
