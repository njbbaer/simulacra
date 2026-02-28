import os
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from src.message import Message
from src.simulacrum import Simulacrum
from src.yaml_config import yaml


@pytest.fixture
def context_data() -> dict[str, Any]:
    return {
        "character_name": "test",
        "user_name": "user",
        "conversation_file": "file://./conversations/test_0.yml",
        "total_cost": 0.0,
        "api_params": {"model": "test/model"},
        "system_prompt": "Hello",
        "instruction_presets": {
            "formal": {
                "content": "Be formal.",
                "name": "Formal Tone",
                "trigger": r"(?i)\bformal\b",
            },
        },
    }


@pytest.fixture
def conversation_data() -> dict[str, Any]:
    return {
        "cost": 0.0,
        "messages": [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
        ],
    }


@pytest.fixture
def sim(fs, context_data, conversation_data):
    fs.add_real_file("src/lm_executors/chat_executor_template.j2")
    with open("context.yml", "w") as f:
        yaml.dump(context_data, f)
    os.makedirs("conversations", exist_ok=True)
    with open("conversations/test_0.yml", "w") as f:
        yaml.dump(conversation_data, f)
    return Simulacrum("context.yml")


class TestExtractInlineInstruction:
    def test_with_instruction(self):
        text, instruction = Simulacrum._extract_inline_instruction("Hello [be concise]")
        assert text == "Hello"
        assert instruction == "be concise"

    def test_preserves_brackets_mid_text(self):
        text, instruction = Simulacrum._extract_inline_instruction("a [b] c [d]")
        assert text == "a [b] c"
        assert instruction == "d"


class TestAppendDocument:
    def test_with_text(self):
        result = Simulacrum._append_document("my message", "doc content")
        assert "<document>\ndoc content\n</document>" in result
        assert "my message" in result

    def test_without_text(self):
        result = Simulacrum._append_document(None, "doc content")
        assert "<document>\ndoc content\n</document>" in result


class TestUndoRetry:
    def test_undo_removes_user_and_assistant_pair(self, sim):
        sim.undo()
        assert len(sim.context.conversation_messages) == 0

    def test_undo_removes_only_user_when_last_message_is_user(self, sim):
        sim.context.load()
        with sim.context.session():
            sim.context.conversation_messages.append(Message("user", "another"))
        sim.undo()
        msgs = sim.context.conversation_messages
        assert len(msgs) == 2
        assert msgs[0].role == "user" and msgs[0].content == "Hi"
        assert msgs[1].role == "assistant" and msgs[1].content == "Hello"

    def test_undo_removes_only_last_assistant_when_consecutive(self, sim):
        sim.context.load()
        with sim.context.session():
            sim.context.conversation_messages.append(Message("assistant", "continued"))
        sim.undo()
        msgs = sim.context.conversation_messages
        assert len(msgs) == 2
        assert msgs[0].role == "user" and msgs[0].content == "Hi"
        assert msgs[1].role == "assistant" and msgs[1].content == "Hello"

    def test_undo_clears_retry_stack(self, sim):
        sim.retry_stack.append([Message("assistant", "old")])
        sim.undo()
        assert sim.retry_stack == []

    def test_undo_retry_restores_previous_message(self, sim):
        sim.retry_stack.append([Message("assistant", "original response")])

        result = sim.undo_retry()

        assert result is True
        msgs = sim.context.conversation_messages
        assert msgs[-1].content == "original response"
        assert sim.retry_stack == []

    def test_undo_retry_with_empty_stack(self, sim):
        assert sim.undo_retry() is False


class TestApplyInstruction:
    def test_known_preset(self, sim):
        result = sim.apply_instruction("formal")
        assert result == "Formal Tone"
        assert sim._pending_instruction is not None
        assert sim._pending_instruction.content == "Be formal."
        assert sim._pending_instruction.preset_key == "formal"

    def test_unknown_preset_uses_freeform(self, sim):
        result = sim.apply_instruction("be very creative")
        assert result is None
        assert sim._pending_instruction is not None
        assert sim._pending_instruction.content == "be very creative"
        assert sim._pending_instruction.preset_key is None


class TestSetInlineInstruction:
    def test_on_existing_user_message(self, sim):
        sim._set_inline_instruction("do something")
        msgs = sim.context.conversation_messages
        user_msg = next(m for m in reversed(msgs) if m.role == "user")
        assert user_msg.metadata["inline_instruction"] == "do something"

    def test_creates_synthetic_when_no_user_message(self, sim):
        sim.context.load()
        sim.context.conversation_messages.clear()
        sim.context.add_message("assistant", "Hi")
        sim.context.save()

        sim._set_inline_instruction("do something")
        msgs = sim.context.conversation_messages
        synthetic = [m for m in msgs if m.metadata.get("inline_instruction")]
        assert len(synthetic) == 1
        assert synthetic[0].role == "user"
        assert synthetic[0].content is None


class TestApplyPendingPreset:
    def test_wraps_text(self, sim):
        sim.apply_instruction("formal")
        text, key = sim._apply_pending_preset("Hello")
        assert "<instruct>\nBe formal.\n</instruct>" in text
        assert "Hello" in text
        assert key == "formal"
        assert sim._pending_instruction is None

    def test_auto_triggers(self, sim):
        sim.context.load()
        text, key = sim._apply_pending_preset("Please be formal about it")
        assert "<instruct>\nBe formal.\n</instruct>" in text
        assert key == "formal"

    def test_no_match(self, sim):
        sim.context.load()
        text, key = sim._apply_pending_preset("Just a normal message")
        assert text == "Just a normal message"
        assert key is None

    def test_does_not_retrigger(self, sim):
        """A preset already triggered should not trigger again."""
        sim.context.load()
        sim.context.add_message(
            "user",
            "be formal",
            metadata={"triggered_preset": "formal"},
        )
        sim.context.save()
        sim.context.load()

        text, key = sim._apply_pending_preset("Please be formal again")
        assert key is None
        assert "<instruct>" not in text


class TestChat:
    @pytest.mark.asyncio
    async def test_documents_are_attached(self, sim):
        with patch.object(sim, "_generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = ("response content", "response content")
            await sim.chat("hello", None, ["doc1", "doc2"])

        msgs = sim.context.conversation_messages
        user_msg = next(
            m
            for m in msgs
            if m.role == "user" and m.content and "<document>" in m.content
        )
        assert "<document>\ndoc1\n</document>" in user_msg.content
        assert "<document>\ndoc2\n</document>" in user_msg.content
