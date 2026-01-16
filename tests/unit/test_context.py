from textwrap import dedent

import pytest

from src.context import Context
from src.yaml_config import yaml


@pytest.fixture
def base_context_data():
    return {
        "character_name": "Alice",
        "user_name": "Bob",
        "total_cost": 1.5,
        "api_params": {"model": "test/model"},
        "system_prompt": "You are {{ character_name }}.",
    }


@pytest.fixture
def context_fs(fs, base_context_data):
    fs.create_dir("/test/conversations")
    with open("/test/context.yml", "w") as f:
        yaml.dump(base_context_data, f)
    return fs


@pytest.fixture
def context(context_fs) -> Context:  # noqa: ARG001
    ctx = Context("/test/context.yml")
    ctx.load()
    return ctx


class TestSession:
    def test_session_saves_on_exit(self, context):
        with context.session():
            context._raw_data["total_cost"] = 99.0

        context.load()
        assert context._raw_data["total_cost"] == 99.0

    def test_session_reloads_when_superseded(self, context):
        with context.session():
            context._raw_data["total_cost"] = 99.0
            context._session_version += 1  # Simulate supersession

        context.load()
        assert context._raw_data["total_cost"] == 1.5

    def test_session_superseded_flag(self, context):
        with context.session() as session:
            assert not session.superseded
            context._session_version += 1
            assert session.superseded


class TestConversationId:
    def test_extracts_id_from_path(self, context):
        context._data["conversation_file"] = "file://./conversations/alice_42.yml"
        assert context.conversation_id == 42

    def test_raises_on_invalid_format(self, context):
        context._data["conversation_file"] = "file://./conversations/invalid.yml"
        with pytest.raises(ValueError, match="Invalid conversation file format"):
            _ = context.conversation_id

    def test_generates_sequential_id(self, context_fs, context):
        context_fs.create_file("/test/conversations/alice_1.yml")
        context_fs.create_file("/test/conversations/alice_5.yml")
        context_fs.create_file("/test/conversations/alice_3.yml")
        assert context._next_conversation_id() == 6


class TestNewConversation:
    def test_creates_new_conversation_file(self, context):
        context.new_conversation()
        assert context.conversation_file == "file://./conversations/alice_1.yml"
        assert len(context.conversation_messages) == 0

    def test_increments_conversation_id(self, context_fs, context):
        context_fs.create_file("/test/conversations/alice_1.yml")
        context.new_conversation()
        assert context.conversation_file == "file://./conversations/alice_2.yml"


class TestExtendConversation:
    def test_preserves_messages_as_memory(self, context):
        context.add_message("user", "Hello")
        context.add_message("assistant", "Hi there")
        context.extend_conversation()

        assert context.conversation_file == "file://./conversations/alice_1.yml"
        assert len(context.conversation_messages) == 0
        assert len(context.conversation_memories) == 1
        assert "BOB:" in context.conversation_memories[0]
        assert "ALICE:" in context.conversation_memories[0]


class TestCostTracking:
    def test_increments_both_context_and_conversation(self, context):
        initial_context_cost = context._raw_data["total_cost"]
        initial_conv_cost = context.conversation_cost
        context.increment_cost(0.5)
        assert context._raw_data["total_cost"] == initial_context_cost + 0.5
        assert context.conversation_cost == initial_conv_cost + 0.5


class TestTemplateResolution:
    def test_resolves_templates_with_context_vars(self, context):
        assert context._data["system_prompt"] == "You are Alice."

    def test_provides_conversation_vars_to_templates(self, fs):
        fs.create_dir("/test/conversations")
        fs.create_file(
            "/test/context.yml",
            contents=dedent("""
                character_name: Alice
                user_name: Bob
                total_cost: 0
                conversation_file: file://./conversations/alice_1.yml
                api_params:
                  model: test/model
                system_prompt: "Mood: {{ vars.mood }}"
            """),
        )
        fs.create_file(
            "/test/conversations/alice_1.yml",
            contents=dedent("""
                created_at: "2024-01-01"
                cost: 0
                vars:
                  mood: happy
                messages: []
            """),
        )
        ctx = Context("/test/context.yml")
        ctx.load()
        assert ctx._data["system_prompt"] == "Mood: happy"
