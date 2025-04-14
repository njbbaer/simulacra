import json
import os

import pytest
from ruamel.yaml import YAML

from src.simulacrum import Simulacrum
from src.yaml_config import yaml


@pytest.fixture
def custom_fs(fs):
    fs.add_real_file("src/lm_executors/chat_executor_template.j2")
    return fs


@pytest.fixture
def context_data():
    return {
        "char_name": "test",
        "model": "anthropic/claude",
        "conversation_id": 0,
        "total_cost": 0.0,
        "pricing": [1, 2],
        "vars": {
            "chat_prompt": "Say something!",
        },
    }


@pytest.fixture
def conversation_data():
    return {
        "cost": 0.0,
        "facts": [],
        "messages": [],
    }


@pytest.fixture
def simulacrum_context(custom_fs, context_data, conversation_data):
    with open("context.yml", "w") as f:
        yaml.dump(context_data, f)
    os.makedirs("conversations", exist_ok=True)
    with open("conversations/test_0.yml", "w") as f:
        yaml.dump(conversation_data, f)


@pytest.fixture
def simulacrum(simulacrum_context):
    return Simulacrum("context.yml")


@pytest.fixture
def generation_id():
    return "gen-4567291038-XpT8aKfqs2wRvZyLmEgC"


@pytest.fixture
def mock_completion_response(generation_id):
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
def mock_cost_response():
    return {"data": {"total_cost": 0.1}}


@pytest.fixture
def mock_openrouter(
    httpx_mock, generation_id, mock_completion_response, mock_cost_response
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


@pytest.fixture
def expected_request_body():
    return {
        "model": "anthropic/claude",
        "max_tokens": 8192,
        "messages": [
            {
                "role": "system",
                "content": [
                    {
                        "text": "Say something!",
                        "type": "text",
                    },
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "text": "Hello",
                        "type": "text",
                        "cache_control": {
                            "type": "ephemeral",
                        },
                    },
                ],
            },
        ],
    }


@pytest.mark.asyncio
async def test_simulacrum_chat(
    simulacrum,
    mock_openrouter,
    context_data,
    conversation_data,
    generation_id,
    expected_request_body,
):
    await simulacrum.chat("Hello", None, None)

    # Verify OpenRouter LLM completion request
    request = mock_openrouter.get_requests(
        url="https://openrouter.ai/api/v1/chat/completions",
    )[0]
    actual_body = json.loads(request.content)
    assert actual_body == expected_request_body

    # Verify OpenRouter cost tracking request
    assert mock_openrouter.get_requests(
        url=f"https://openrouter.ai/api/v1/generation?id={generation_id}"
    )

    # Verify contents of the context file
    with open("context.yml", "r") as f:
        expected_context_data = context_data.copy()
        expected_context_data["conversation_id"] = 0
        expected_context_data["total_cost"] = 0.1
        new_context_data = YAML(typ="safe").load(f)
        assert new_context_data == expected_context_data

    # Verify contents of the conversation file
    with open("conversations/test_0.yml", "r") as f:
        expected_conversation_data = conversation_data.copy()
        expected_conversation_data["cost"] = 0.1
        expected_conversation_data["messages"] = [
            {
                "role": "user",
                "content": "Hello",
            },
            {
                "role": "assistant",
                "content": "Something",
            },
        ]
        new_conversation_data = YAML(typ="safe").load(f)
        assert new_conversation_data == expected_conversation_data


@pytest.mark.asyncio
async def test_new_conversation(simulacrum, context_data):
    await simulacrum.new_conversation()

    # Verify context file updates
    with open("context.yml", "r") as f:
        expected_context_data = context_data.copy()
        expected_context_data["conversation_id"] = 1
        new_context_data = YAML(typ="safe").load(f)
        assert new_context_data == expected_context_data

    # Verify contents of the new conversation file
    assert os.path.exists("conversations/test_1.yml")
    with open("conversations/test_1.yml", "r") as f:
        expected_conversation_data = {
            "cost": 0.0,
            "facts": [],
            "messages": [],
        }
        new_conversation_data = YAML(typ="safe").load(f)
        assert new_conversation_data == expected_conversation_data
