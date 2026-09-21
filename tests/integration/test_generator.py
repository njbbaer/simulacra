# ruff: noqa: ASYNC230
import copy
import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from ruamel.yaml import YAML

from src.request_recorder import RequestRecorder
from src.simulacrum import Simulacrum
from src.yaml_config import yaml


@pytest.mark.asyncio
async def test_post_process_replaces_response(
    post_process_simulacrum: Simulacrum,
    mock_edited_response,
) -> None:
    response = await post_process_simulacrum.chat("Hello assistant", None, None)

    assert response == "Edited"
    message = post_process_simulacrum.context.conversation.messages[-1]
    assert message.content == "Edited"
    assert message.metadata["draft"] == "Something"

    # The second request repeats the first, with the draft and prompt appended
    requests = mock_edited_response.get_requests()
    assert len(requests) == 2
    body = json.loads(requests[1].content)
    assert body["model"] == "test/editor"
    assert body["messages"][-2]["role"] == "assistant"
    assert body["messages"][-2]["content"][0]["text"] == "<draft>\nSomething\n</draft>"
    # A trailing user message keeps the draft from being treated as a prefill
    assert body["messages"][-1]["role"] == "user"
    assert (
        body["messages"][-1]["content"][0]["text"]
        == "<instruct>\nRevise the draft.\n</instruct>"
    )


@pytest.mark.asyncio
async def test_post_process_extracts_editor_notes(
    post_process_simulacrum: Simulacrum,
    mock_openrouter,
    mock_completion_response: dict[str, Any],
) -> None:
    edited = copy.deepcopy(mock_completion_response)
    edited["choices"][0]["message"]["content"] = (
        "<assessment>\nCut the hedge in the last line.\n</assessment>\n\nEdited"
    )
    mock_openrouter.add_response(
        url="https://openrouter.ai/api/v1/chat/completions",
        json=edited,
    )

    response = await post_process_simulacrum.chat("Hello assistant", None, None)

    assert response == "Edited"
    message = post_process_simulacrum.context.conversation.messages[-1]
    assert message.content == "Edited"
    assert message.metadata["draft"] == "Something"
    assert message.metadata["editor_notes"] == "Cut the hedge in the last line."


@pytest.fixture
def strict_post_process_simulacrum(
    post_process_simulacrum: Simulacrum,
    context_data: dict[str, Any],
) -> Simulacrum:
    context_data["require_tags"] = ["thinking"]
    with open("test.yml", "w") as f:
        yaml.dump(context_data, f)
    return post_process_simulacrum


@pytest.fixture
def mock_tagged_draft(mock_openrouter, mock_completion_response: dict[str, Any]):
    draft = copy.deepcopy(mock_completion_response)
    draft["choices"][0]["message"]["content"] = "<thinking>hm</thinking>\nSomething"
    mock_openrouter.reset()
    mock_openrouter.add_response(
        url="https://openrouter.ai/api/v1/chat/completions",
        json=draft,
    )
    return mock_openrouter


@pytest.mark.asyncio
async def test_post_process_accepts_expected_format(
    strict_post_process_simulacrum: Simulacrum,
    mock_tagged_draft,
    mock_completion_response: dict[str, Any],
) -> None:
    edited = copy.deepcopy(mock_completion_response)
    edited["choices"][0]["message"]["content"] = (
        "<assessment>\nNotes\n</assessment>\n<thinking>hm</thinking>\nEdited"
    )
    mock_tagged_draft.add_response(
        url="https://openrouter.ai/api/v1/chat/completions",
        json=edited,
    )

    response = await strict_post_process_simulacrum.chat("Hello assistant", None, None)

    assert response == "Edited"
    message = strict_post_process_simulacrum.context.conversation.messages[-1]
    assert message.metadata["editor_notes"] == "Notes"


@pytest.mark.asyncio
async def test_post_process_logs_both_requests(
    post_process_simulacrum: Simulacrum,
    mock_edited_response,  # noqa: ARG001
) -> None:
    await post_process_simulacrum.chat("Hello assistant", None, None)

    with open(RequestRecorder.FILEPATH) as f:
        log = YAML(typ="safe").load(f)
    assert list(log) == ["response", "post_process"]
    edited = log["post_process"]["response"]["choices"][0]["message"]["content"]
    assert edited == "Edited"


@pytest.mark.asyncio
async def test_post_process_skipped_for_scene(
    post_process_simulacrum: Simulacrum,
    mock_openrouter,
) -> None:
    response = await post_process_simulacrum.scene()

    assert response == "Something"
    assert len(mock_openrouter.get_requests()) == 1


@pytest.mark.asyncio
async def test_trial_accepts_one_candidate(
    trial_simulacrum: Simulacrum,
    mock_candidate_responses,  # noqa: ARG001
    monkeypatch,
) -> None:
    monkeypatch.setattr("src.trials.runner.random.choice", lambda aliases: aliases[1])

    response = await trial_simulacrum.chat("Hello assistant", None, None)

    assert response == "Second edit"
    message = trial_simulacrum.context.conversation.messages[-1]
    assert message.content == "Second edit"
    assert message.metadata["trial"] == 1
    assert "candidates" not in message.metadata


@pytest.mark.asyncio
async def test_trial_marks_selected_model_only_when_it_changes(
    trial_simulacrum: Simulacrum,
    mock_candidate_responses,
    mock_completion_response: dict[str, Any],
    monkeypatch,
) -> None:
    monkeypatch.setattr("src.trials.runner.random.choice", lambda aliases: aliases[0])
    await trial_simulacrum.chat("Hello assistant", None, None)
    conversation = trial_simulacrum.context.conversation
    assert conversation.models == {
        "response": "anthropic/claude",
        "post_process": "test/editor-one",
    }
    assert "models" not in conversation.messages[-1].metadata

    for _ in range(3):
        mock_candidate_responses.add_response(
            url="https://openrouter.ai/api/v1/chat/completions",
            json=mock_completion_response,
        )
    monkeypatch.setattr("src.trials.runner.random.choice", lambda aliases: aliases[1])
    await trial_simulacrum.chat("Again", None, None)
    message = trial_simulacrum.context.conversation.messages[-1]
    assert message.metadata["models"] == {"post_process": "test/editor"}


@pytest.mark.asyncio
async def test_trial_logs_every_candidate(
    trial_simulacrum: Simulacrum,
    mock_candidate_responses,  # noqa: ARG001
    monkeypatch,
    read_trial_log,
) -> None:
    monkeypatch.setattr("src.trials.runner.random.choice", lambda aliases: aliases[0])

    await trial_simulacrum.chat("Hello assistant", None, None)

    log = read_trial_log()
    assert log["messages"][0] == {"role": "assistant", "content": "Hello user"}
    assert log["messages"][1] == {"role": "user", "content": "Hello assistant"}
    trial = log["messages"][2]["trial"]
    assert "content" not in log["messages"][2]
    assert trial["response"] == {"content": "Something"}
    assert trial["post_process"]["selected"] == "A"
    assert trial["post_process"]["candidates"]["A"]["content"] == "First edit"
    assert trial["post_process"]["candidates"]["B"]["content"] == "Second edit"


@pytest.mark.asyncio
async def test_trial_applies_candidate_overrides(
    trial_simulacrum: Simulacrum,
    mock_candidate_responses,
    monkeypatch,
) -> None:
    monkeypatch.setattr("src.trials.runner.random.choice", lambda aliases: aliases[0])

    await trial_simulacrum.chat("Hello assistant", None, None)

    requests = mock_candidate_responses.get_requests()
    first, second = (json.loads(r.content) for r in requests[1:])
    assert first["model"] == "test/editor-one"
    assert second["model"] == "test/editor"
    assert "harder" in second["messages"][-1]["content"][0]["text"]


@pytest.mark.asyncio
async def test_trial_costs_are_summed(
    trial_simulacrum: Simulacrum,
    mock_candidate_responses,  # noqa: ARG001
) -> None:
    await trial_simulacrum.chat("Hello assistant", None, None)

    assert trial_simulacrum.last_message_cost == pytest.approx(0.3)


@pytest.fixture
def response_trial_simulacrum(
    simulacrum: Simulacrum,
    context_data: dict[str, Any],
) -> Simulacrum:
    context_data["candidates"] = [
        {"api_params": {"model": "test/one"}},
        {"api_params": {"model": "test/two"}},
    ]
    with open("test.yml", "w") as f:
        yaml.dump(context_data, f)
    return simulacrum


@pytest.fixture
def mock_response_candidates(
    mock_openrouter,
    mock_completion_response: dict[str, Any],
):
    alternative = copy.deepcopy(mock_completion_response)
    alternative["choices"][0]["message"]["content"] = "Something else"
    mock_openrouter.add_response(
        url="https://openrouter.ai/api/v1/chat/completions",
        json=alternative,
    )
    return mock_openrouter


@pytest.mark.asyncio
async def test_response_trial_accepts_one_candidate(
    response_trial_simulacrum: Simulacrum,
    mock_response_candidates,  # noqa: ARG001
    monkeypatch,
) -> None:
    monkeypatch.setattr("src.trials.runner.random.choice", lambda aliases: aliases[1])

    response = await response_trial_simulacrum.chat("Hello assistant", None, None)

    assert response == "Something else"
    message = response_trial_simulacrum.context.conversation.messages[-1]
    assert message.content == "Something else"
    assert message.metadata == {"trial": 1}


@pytest.mark.asyncio
async def test_response_trial_applies_candidate_overrides(
    response_trial_simulacrum: Simulacrum,
    mock_response_candidates,
    monkeypatch,
) -> None:
    monkeypatch.setattr("src.trials.runner.random.choice", lambda aliases: aliases[0])

    await response_trial_simulacrum.chat("Hello assistant", None, None)

    first, second = (
        json.loads(r.content) for r in mock_response_candidates.get_requests()
    )
    assert first["model"] == "test/one"
    assert second["model"] == "test/two"


@pytest.mark.asyncio
async def test_response_trial_logs_each_candidate_request(
    response_trial_simulacrum: Simulacrum,
    mock_response_candidates,  # noqa: ARG001
    monkeypatch,
) -> None:
    monkeypatch.setattr("src.trials.runner.random.choice", lambda aliases: aliases[0])

    await response_trial_simulacrum.chat("Hello assistant", None, None)

    with open(RequestRecorder.FILEPATH) as f:
        log = YAML(typ="safe").load(f)
    assert sorted(log) == ["response_A", "response_B"]


@pytest.mark.asyncio
async def test_response_trial_costs_are_summed(
    response_trial_simulacrum: Simulacrum,
    mock_response_candidates,  # noqa: ARG001
) -> None:
    await response_trial_simulacrum.chat("Hello assistant", None, None)

    assert response_trial_simulacrum.last_message_cost == pytest.approx(0.2)


@pytest.fixture
def chained_trial_simulacrum(
    response_trial_simulacrum: Simulacrum,
    context_data: dict[str, Any],
) -> Simulacrum:
    context_data["post_process"] = {
        "prompt": "Revise the draft.",
        "api_params": {"model": "test/editor"},
        "candidates": [{"prompt": "Revise."}, {"prompt": "Revise harder."}],
    }
    with open("test.yml", "w") as f:
        yaml.dump(context_data, f)
    return response_trial_simulacrum


@pytest.fixture
def mock_chained_responses(
    mock_response_candidates,
    mock_completion_response: dict[str, Any],
):
    for text in ["First edit", "Second edit"]:
        edited = copy.deepcopy(mock_completion_response)
        edited["choices"][0]["message"]["content"] = text
        mock_response_candidates.add_response(
            url="https://openrouter.ai/api/v1/chat/completions",
            json=edited,
        )
    return mock_response_candidates


@pytest.mark.asyncio
async def test_chained_trials_post_process_only_the_selected_response(
    chained_trial_simulacrum: Simulacrum,
    mock_chained_responses,
    monkeypatch,
) -> None:
    monkeypatch.setattr("src.trials.runner.random.choice", lambda aliases: aliases[0])

    response = await chained_trial_simulacrum.chat("Hello assistant", None, None)

    assert response == "First edit"
    requests = mock_chained_responses.get_requests()
    assert len(requests) == 4
    drafted = json.loads(requests[2].content)["messages"][-2]["content"][0]["text"]
    assert drafted == "<draft>\nSomething\n</draft>"


@pytest.mark.asyncio
async def test_chained_trials_are_logged_stage_by_stage(
    chained_trial_simulacrum: Simulacrum,
    mock_chained_responses,  # noqa: ARG001
    monkeypatch,
    read_trial_log,
) -> None:
    monkeypatch.setattr("src.trials.runner.random.choice", lambda aliases: aliases[0])

    await chained_trial_simulacrum.chat("Hello assistant", None, None)

    trial = read_trial_log()["messages"][2]["trial"]
    assert trial["response"]["selected"] == "A"
    assert list(trial["response"]["candidates"]) == ["A", "B"]
    assert trial["post_process"]["selected"] == "A"
    assert list(trial["post_process"]["candidates"]) == ["A", "B"]


@pytest.mark.asyncio
async def test_post_processing_inherits_the_selected_candidate_context(
    simulacrum: Simulacrum,
    context_data: dict[str, Any],
    mock_response_candidates,
    mock_completion_response: dict[str, Any],
    monkeypatch,
) -> None:
    context_data["candidates"] = [
        {"post_process": {"api_params": {"model": "test/editor-one"}}},
        {"post_process": {"api_params": {"model": "test/editor-two"}}},
    ]
    context_data["post_process"] = {"prompt": "Revise the draft."}
    with open("test.yml", "w") as f:
        yaml.dump(context_data, f)
    mock_response_candidates.add_response(
        url="https://openrouter.ai/api/v1/chat/completions",
        json=mock_completion_response,
    )
    monkeypatch.setattr("src.trials.runner.random.choice", lambda aliases: aliases[1])

    await simulacrum.chat("Hello assistant", None, None)

    requests = mock_response_candidates.get_requests()
    assert len(requests) == 3
    assert json.loads(requests[2].content)["model"] == "test/editor-two"


@pytest.fixture
def drafts_simulacrum(
    simulacrum: Simulacrum,
    context_data: dict[str, Any],
) -> Simulacrum:
    context_data["post_process"] = {
        "prompt": "Revise the drafts.",
        "drafts": 2,
        "api_params": {"model": "test/editor"},
    }
    with open("test.yml", "w") as f:
        yaml.dump(context_data, f)
    return simulacrum


@pytest.fixture
def mock_two_drafts(
    httpx_mock,
    mock_completion_response: dict[str, Any],
):
    for text in ["Draft one", "Draft two", "Edited"]:
        response = copy.deepcopy(mock_completion_response)
        response["choices"][0]["message"]["content"] = text
        httpx_mock.add_response(
            url="https://openrouter.ai/api/v1/chat/completions",
            json=response,
        )
    return httpx_mock


@pytest.mark.asyncio
async def test_drafts_are_requested_separately(
    drafts_simulacrum: Simulacrum,
    mock_two_drafts,
) -> None:
    response = await drafts_simulacrum.chat("Hello assistant", None, None)

    assert response == "Edited"
    requests = mock_two_drafts.get_requests()
    assert len(requests) == 3
    first, second = (json.loads(r.content)["messages"] for r in requests[:2])
    assert first == second
    with open(RequestRecorder.FILEPATH) as f:
        log = YAML(typ="safe").load(f)
    assert sorted(log) == ["post_process", "response_1", "response_2"]


@pytest.mark.asyncio
async def test_later_drafts_wait_for_the_cache_unless_it_is_warm(
    drafts_simulacrum: Simulacrum,
    httpx_mock,
    mock_completion_response: dict[str, Any],
    monkeypatch,
) -> None:
    for _ in range(9):
        httpx_mock.add_response(
            url="https://openrouter.ai/api/v1/chat/completions",
            json=mock_completion_response,
        )
    clock = {"now": 0.0}
    monkeypatch.setattr("src.generator.time.monotonic", lambda: clock["now"])
    monkeypatch.setattr("src.generator.CACHE_WRITE_SECONDS", 2.0)

    with patch("src.generator.asyncio.sleep", new_callable=AsyncMock) as sleep:
        await drafts_simulacrum.chat("Hello assistant", None, None)
        clock["now"] = 60
        await drafts_simulacrum.chat("Hello again", None, None)
        clock["now"] = 60 + 16 * 60
        await drafts_simulacrum.chat("Hello once more", None, None)

    delays = [call.args[0] for call in sleep.call_args_list]
    assert delays == [0.0, 2.0, 0.0, 0.0, 0.0, 2.0]


@pytest.mark.asyncio
async def test_editor_receives_every_draft_in_one_message(
    drafts_simulacrum: Simulacrum,
    mock_two_drafts,
) -> None:
    await drafts_simulacrum.chat("Hello assistant", None, None)

    body = json.loads(mock_two_drafts.get_requests()[2].content)
    assert body["model"] == "test/editor"
    assert body["messages"][-2]["role"] == "assistant"
    assert body["messages"][-2]["content"][0]["text"] == (
        "<draft_1>\nDraft one\n</draft_1>\n\n<draft_2>\nDraft two\n</draft_2>"
    )
    assert body["messages"][-1]["role"] == "user"


@pytest.mark.asyncio
async def test_drafts_are_stored_in_metadata(
    drafts_simulacrum: Simulacrum,
    mock_two_drafts,  # noqa: ARG001
) -> None:
    await drafts_simulacrum.chat("Hello assistant", None, None)

    message = drafts_simulacrum.context.conversation.messages[-1]
    assert message.content == "Edited"
    assert message.metadata == {"drafts": ["Draft one", "Draft two"]}


@pytest.mark.asyncio
async def test_draft_costs_are_summed(
    drafts_simulacrum: Simulacrum,
    mock_two_drafts,  # noqa: ARG001
) -> None:
    await drafts_simulacrum.chat("Hello assistant", None, None)

    assert drafts_simulacrum.last_message_cost == pytest.approx(0.3)


@pytest.mark.asyncio
async def test_one_draft_without_post_processing(
    drafts_simulacrum: Simulacrum,
    context_data: dict[str, Any],
    mock_openrouter,
) -> None:
    del context_data["post_process"]["prompt"]
    with open("test.yml", "w") as f:
        yaml.dump(context_data, f)

    response = await drafts_simulacrum.chat("Hello assistant", None, None)

    assert response == "Something"
    assert len(mock_openrouter.get_requests()) == 1
    assert drafts_simulacrum.context.conversation.messages[-1].metadata == {}


@pytest.mark.asyncio
async def test_one_draft_for_scene(
    drafts_simulacrum: Simulacrum,
    mock_openrouter,
) -> None:
    response = await drafts_simulacrum.scene()

    assert response == "Something"
    assert len(mock_openrouter.get_requests()) == 1


@pytest.mark.asyncio
async def test_response_trial_drafts_every_candidate(
    drafts_simulacrum: Simulacrum,
    context_data: dict[str, Any],
    httpx_mock,
    mock_completion_response: dict[str, Any],
    monkeypatch,
    read_trial_log,
) -> None:
    context_data["candidates"] = [
        {"api_params": {"model": "test/one"}},
        {"api_params": {"model": "test/two"}},
    ]
    with open("test.yml", "w") as f:
        yaml.dump(context_data, f)
    for text in ["A one", "A two", "B one", "B two", "Edited"]:
        response = copy.deepcopy(mock_completion_response)
        response["choices"][0]["message"]["content"] = text
        httpx_mock.add_response(
            url="https://openrouter.ai/api/v1/chat/completions",
            json=response,
        )
    monkeypatch.setattr("src.trials.runner.random.choice", lambda aliases: aliases[1])

    await drafts_simulacrum.chat("Hello assistant", None, None)

    requests = httpx_mock.get_requests()
    assert len(requests) == 5
    assert [json.loads(r.content)["model"] for r in requests[:4]] == [
        "test/one",
        "test/one",
        "test/two",
        "test/two",
    ]
    drafted = json.loads(requests[4].content)["messages"][-2]["content"][0]["text"]
    assert drafted == "<draft_1>\nB one\n</draft_1>\n\n<draft_2>\nB two\n</draft_2>"
    with open(RequestRecorder.FILEPATH) as f:
        log = YAML(typ="safe").load(f)
    assert sorted(log) == [
        "post_process",
        "response_A_1",
        "response_A_2",
        "response_B_1",
        "response_B_2",
    ]
    trial = read_trial_log()["messages"][2]["trial"]
    assert trial["response"]["selected"] == "B"
    assert trial["response"]["candidates"]["B"] == {"drafts": ["B one", "B two"]}
    message = drafts_simulacrum.context.conversation.messages[-1]
    assert message.metadata == {"trial": 1, "drafts": ["B one", "B two"]}
