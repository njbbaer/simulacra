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
def generation_id() -> str:
    return "gen-4567291038-XpT8aKfqs2wRvZyLmEgC"


@pytest.fixture
def mock_completion_response(generation_id: str) -> dict[str, Any]:
    return {
        "id": generation_id,
        "choices": [
            {
                "message": {
                    "content": "Something",
                },
            }
        ],
    }


@pytest.fixture
def mock_cost_response() -> dict[str, Any]:
    return {"data": {"total_cost": 0.1}}


@pytest.fixture
def mock_openrouter(
    httpx_mock,
    generation_id: str,
    mock_completion_response: dict[str, Any],
    mock_cost_response: dict[str, Any],
):
    httpx_mock.add_response(
        url="https://openrouter.ai/api/v1/chat/completions",
        json=mock_completion_response,
    )
    httpx_mock.add_response(
        url=f"https://openrouter.ai/api/v1/generation?id={generation_id}",
        json=mock_cost_response,
    )
    return httpx_mock


@pytest.mark.asyncio
async def test_simulacrum_chat(
    simulacrum: Simulacrum,
    mock_openrouter,
    context_data: dict[str, Any],
    conversation_data: dict[str, Any],
    generation_id: str,
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

    # Verify OpenRouter cost tracking request was made
    assert mock_openrouter.get_requests(
        url=f"https://openrouter.ai/api/v1/generation?id={generation_id}"
    )

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
        assert isinstance(new_conversation_data["facts"], list)
        assert len(new_conversation_data["facts"]) == 0
        assert isinstance(new_conversation_data["messages"], list)
        assert len(new_conversation_data["messages"]) == 0


def test_reset_conversation(
    simulacrum: Simulacrum,
    context_data: dict[str, Any],
    conversation_data: dict[str, Any],
) -> None:
    initial_cost = conversation_data["cost"]
    initial_message_count = len(conversation_data["messages"])

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
        assert len(new_conversation_data["facts"]) == 0
        assert len(new_conversation_data["messages"]) == 0
        assert new_conversation_data["cost"] < initial_cost
        assert len(new_conversation_data["messages"]) < initial_message_count
