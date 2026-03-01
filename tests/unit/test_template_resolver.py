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
    data = {"content": "{{ load_string('greeting.j2') }}"}
    result = resolver.resolve(data, {"name": "World"})
    assert result["content"] == "Hello, World!"


def test_search_dirs_fallback(fs):
    fs.create_file("/shared/common.md", contents="shared content")
    fs.create_file("/character/local.md", contents="local content")
    resolver = TemplateResolver("/character", search_dirs=["/shared"])
    data = {"a": "{{ load_string('common.md') }}", "b": "{{ load_string('local.md') }}"}
    result = resolver.resolve(data, {})
    assert result["a"] == "shared content"
    assert result["b"] == "local content"


def test_search_dirs_local_takes_priority(fs):
    fs.create_file("/shared/file.md", contents="from shared")
    fs.create_file("/character/file.md", contents="from local")
    resolver = TemplateResolver("/character", search_dirs=["/shared"])
    data = {"content": "{{ load_string('file.md') }}"}
    result = resolver.resolve(data, {})
    assert result["content"] == "from local"


def test_load_yaml_file(fs):
    fs.create_file("/config/data.yml", contents="key: value\ncount: 42")
    resolver = TemplateResolver("/config")
    data = {"loaded": "{{ load_yaml('data.yml') }}"}
    result = resolver.resolve(data, {})
    assert result["loaded"] == {"key": "value", "count": 42}
