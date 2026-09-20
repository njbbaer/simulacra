from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.lm_executors.chat_executor import ChatExecutor
from src.message import Message

COMPLETION = {
    "choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cost": 0.001},
}


class TestSessionId:
    @pytest.mark.asyncio
    async def test_includes_session_id(self):
        context = MagicMock(api_params={"model": "m"}, session_id="alice_42")
        executor = ChatExecutor(context, request_key="k")
        with (
            patch.object(executor, "_build_messages", return_value=[]),
            patch("src.lm_executors.chat_executor.RequestRecorder"),
            patch(
                "src.lm_executors.chat_executor.fetch_completion",
                new=AsyncMock(return_value=COMPLETION),
            ) as fetch,
        ):
            await executor.execute()
        assert fetch.call_args.args[0]["session_id"] == "alice_42"


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


class TestStripImages:
    def test_removes_image_from_message(self):
        messages = [Message("user", "Look", image="img.png")]
        result = ChatExecutor._strip_images(messages)
        assert result[0].image is None
        assert result[0].content == "Look"

    def test_image_only_message_gets_placeholder(self):
        messages = [
            Message("user", None, image="img.png"),
            Message("assistant", "Response"),
        ]
        result = ChatExecutor._strip_images(messages)
        assert len(result) == 2
        assert result[0].content == "[image]"
        assert result[0].image is None

    def test_does_not_mutate_originals(self):
        messages = [Message("user", "Look", image="img.png")]
        ChatExecutor._strip_images(messages)
        assert messages[0].image == "img.png"
