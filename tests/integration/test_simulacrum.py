# ruff: noqa: ASYNC230
import json
import os
from typing import Any

import pytest
from ruamel.yaml import YAML

from src.simulacrum import Simulacrum
from src.yaml_config import yaml


@pytest.fixture
def custom_fs(fs):
    fs.add_real_file("src/lm_executors/chat_executor_template.j2")
    return fs


@pytest.fixture
def context_data() -> dict[str, Any]:
    return {
        "character_name": "test",
        "conversation_file": "file://./conversations/test_0.yml",
        "total_cost": 0.1,
        "pricing": [1, 2],
        "api_params": {"model": "anthropic/claude"},
        "system_prompt": "Say something!",
        "scene_instructions": "Describe the scene.",
        "continue_prompt": "Continue",
    }


@pytest.fixture
def conversation_data() -> dict[str, Any]:
    return {
        "cost": 0.1,
        "facts": [],
        "messages": [
            {
                "role": "assistant",
                "content": "Hello user",
            },
        ],
    }


@pytest.fixture
def simulacrum_context(
    custom_fs,  # noqa: ARG001
    context_data: dict[str, Any],
    conversation_data: dict[str, Any],
) -> None:
    with open("context.yml", "w") as f:
        yaml.dump(context_data, f)
    os.makedirs("conversations", exist_ok=True)
    with open("conversations/test_0.yml", "w") as f:
        yaml.dump(conversation_data, f)


@pytest.fixture
def simulacrum(simulacrum_context) -> Simulacrum:  # noqa: ARG001
    return Simulacrum("context.yml")


@pytest.fixture
def mock_completion_response() -> dict[str, Any]:
    return {
        "id": "gen-test",
        "choices": [
            {
                "message": {
                    "content": "Something",
                },
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "cost": 0.1,
            "prompt_tokens_details": {"cached_tokens": 0},
        },
    }


@pytest.fixture
def mock_openrouter(
    httpx_mock,
    mock_completion_response: dict[str, Any],
):
    httpx_mock.add_response(
        url="https://openrouter.ai/api/v1/chat/completions",
        json=mock_completion_response,
    )
    return httpx_mock


@pytest.mark.asyncio
async def test_simulacrum_chat(
    simulacrum: Simulacrum,
    mock_openrouter,
    context_data: dict[str, Any],
    conversation_data: dict[str, Any],
) -> None:
    initial_context_cost = context_data["total_cost"]
    initial_conversation_cost = conversation_data["cost"]
    initial_message_count = len(conversation_data["messages"])
    user_message = "Hello assistant"

    await simulacrum.chat(user_message, None, None)

    request = mock_openrouter.get_requests(
        url="https://openrouter.ai/api/v1/chat/completions",
    )[0]
    actual_body = json.loads(request.content)

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

    # Verify contents of the context file
    with open("context.yml") as f:
        content = f.read()
        new_context_data = YAML(typ="safe").load(content)
        assert (
            new_context_data["conversation_file"] == context_data["conversation_file"]
        )
        assert new_context_data["total_cost"] > initial_context_cost

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


@pytest.mark.asyncio
async def test_new_conversation(
    simulacrum: Simulacrum, context_data: dict[str, Any]
) -> None:
    await simulacrum.new_conversation()

    # Verify context file updates
    with open("context.yml") as f:
        content = f.read()
        new_context_data = YAML(typ="safe").load(content)
        assert (
            new_context_data["conversation_file"] == "file://./conversations/test_1.yml"
        )
        assert new_context_data["total_cost"] == context_data["total_cost"]

    # Verify contents of the new conversation file
    new_conversation_path = "conversations/test_1.yml"
    assert os.path.exists(new_conversation_path)
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
    msgs = simulacrum.context.conversation_messages
    assert len(msgs) == 1
    assert msgs[0].role == "assistant"
    assert msgs[0].content == "Something"
    assert len(simulacrum.retry_stack) == 1


@pytest.mark.asyncio
async def test_retry_detects_scene_message(
    simulacrum: Simulacrum,
    mock_openrouter,  # noqa: ARG001
) -> None:
    # Replace the existing assistant message with a scene message
    simulacrum.context.load()
    simulacrum.context.conversation_messages.clear()
    simulacrum.context.add_message(
        "user", "A dark room.", metadata={"scene": True, "scene_input": "darkness"}
    )
    simulacrum.context.save()

    response = await simulacrum.retry()

    assert response == "Something"
    # Verify the scene message was replaced (not an assistant message added)
    msgs = simulacrum.context.conversation_messages
    assert len(msgs) == 1
    assert msgs[0].role == "user"
    metadata = msgs[0].metadata
    assert metadata is not None
    assert metadata["scene"] is True
    assert metadata["scene_input"] == "darkness"
    # Verify retry stack has the old scene message
    assert len(simulacrum.retry_stack) == 1
    assert simulacrum.retry_stack[0][0].content == "A dark room."


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
    assert messages[-1]["role"] == "user"
    assert "<instruct>Continue</instruct>" in messages[-1]["content"][0]["text"]

    # Verify the temp message is not persisted
    msgs = simulacrum.context.conversation_messages
    assert len(msgs) == 2
    assert msgs[0].role == "assistant"
    assert msgs[1].role == "assistant"


def test_reset_conversation(
    simulacrum: Simulacrum,
    context_data: dict[str, Any],
) -> None:
    simulacrum.reset_conversation()

    # Verify conversation file doesn't change
    with open("context.yml") as f:
        new_context_data = YAML(typ="safe").load(f)
        assert (
            new_context_data["conversation_file"] == context_data["conversation_file"]
        )

    # Verify conversation file was reset
    with open("conversations/test_0.yml") as f:
        new_conversation_data = YAML(typ="safe").load(f)
        assert new_conversation_data["cost"] == 0.0
        assert len(new_conversation_data["messages"]) == 0
