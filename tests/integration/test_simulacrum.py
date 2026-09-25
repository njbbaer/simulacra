# ruff: noqa: ASYNC230
import copy
import json
import os
from typing import Any

import pytest
from ruamel.yaml import YAML

from src.simulacrum import Simulacrum


@pytest.mark.asyncio
async def test_models_recorded_in_conversation_header(
    post_process_simulacrum: Simulacrum,
    mock_edited_response,  # noqa: ARG001
) -> None:
    await post_process_simulacrum.chat("Hello assistant", None, None)

    with open("conversations/test_0.yml") as f:
        data = YAML(typ="safe").load(f)
    assert data["models"] == {
        "response": "anthropic/claude",
        "post_process": "test/editor",
    }
    assert "models" not in data["messages"][-1].get("metadata", {})


@pytest.mark.asyncio
async def test_simulacrum_chat(
    simulacrum: Simulacrum,
    mock_openrouter,
    context_data: dict[str, Any],
    state_data: dict[str, Any],
    conversation_data: dict[str, Any],
) -> None:
    initial_conversation_cost = conversation_data["cost"]
    initial_message_count = len(conversation_data["messages"])
    user_message = "Hello assistant"

    await simulacrum.chat(user_message, None, None)

    request = mock_openrouter.get_requests(
        url="https://openrouter.ai/api/v1/chat/completions",
    )[0]
    actual_body = json.loads(request.content)

    assert request.headers["HTTP-Referer"] == "https://github.com/njbbaer/simulacra"
    assert request.headers["X-OpenRouter-Title"] == "Simulacra"

    # Verify API request contains all context api_params
    assert all(
        key in actual_body and actual_body[key] == value
        for key, value in context_data["api_params"].items()
    )

    # Check the messages structure
    assert len(actual_body["messages"]) == 3
    assert actual_body["messages"][0]["role"] == "system"
    assert (
        actual_body["messages"][0]["content"][0]["text"]
        == context_data["system_prompt"]
    )

    assert actual_body["messages"][1]["role"] == "assistant"
    assert (
        actual_body["messages"][1]["content"][0]["text"]
        == conversation_data["messages"][0]["content"]
    )

    assert actual_body["messages"][2]["role"] == "user"
    assert actual_body["messages"][2]["content"][0]["text"] == user_message

    # Verify contents of the state file
    with open("test.state.yml") as f:
        saved_state = YAML(typ="safe").load(f)
        assert saved_state["conversation_file"] == state_data["conversation_file"]
        assert saved_state["total_cost"] > 0

    # Verify contents of the conversation file
    with open("conversations/test_0.yml") as f:
        content = f.read()
        new_conversation_data = YAML(typ="safe").load(content)
        assert new_conversation_data["cost"] > initial_conversation_cost
        assert len(new_conversation_data["messages"]) == initial_message_count + 2

        # Verify the last two messages
        assert new_conversation_data["messages"][-2]["role"] == "user"
        assert new_conversation_data["messages"][-2]["content"] == user_message
        assert new_conversation_data["messages"][-1]["role"] == "assistant"
        assert new_conversation_data["messages"][-1]["content"] == "Something"


def test_compact_conversation(simulacrum: Simulacrum) -> None:
    simulacrum.compact_conversation()

    # Conversation compacted into a single memory
    assert len(simulacrum.context.conversation.messages) == 0
    memories = simulacrum.context.conversation.memories
    assert len(memories) == 1


@pytest.mark.asyncio
async def test_new_conversation(simulacrum: Simulacrum) -> None:
    await simulacrum.new_conversation()

    # Verify state file updates
    with open("test.state.yml") as f:
        state_data = YAML(typ="safe").load(f)
        assert state_data["conversation_file"] == "file://./conversations/test_1.yml"

    # Verify contents of the new conversation file
    new_conversation_path = "conversations/test_1.yml"
    assert os.path.exists(new_conversation_path)  # noqa: ASYNC240
    with open(new_conversation_path) as f:
        content = f.read()
        new_conversation_data = YAML(typ="safe").load(content)
        assert new_conversation_data["cost"] == 0.0
        assert isinstance(new_conversation_data["messages"], list)
        assert len(new_conversation_data["messages"]) == 0


@pytest.mark.asyncio
async def test_retry(
    simulacrum: Simulacrum,
    mock_openrouter,  # noqa: ARG001
) -> None:
    response = await simulacrum.retry()

    assert response == "Something"
    msgs = simulacrum.context.conversation.messages
    assert len(msgs) == 1
    assert msgs[0].role == "assistant"
    assert msgs[0].content == "Something"
    assert msgs[0].metadata["replaced"] == [
        {"role": "assistant", "content": "Hello user"}
    ]


@pytest.mark.asyncio
async def test_retry_detects_scene_message(
    simulacrum: Simulacrum,
    mock_openrouter,  # noqa: ARG001
) -> None:
    # Replace the existing assistant message with a scene message
    simulacrum.context.load()
    simulacrum.context.conversation.messages.clear()
    simulacrum.context.conversation.add_message(
        "user", "A dark room.", metadata={"scene": True, "scene_input": "darkness"}
    )
    simulacrum.context.save()

    response = await simulacrum.retry()

    assert response == "Something"
    # Verify the scene message was replaced (not an assistant message added)
    msgs = simulacrum.context.conversation.messages
    assert len(msgs) == 1
    assert msgs[0].role == "user"
    metadata = msgs[0].metadata
    assert metadata is not None
    assert metadata["scene"] is True
    assert metadata["scene_input"] == "darkness"
    assert metadata["replaced"][0]["content"] == "A dark room."


@pytest.mark.asyncio
async def test_undo_retry_restores_a_retried_scene(
    simulacrum: Simulacrum,
    mock_openrouter,  # noqa: ARG001
) -> None:
    simulacrum.context.load()
    simulacrum.context.conversation.add_message(
        "user", "A dark room.", metadata={"scene": True, "scene_input": "darkness"}
    )
    simulacrum.context.save()

    await simulacrum.retry()
    simulacrum.undo_retry()

    simulacrum.context.load()
    assert [m.content for m in simulacrum.context.conversation.messages] == [
        "Hello user",
        "A dark room.",
    ]


@pytest.mark.asyncio
async def test_continue_conversation(
    simulacrum: Simulacrum,
    mock_openrouter,
) -> None:
    response = await simulacrum.continue_conversation()

    assert response == "Something"

    # Verify the API request included the continue prompt
    request = mock_openrouter.get_requests(
        url="https://openrouter.ai/api/v1/chat/completions",
    )[0]
    body = json.loads(request.content)
    messages = body["messages"]
    assert messages[-1]["role"] == "system"
    assert "<instruct>Continue</instruct>" in messages[-1]["content"][0]["text"]

    # Verify the temp message is not persisted
    msgs = simulacrum.context.conversation.messages
    assert len(msgs) == 2
    assert msgs[0].role == "assistant"
    assert msgs[1].role == "assistant"


def test_reset_conversation(
    simulacrum: Simulacrum,
    state_data: dict[str, Any],
) -> None:
    simulacrum.reset_conversation()

    # Verify conversation file doesn't change
    with open("test.state.yml") as f:
        saved_state = YAML(typ="safe").load(f)
        assert saved_state["conversation_file"] == state_data["conversation_file"]

    # Verify conversation file was reset
    with open("conversations/test_0.yml") as f:
        new_conversation_data = YAML(typ="safe").load(f)
        assert new_conversation_data["cost"] == 0.0
        assert len(new_conversation_data["messages"]) == 0


@pytest.mark.asyncio
async def test_retried_turn_drops_out_of_the_trial_log(
    trial_simulacrum: Simulacrum,
    mock_candidate_responses,  # noqa: ARG001
    read_trial_log,
) -> None:
    await trial_simulacrum.chat("Hello assistant", None, None)
    assert "trial" in read_trial_log()["messages"][2]

    trial_simulacrum.undo()

    assert read_trial_log()["messages"] == [
        {"role": "assistant", "content": "Hello user"}
    ]


@pytest.mark.asyncio
async def test_retried_trial_is_kept_until_the_retry_is_undone(
    trial_simulacrum: Simulacrum,
    mock_candidate_responses,
    mock_completion_response: dict[str, Any],
    read_trial_log,
) -> None:
    await trial_simulacrum.chat("Hello assistant", None, None)
    first = read_trial_log()["messages"][2]
    for text in ["Something", "Third edit", "Fourth edit"]:
        response = copy.deepcopy(mock_completion_response)
        response["choices"][0]["message"]["content"] = text
        mock_candidate_responses.add_response(
            url="https://openrouter.ai/api/v1/chat/completions", json=response
        )

    await trial_simulacrum.retry()

    retried = read_trial_log()["messages"][2]
    assert retried["trial"]["id"] == first["trial"]["id"] + 1
    assert retried["replaced"] == [first]

    trial_simulacrum.undo_retry()

    assert read_trial_log()["messages"][2] == first


@pytest.mark.asyncio
async def test_reset_conversation_deletes_the_trial_log(
    trial_simulacrum: Simulacrum,
    mock_candidate_responses,  # noqa: ARG001
) -> None:
    await trial_simulacrum.chat("Hello assistant", None, None)
    assert os.path.exists("trials/test_0.yml")  # noqa: ASYNC240

    trial_simulacrum.reset_conversation()

    assert not os.path.exists("trials/test_0.yml")  # noqa: ASYNC240
