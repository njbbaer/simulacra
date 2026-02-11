from src.lm_executors.chat_executor import ChatExecutor
from src.message import Message


class TestStripInlineInstructions:
    def test_no_assistant_keeps_original(self):
        messages = [Message("user", "Hello ## in a friendly tone")]
        result = ChatExecutor._strip_inline_instructions(messages)
        assert result[0].content == "Hello ## in a friendly tone"

    def test_strips_instruction_before_assistant(self):
        messages = [
            Message("user", "Hello ## in a friendly tone"),
            Message("assistant", "Hi there!"),
        ]
        result = ChatExecutor._strip_inline_instructions(messages)
        assert result[0].content == "Hello"
        assert result[1].content == "Hi there!"

    def test_users_after_last_assistant_kept(self):
        messages = [
            Message("user", "Old ## instruction"),
            Message("assistant", "Response"),
            Message("user", "New ## instruction"),
        ]
        result = ChatExecutor._strip_inline_instructions(messages)
        assert result[0].content == "Old"
        assert result[2].content == "New ## instruction"

    def test_does_not_mutate_originals(self):
        messages = [
            Message("user", "Hello ## instruction"),
            Message("assistant", "Hi"),
        ]
        ChatExecutor._strip_inline_instructions(messages)
        assert messages[0].content == "Hello ## instruction"

    def test_none_content_unchanged(self):
        messages = [
            Message("user", None, image="img.png"),
            Message("assistant", "Response"),
        ]
        result = ChatExecutor._strip_inline_instructions(messages)
        assert result[0].content is None

    def test_only_last_double_pound_splits(self):
        messages = [
            Message("user", "a ## b ## c"),
            Message("assistant", "Response"),
        ]
        result = ChatExecutor._strip_inline_instructions(messages)
        assert result[0].content == "a ## b"
