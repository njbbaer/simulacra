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
def loaded_context(temp_yaml_file):
    context = Context(temp_yaml_file)
    context.load()
    return context


def test_load(loaded_context):
    assert loaded_context.data["names"] == {"user": "Alice", "bot": "Bob"}


def test_add_message(loaded_context):
    loaded_context.add_message("user", "Hello, Bob!")
    assert loaded_context.current_messages[-1] == {
        "role": "user",
        "content": "Hello, Bob!",
    }


def test_save(temp_yaml_file, loaded_context):
    with patch("builtins.open", new_callable=mock_open) as mocked_open:
        loaded_context.save()
        mocked_open.assert_called_once_with(temp_yaml_file, "w")


def test_add_cost(loaded_context):
    loaded_context.add_cost(50)
    assert loaded_context.data["total_cost"] == 50


def test_append_memory(loaded_context):
    loaded_context.append_memory("Recall our previous discussion about AI.")
    assert (
        loaded_context.current_memory_chunks[-1]
        == "Recall our previous discussion about AI."
    )


def test_clear_messages_no_argument(loaded_context):
    loaded_context.add_message("user", "Message 1")
    loaded_context.add_message("bot", "Message 2")
    loaded_context.clear_messages()
    assert not loaded_context.current_messages


def test_clear_messages_with_argument(loaded_context):
    loaded_context.add_message("user", "Message 1")
    loaded_context.add_message("bot", "Message 2")
    loaded_context.clear_messages(1)
    assert (
        len(loaded_context.current_messages) == 1
        and loaded_context.current_messages[0]["role"] == "user"
    )


def test_new_conversation(loaded_context):
    initial_conversations_count = len(loaded_context.data["conversations"])
    loaded_context.new_conversation(["In the previous conversation..."])
    assert len(loaded_context.data["conversations"]) == initial_conversations_count + 1
    assert (
        loaded_context.current_conversation["memory"][0]
        == "In the previous conversation..."
    )


def test_get_name(loaded_context):
    assert loaded_context.get_name("user") == "Alice"
    assert loaded_context.get_name("bot") == "Bob"


def test_properties(loaded_context):
    assert loaded_context.chat_prompt == "You are Alice, speaking to Bob."
    assert loaded_context.reinforcement_chat_prompt == "Remember, you are Alice."
    loaded_context.add_message("user", "Just testing properties.")
    assert loaded_context.current_conversation_size == len("Just testing properties.")
    assert not loaded_context.current_memory_size


def test_current_memory_size_with_memory(loaded_context):
    loaded_context.append_memory("Remembering something important.")
    assert loaded_context.current_memory_size == len("Remembering something important.")


def test_current_conversation_size_multiple_messages(loaded_context):
    loaded_context.add_message("user", "First message.")
    loaded_context.add_message("bot", "Second message.")
    expected_size = len("First message.") + len("Second message.")
    assert loaded_context.current_conversation_size == expected_size
