import pytest

from src.template_resolver import TemplateResolver


@pytest.fixture
def fs_with_templates(fs):
    fs.create_file("/templates/greeting.j2", contents="Hello, {{ name }}!")
    return fs


def test_resolves_simple_variable():
    resolver = TemplateResolver("/")
    data = {"greeting": "Hello, {{ name }}"}
    result = resolver.resolve(data, {"name": "World"})
    assert result["greeting"] == "Hello, World"


def test_resolves_chained_variables():
    resolver = TemplateResolver("/")
    data = {"a": "{{ b }}", "b": "{{ c }}", "c": "final"}
    result = resolver.resolve(data, {})
    assert result["a"] == "final"


def test_resolves_nested_structures():
    resolver = TemplateResolver("/")
    data = {"outer": {"inner": "{{ value }}"}, "items": ["{{ value }}", "static"]}
    result = resolver.resolve(data, {"value": "resolved"})
    assert result["outer"]["inner"] == "resolved"
    assert result["items"] == ["resolved", "static"]


def test_load_resolves_external_file(fs_with_templates):  # noqa: ARG001
    resolver = TemplateResolver("/templates")
    data = {"content": "{{ load('greeting.j2') }}"}
    result = resolver.resolve(data, {"name": "World"})
    assert result["content"] == "Hello, World!"
