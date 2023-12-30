from unittest.mock import mock_open, patch

import pytest

from src.context import Context


@pytest.fixture
def data():
    return """
    names:
      user: Alice
      bot: Bob
    prompts:
      chat_prompt: "You are Alice, speaking to Bob."
      reinforcement_chat_prompt: "Remember, you are Alice."
    conversations:
      - memory: []
        messages: []
    """


@pytest.fixture
def temp_yaml_file(tmp_path, data):
    p = tmp_path / "temp.yml"
    p.write_text(data)
    return p


@pytest.fixture
def context_instance(temp_yaml_file):
    return Context(temp_yaml_file)


def test_load(context_instance):
    assert context_instance.data["names"] == {"user": "Alice", "bot": "Bob"}


def test_add_message(context_instance):
    context_instance.add_message("user", "Hello, Bob!")
    assert context_instance.current_messages[-1] == {
        "role": "user",
        "content": "Hello, Bob!",
    }


def test_save(temp_yaml_file, context_instance):
    with patch("builtins.open", new_callable=mock_open) as mocked_open:
        context_instance.save()
        mocked_open.assert_called_once_with(temp_yaml_file, "w")


def test_add_cost(context_instance):
    context_instance.add_cost(50)
    assert context_instance.data["total_cost"] == 50


def test_append_memory(context_instance):
    context_instance.append_memory("Recall our previous discussion about AI.")
    assert (
        context_instance.current_memory_chunks[-1]
        == "Recall our previous discussion about AI."
    )


def test_clear_messages_no_argument(context_instance):
    context_instance.add_message("user", "Message 1")
    context_instance.add_message("bot", "Message 2")
    context_instance.clear_messages()
    assert not context_instance.current_messages


def test_clear_messages_with_argument(context_instance):
    context_instance.add_message("user", "Message 1")
    context_instance.add_message("bot", "Message 2")
    context_instance.clear_messages(1)
    assert (
        len(context_instance.current_messages) == 1
        and context_instance.current_messages[0]["role"] == "user"
    )


def test_new_conversation(context_instance):
    initial_conversations_count = len(context_instance.data["conversations"])
    context_instance.new_conversation(["Memory"])
    assert (
        len(context_instance.data["conversations"]) == initial_conversations_count + 1
    )
    assert context_instance.current_conversation["memory"][0] == "Memory"


def test_get_name(context_instance):
    assert context_instance.get_name("user") == "Alice"
    assert context_instance.get_name("bot") == "Bob"


def test_properties(context_instance):
    assert context_instance.chat_prompt == "You are Alice, speaking to Bob."
    assert context_instance.reinforcement_chat_prompt == "Remember, you are Alice."
