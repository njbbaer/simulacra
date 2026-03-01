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
        assert context._conversation_files.next_id() == 6


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

    def test_preserves_conversation_name(self, context):
        context.save()  # Create the conversation file on disk
        context.name_conversation("adventure")
        context.add_message("user", "Hello")
        context.extend_conversation()

        assert context.conversation_name == "adventure"
        assert context.conversation_id == 2  # New conversation with next ID


class TestSwitchConversation:
    @pytest.fixture
    def base_conversation_data(self):
        return {"created_at": "2024-01-01", "cost": 0, "messages": []}

    def test_switch_by_id(
        self,
        context_fs,  # noqa: ARG002
        context,
        base_conversation_data,
    ):
        with open("/test/conversations/alice_5.yml", "w") as f:
            yaml.dump(base_conversation_data, f)
        conv_id, conv_name = context.switch_conversation("5")
        assert conv_id == 5
        assert conv_name is None
        assert context.conversation_id == 5

    def test_switch_by_name(
        self,
        context_fs,  # noqa: ARG002
        context,
        base_conversation_data,
    ):
        with open("/test/conversations/alice_3_quest.yml", "w") as f:
            yaml.dump(base_conversation_data, f)
        conv_id, conv_name = context.switch_conversation("quest")
        assert conv_id == 3
        assert conv_name == "quest"


class TestNameConversation:
    def test_renames_conversation_file(self, context):
        context.save()  # Create the conversation file on disk
        sanitized = context.name_conversation("My Adventure")
        assert sanitized == "my_adventure"
        assert context.conversation_name == "my_adventure"
        assert "my_adventure" in context.conversation_file


class TestCostTracking:
    def test_increments_both_context_and_conversation(self, context):
        initial_context_cost = context._raw_data["total_cost"]
        initial_conv_cost = context.conversation_cost
        context.increment_cost(0.5)
        assert context._raw_data["total_cost"] == initial_context_cost + 0.5
        assert context.conversation_cost == initial_conv_cost + 0.5


class TestExtends:
    def test_inherits_base_values(self, fs):
        fs.create_dir("/test/conversations")
        fs.create_file(
            "/base.yml",
            contents=dedent("""
                api_params:
                  model: base/model
                require_tags:
                  - tag_a
                shared_field: from_base
            """),
        )
        fs.create_file(
            "/test/context.yml",
            contents=dedent("""
                extends: ../base.yml
                character_name: Alice
                user_name: Bob
                total_cost: 0
                api_params:
                  model: test/model
            """),
        )
        ctx = Context("/test/context.yml")
        ctx.load()
        assert ctx._data["api_params"]["model"] == "test/model"
        assert ctx._data["shared_field"] == "from_base"
        assert ctx._data["require_tags"] == ["tag_a"]
        assert "extends" not in ctx._data

    def test_no_extends_key(self, context):
        assert "extends" not in context._data
        assert context._data["character_name"] == "Alice"


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
