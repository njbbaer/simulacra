from textwrap import dedent

import pytest

from src.context import Context
from src.yaml_config import yaml


@pytest.fixture
def base_context_data():
    return {
        "character_name": "Alice",
        "total_cost": 1.5,
        "api_params": {"model": "test/model"},
        "system_prompt": "You are {{ character_name }}.",
    }


@pytest.fixture
def context_fs(fs, base_context_data):
    fs.create_dir("/test/conversations")
    with open("/test/alice.yml", "w") as f:
        yaml.dump(base_context_data, f)
    return fs


@pytest.fixture
def context(context_fs) -> Context:  # noqa: ARG001
    ctx = Context("/test/alice.yml")
    ctx.load()
    return ctx


class TestSession:
    def test_session_saves_on_exit(self, context):
        with context.session():
            context._state_data["total_cost"] = 99.0

        context.load()
        assert context._state_data["total_cost"] == 99.0

    def test_session_reloads_when_superseded(self, context):
        with context.session():
            context._state_data["total_cost"] = 99.0
            context._session_version += 1  # Simulate supersession

        context.load()
        assert "total_cost" not in context._state_data

    def test_session_superseded_flag(self, context):
        with context.session() as session:
            assert not session.superseded
            context._session_version += 1
            assert session.superseded


class TestConversationId:
    def test_extracts_id_from_path(self, context):
        context._state_data["conversation_file"] = "file://./conversations/alice_42.yml"
        assert context.conversation_id == 42

    def test_raises_on_invalid_format(self, context):
        context._state_data["conversation_file"] = "file://./conversations/invalid.yml"
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

    def test_names_from_context_file_not_character_name(self, fs):
        fs.create_dir("/test/conversations")
        with open("/test/agatha.yml", "w") as f:
            yaml.dump(
                {"character_name": "Alice", "api_params": {"model": "test/model"}}, f
            )
        ctx = Context("/test/agatha.yml")
        ctx.new_conversation()
        assert ctx.conversation_file == "file://./conversations/agatha_1.yml"

    def test_increments_conversation_id(self, context_fs, context):
        context_fs.create_file("/test/conversations/alice_1.yml")
        context.new_conversation()
        assert context.conversation_file == "file://./conversations/alice_2.yml"


class TestCompactConversation:
    def test_preserves_messages_as_memory(self, context):
        context.add_message("user", "Hello")
        context.add_message("assistant", "Hi there")
        context.compact_conversation()

        assert context.conversation_file == "file://./conversations/alice_1.yml"
        assert len(context.conversation_messages) == 0
        assert len(context.conversation_memories) == 1
        assert "---" in context.conversation_memories[0]
        assert "ALICE:" in context.conversation_memories[0]

    def test_preserves_conversation_name(self, context):
        context.save()  # Create the conversation file on disk
        context.name_conversation("adventure")
        context.add_message("user", "Hello")
        context.compact_conversation()

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
        initial_conv_cost = context.conversation_cost
        context.increment_cost(0.5)
        assert context._state_data["total_cost"] == 0.5
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

    def test_chained_extends(self, fs):
        fs.create_dir("/test/conversations")
        fs.create_file(
            "/shared/root.yml",
            contents=dedent("""
                api_params:
                  model: root/model
                root_field: from_root
            """),
        )
        fs.create_file(
            "/parent/parent.yml",
            contents=dedent("""
                extends: ../shared/root.yml
                character_name: Alice
                parent_field: from_parent
            """),
        )
        fs.create_file(
            "/test/context.yml",
            contents=dedent("""
                extends: ../parent/parent.yml
                total_cost: 0
                parent_field: overridden
            """),
        )
        ctx = Context("/test/context.yml")
        ctx.load()
        assert ctx._data["character_name"] == "Alice"
        assert ctx._data["root_field"] == "from_root"
        assert ctx._data["parent_field"] == "overridden"
        assert "extends" not in ctx._data

    def test_inherits_extended_content_dirs(self, fs):
        fs.create_dir("/test/conversations")
        fs.create_file("/parent/content/doc.md", contents="parent doc")
        fs.create_file("/parent/content/shadowed.md", contents="from parent")
        fs.create_file("/test/content/shadowed.md", contents="from child")
        fs.create_file(
            "/parent/parent.yml",
            contents=dedent("""
                character_name: Alice
                api_params:
                  model: test/model
            """),
        )
        fs.create_file(
            "/test/context.yml",
            contents=dedent("""
                extends: ../parent/parent.yml
                total_cost: 0
                system_prompt: "{{ load_string('doc.md') }}"
                other_prompt: "{{ load_string('shadowed.md') }}"
            """),
        )
        ctx = Context("/test/context.yml")
        ctx.load()
        assert ctx._data["system_prompt"] == "parent doc"
        assert ctx._data["other_prompt"] == "from child"


class TestTemplateResolution:
    def test_resolves_templates_with_context_vars(self, context):
        assert context._data["system_prompt"] == "You are Alice."

    def test_provides_conversation_vars_to_templates(self, fs):
        fs.create_dir("/test/conversations")
        fs.create_file(
            "/test/context.yml",
            contents=dedent("""
                character_name: Alice
                total_cost: 0
                api_params:
                  model: test/model
                system_prompt: "Mood: {{ vars.mood }}"
            """),
        )
        fs.create_file(
            "/test/context.state.yml",
            contents="conversation_file: file://./conversations/alice_1.yml\n",
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

    def test_provides_model_to_templates(self, fs, base_context_data):
        fs.create_dir("/test/conversations")
        base_context_data["system_prompt"] = "Model: {{ api_params.model }}"
        with open("/test/alice.yml", "w") as f:
            yaml.dump(base_context_data, f)
        ctx = Context("/test/alice.yml")
        assert ctx._data["system_prompt"] == "Model: test/model"


class TestModel:
    def test_extending_context_overrides_model(self, context_fs):  # noqa: ARG002
        with open("/test/base.yml", "w") as f:
            yaml.dump(
                {
                    "character_name": "Alice",
                    "api_params": {"model": "base/model", "temperature": 0.5},
                },
                f,
            )
        with open("/test/child.yml", "w") as f:
            child = {"extends": "base.yml", "api_params": {"model": "child/model"}}
            yaml.dump(child, f)
        ctx = Context("/test/child.yml")
        assert ctx.model == "child/model"
        assert ctx.api_params["temperature"] == 0.5  # Siblings survive the merge

    def test_override_sets_model(self, context_fs):  # noqa: ARG002
        ctx = Context("/test/alice.yml", overrides={"api_params": {"model": "other"}})
        assert ctx.model == "other"


class TestStateFile:
    def test_empty_state_when_no_state_file(self, context):
        # conversation_file is auto-generated by _load_conversation
        assert "total_cost" not in context._state_data

    def test_creates_state_file_on_save(self, context):
        context.increment_cost(1.0)
        context.save()
        with open("/test/alice.state.yml") as f:
            state = yaml.load(f)
        assert state["total_cost"] == 1.0
        assert "conversation_file" in state

    def test_context_file_unchanged_after_save(self, context):
        with open("/test/alice.yml") as f:
            original = f.read()
        context.increment_cost(10.0)
        context.save()
        with open("/test/alice.yml") as f:
            after = f.read()
        assert original == after

    def test_state_owns_conversation_file(self, context):
        context.new_conversation()
        assert context.conversation_file == context._state_data["conversation_file"]

    def test_reads_conversation_file_from_state(self, fs):
        fs.create_dir("/test/conversations")
        with open("/test/alice.yml", "w") as f:
            yaml.dump(
                {"character_name": "Alice", "api_params": {"model": "test/model"}}, f
            )
        with open("/test/alice.state.yml", "w") as f:
            yaml.dump({"conversation_file": "file://./conversations/alice_9.yml"}, f)
        ctx = Context("/test/alice.yml")
        assert ctx.conversation_id == 9

    def test_loads_from_state_file(self, context):
        context.increment_cost(5.0)
        context.save()
        ctx2 = Context("/test/alice.yml")
        ctx2.load()
        assert ctx2._state_data["total_cost"] == 5.0


def configure(context: Context, **data) -> None:
    """Add context data as though the file had declared it."""
    context._unresolved_data.update(data)
    context._rebuild()


class TestWithOverrides:
    def test_override_replaces_value(self, context):
        clone = context.with_overrides({"api_params": {"model": "other/model"}})
        assert clone.model == "other/model"
        assert context.model == "test/model"

    def test_override_merges_into_nested_block(self, context):
        configure(context, post_process={"prompt": "Edit.", "api_params": {"top_p": 1}})
        clone = context.with_overrides(
            {"post_process": {"api_params": {"model": "editor/model"}}}
        )
        assert clone.post_process_prompt == "Edit."
        assert clone.post_process_params["model"] == "editor/model"
        assert clone.post_process_params["top_p"] == 1

    def test_overrides_are_resolved_as_templates(self, context):
        clone = context.with_overrides({"system_prompt": "I am {{ character_name }}."})
        assert clone.resolved_data["system_prompt"] == "I am Alice."

    def test_overrides_apply_before_dependent_templates(self, context):
        clone = context.with_overrides({"character_name": "Bob"})
        assert clone.resolved_data["system_prompt"] == "You are Bob."

    def test_costs_accrue_to_the_original(self, context):
        clone = context.with_overrides({"api_params": {"model": "other/model"}})
        clone.increment_cost(0.25)
        assert context.conversation_cost == 0.25
        assert context._state_data["total_cost"] == 0.25

    def test_conversation_is_shared(self, context):
        clone = context.with_overrides({})
        context.add_message("user", "Hi")
        assert len(clone.conversation_messages) == 1

    def test_preset_overrides_are_kept(self, context):
        configure(
            context,
            instruction_presets={
                "terse": {
                    "content": "Be terse.",
                    "overrides": {"api_params": {"top_p": 1}},
                }
            },
        )
        context.apply_preset_overrides("terse")
        clone = context.with_overrides({"api_params": {"model": "other/model"}})
        assert clone.api_params == {"model": "other/model", "top_p": 1}


class TestPresetOverrides:
    def test_overrides_are_dropped_on_reload(self, context):
        configure(
            context,
            instruction_presets={
                "terse": {
                    "content": "Be terse.",
                    "overrides": {"api_params": {"top_p": 1}},
                }
            },
        )
        context.apply_preset_overrides("terse")
        assert context.api_params["top_p"] == 1
        context.load()
        assert "top_p" not in context.api_params
