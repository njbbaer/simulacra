from textwrap import dedent

import pytest

from src.resolve_vars import resolve_vars


@pytest.fixture
def vars():
    return {
        "list_of_things": ["thing1", "{{ jinja_thing }}"],
        "chat_prompt": "file:chat_prompt.j2",
        "reinforcement_chat_prompt": "Remember, you are Alice.",
        "jinja_thing": "thing2",
    }


@pytest.fixture
def chat_prompt_file_content():
    return dedent(
        """
        You are Alice, speaking to Bob.
        {% for thing in list_of_things %}
          - {{ thing }}
        {% endfor %}
        """
    ).strip()


@pytest.fixture
def mock_read_chat_prompt(mocker, chat_prompt_file_content):
    mock_open = mocker.mock_open(read_data=chat_prompt_file_content)
    return mocker.patch("builtins.open", mock_open)


def test_resolve(mock_read_chat_prompt, vars):
    resolved_vars = resolve_vars(vars, "base_path")

    mock_read_chat_prompt.assert_called_once_with("base_path/chat_prompt.j2")
    assert resolved_vars["list_of_things"] == ["thing1", "thing2"]
    assert resolved_vars["reinforcement_chat_prompt"] == "Remember, you are Alice."
    assert (
        resolved_vars["chat_prompt"]
        == "You are Alice, speaking to Bob.\n  - thing1\n  - thing2"
    )
