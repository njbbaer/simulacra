from unittest.mock import mock_open, patch

import pytest

from src.context import Context


@pytest.fixture
def data():
    return """
    names:
      user: Bob
      assistant: Alice
    vars:
      chat_prompt: "You are Alice, speaking to Bob."
      reinforcement_chat_prompt: "Remember, you are Alice."
    total_cost: 0.25
    conversations:
      - name: 2024-01-01 00:00:00.00
        cost: 0.10
        details:
          - A detail
        messages:
          - role: user
            content: "Hello, Alice!"
          - role: assistant
            content: "Hello, Bob!"
    """


@pytest.fixture
def temp_yaml_file(tmp_path, data):
    p = tmp_path / "temp.yml"
    p.write_text(data)
    return p


@pytest.fixture
def context_instance(temp_yaml_file):
    return Context(temp_yaml_file)


def test_save(temp_yaml_file, context_instance):
    with patch("builtins.open", new_callable=mock_open) as mocked_open:
        context_instance.save()
        mocked_open.assert_called_once_with(temp_yaml_file, "w")


def test_add_message(context_instance):
    context_instance.add_message("user", "Nice to meet you!")
    assert context_instance.current_messages[-1] == {
        "role": "user",
        "content": "Nice to meet you!",
    }


def test_add_cost(context_instance):
    context_instance.add_cost(0.25)
    assert context_instance.total_cost == 0.50


def reset_current_conversation(context_instance):
    context_instance.reset_current_conversation()
    assert context_instance.current_messages == []
    assert context_instance.current_conversation_cost == 0


def test_clear_messages(context_instance):
    context_instance.clear_messages(1)
    assert len(context_instance.current_messages) == 1
    assert context_instance.current_messages[-1]["content"] == "Hello, Alice!"


def test_new_conversation(context_instance):
    context_instance.new_conversation()
    assert len(context_instance.data["conversations"]) == 2
    assert context_instance.current_conversation["name"]
    assert context_instance.current_conversation["cost"] == 0
    assert context_instance.current_conversation["details"] == []
    assert context_instance.current_conversation["messages"] == []


def test_get_name(context_instance):
    assert context_instance.get_name("user") == "Bob"
    assert context_instance.get_name("assistant") == "Alice"


def test_vars(context_instance):
    vars = context_instance.vars
    assert vars["chat_prompt"] == "You are Alice, speaking to Bob."
    assert vars["reinforcement_chat_prompt"] == "Remember, you are Alice."


def test_details(context_instance):
    assert context_instance.current_conversation_details == ["A detail"]


def test_add_conversation_detail(context_instance):
    context_instance.add_conversation_detail("Another detail")
    assert context_instance.current_conversation_details == [
        "A detail",
        "Another detail",
    ]
