from src.lm_executors.chat_executor import ChatExecutor
from src.message import Message


class TestInjectInlineInstructions:
    def test_no_assistant_injects_instruction(self):
        messages = [
            Message("user", "Hello", metadata={"inline_instruction": "be friendly"})
        ]
        result = ChatExecutor._inject_inline_instructions(messages)
        assert result[0].content == "Hello [be friendly]"

    def test_instruction_before_assistant_not_injected(self):
        messages = [
            Message("user", "Hello", metadata={"inline_instruction": "be friendly"}),
            Message("assistant", "Hi there!"),
        ]
        result = ChatExecutor._inject_inline_instructions(messages)
        assert result[0].content == "Hello"
        assert result[1].content == "Hi there!"

    def test_instruction_after_last_assistant_injected(self):
        messages = [
            Message("user", "Old", metadata={"inline_instruction": "instruction"}),
            Message("assistant", "Response"),
            Message("user", "New", metadata={"inline_instruction": "instruction"}),
        ]
        result = ChatExecutor._inject_inline_instructions(messages)
        assert result[0].content == "Old"
        assert result[2].content == "New [instruction]"

    def test_does_not_mutate_originals(self):
        messages = [
            Message("user", "Hello", metadata={"inline_instruction": "instruction"}),
        ]
        ChatExecutor._inject_inline_instructions(messages)
        assert messages[0].content == "Hello"

    def test_none_content_unchanged(self):
        messages = [
            Message("user", None, image="img.png"),
            Message("assistant", "Response"),
        ]
        result = ChatExecutor._inject_inline_instructions(messages)
        assert result[0].content is None

    def test_no_metadata_unchanged(self):
        messages = [
            Message("user", "Hello"),
        ]
        result = ChatExecutor._inject_inline_instructions(messages)
        assert result[0].content == "Hello"

    def test_brackets_in_content_without_instruction_unchanged(self):
        messages = [
            Message("user", "<document>text [footnote 1]</document>"),
            Message("assistant", "Response"),
        ]
        result = ChatExecutor._inject_inline_instructions(messages)
        assert result[0].content == "<document>text [footnote 1]</document>"

    def test_synthetic_message_injects_instruction_only(self):
        messages = [
            Message("user", None, metadata={"inline_instruction": "be creative"}),
        ]
        result = ChatExecutor._inject_inline_instructions(messages)
        assert len(result) == 1
        assert result[0].content == "[be creative]"

    def test_synthetic_message_dropped_after_response(self):
        messages = [
            Message("user", None, metadata={"inline_instruction": "be creative"}),
            Message("assistant", "Response"),
        ]
        result = ChatExecutor._inject_inline_instructions(messages)
        assert len(result) == 1
        assert result[0].content == "Response"
