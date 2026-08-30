import os
from typing import Any

import pytest

from src.message import Message
from src.trials import Stage, TrialLog, run
from src.yaml_config import yaml

POST_PROCESS = Stage("post_process", scope="post_process")
RESPONSE = Stage("response")


class FakeContext:
    """Substitute for Context that records the overrides it was given."""

    def __init__(self, data: dict[str, Any], overrides: dict[str, Any] | None = None):
        self.resolved_data = data
        self.overrides = overrides or {}

    def with_overrides(self, overrides: dict[str, Any]) -> FakeContext:
        return FakeContext(self.resolved_data, overrides)


@pytest.fixture
def context() -> FakeContext:
    return FakeContext(
        {
            "post_process": {
                "prompt": "Edit.",
                "candidates": [
                    {"api_params": {"model": "one"}},
                    {"api_params": {"model": "two"}},
                    {"prompt": "Edit harder."},
                ],
            }
        }
    )


async def echo_model(context: FakeContext, alias: str | None) -> tuple[str | None, Any]:
    return alias, context.overrides


class TestRun:
    @pytest.mark.asyncio
    async def test_runs_once_without_candidates(self):
        context = FakeContext({})
        trial = await run(context, POST_PROCESS, echo_model)
        assert trial.selected is None
        assert trial.outputs == {}
        assert trial.result == (None, {})

    @pytest.mark.asyncio
    async def test_an_untried_stage_still_reports_its_lone_candidate(self):
        trial = await run(FakeContext({}), POST_PROCESS, echo_model)
        assert trial.candidates == {"A": trial.result}

    @pytest.mark.asyncio
    async def test_root_scoped_candidates_override_the_whole_context(self):
        context = FakeContext(
            {"candidates": [{"api_params": {"model": "one"}}, {"system_prompt": "Hi"}]}
        )
        trial = await run(context, RESPONSE, echo_model)
        assert trial.outputs["A"][1] == {"api_params": {"model": "one"}}
        assert trial.outputs["B"][1] == {"system_prompt": "Hi"}

    @pytest.mark.asyncio
    async def test_assigns_aliases_by_position(self, context):
        trial = await run(context, POST_PROCESS, echo_model)
        assert list(trial.outputs) == ["A", "B", "C"]
        assert trial.outputs["B"][1] == {
            "post_process": {"api_params": {"model": "two"}}
        }

    @pytest.mark.asyncio
    async def test_selects_a_candidate(self, context, monkeypatch):
        monkeypatch.setattr("src.trials.runner.random.choice", lambda _: "C")
        trial = await run(context, POST_PROCESS, echo_model)
        assert trial.selected == "C"
        assert trial.result is trial.outputs["C"]

    @pytest.mark.asyncio
    async def test_candidates_key_is_not_passed_through(self, context):
        context.resolved_data["post_process"]["candidates"][0]["candidates"] = ["x"]
        trial = await run(context, POST_PROCESS, echo_model)
        assert "candidates" not in trial.outputs["A"][1]["post_process"]

    @pytest.mark.asyncio
    async def test_a_failing_candidate_fails_the_trial(self, context):
        async def execute(_: FakeContext, alias: str | None):
            if alias == "B":
                raise ValueError("bad edit")
            return alias

        with pytest.raises(ValueError, match="bad edit"):
            await run(context, POST_PROCESS, execute)


class TestStage:
    def test_request_key_is_the_name_without_an_alias(self):
        assert RESPONSE.request_key(None) == "response"

    def test_request_key_is_suffixed_by_the_alias(self):
        assert POST_PROCESS.request_key("B") == "post_process_B"


class FakeLogContext:
    is_ephemeral = False
    context_name = "alice"
    conversation_id = 4
    trials_dir = "/test/trials"

    def __init__(self, messages: list[Message]):
        self.conversation_messages = messages


def record(trial_id: int, content: str) -> dict[str, Any]:
    return {
        "id": trial_id,
        "draft": "draft text",
        "selected": "A",
        "candidates": {"A": {"content": content}},
    }


def read_log() -> dict[str, Any]:
    with open("/test/trials/alice_4.yml") as file:
        return yaml.load(file)


class TestTrialLog:
    @pytest.fixture
    def messages(self) -> list[Message]:
        return [
            Message("user", "Hi"),
            Message("assistant", "Edited", metadata={"trial": 1}),
        ]

    def test_writes_the_conversation_with_candidates(self, fs, messages):  # noqa: ARG002
        TrialLog(FakeLogContext(messages)).write(record(1, "Edited"))
        data = read_log()
        assert data["conversation_id"] == 4
        assert data["messages"][0] == {"role": "user", "content": "Hi"}
        assert data["messages"][1]["trial"]["selected"] == "A"

    def test_omits_content_on_trial_turns(self, fs, messages):  # noqa: ARG002
        TrialLog(FakeLogContext(messages)).write(record(1, "Edited"))
        assert "content" not in read_log()["messages"][1]

    def test_next_id_follows_the_highest_recorded(self, fs, messages):  # noqa: ARG002
        log = TrialLog(FakeLogContext(messages))
        assert log.next_id() == 1
        log.write(record(1, "Edited"))
        assert log.next_id() == 2

    def test_drops_records_no_longer_in_the_conversation(self, fs, messages):  # noqa: ARG002
        context = FakeLogContext(messages)
        log = TrialLog(context)
        log.write(record(1, "Edited"))
        context.conversation_messages = [Message("user", "Hi")]
        log.write()
        assert read_log()["messages"] == [{"role": "user", "content": "Hi"}]

    def test_carries_earlier_records_forward(self, fs, messages):  # noqa: ARG002
        context = FakeLogContext(messages)
        log = TrialLog(context)
        log.write(record(1, "First"))
        context.conversation_messages = [
            *messages,
            Message("user", "More"),
            Message("assistant", "Second", metadata={"trial": 2}),
        ]
        log.write(record(2, "Second"))
        entries = read_log()["messages"]
        assert entries[1]["trial"]["candidates"]["A"]["content"] == "First"
        assert entries[3]["trial"]["candidates"]["A"]["content"] == "Second"

    def test_does_nothing_without_a_record_or_existing_log(self, fs, messages):  # noqa: ARG002
        TrialLog(FakeLogContext(messages)).write()
        assert not os.path.exists("/test/trials")

    def test_skips_ephemeral_contexts(self, fs, messages):  # noqa: ARG002
        context = FakeLogContext(messages)
        context.is_ephemeral = True
        TrialLog(context).write(record(1, "Edited"))
        assert not os.path.exists("/test/trials")
