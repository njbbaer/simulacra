from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.agent_sdk_client import (
    fetch_agent_sdk_completion,
    split_messages,
    to_blocks,
    to_completion,
    to_entries,
    translate_params,
)


def _text(role, text):
    return {"role": role, "content": [{"type": "text", "text": text}]}


def _result(**overrides):
    fields = {
        "subtype": "success",
        "is_error": False,
        "stop_reason": "end_turn",
        "total_cost_usd": 0.01,
        "result": "Hi",
        "usage": {
            "input_tokens": 10,
            "cache_read_input_tokens": 20,
            "cache_creation_input_tokens": 5,
            "output_tokens": 7,
        },
    }
    return SimpleNamespace(**{**fields, **overrides})


def test_split_messages_separates_system_history_and_prompt():
    messages = [
        _text("system", "Be Margaret."),
        _text("user", "Hi"),
        _text("assistant", "Hello, Peter."),
        _text("user", "Where are we?"),
        _text("system", "Reinforce."),
    ]
    system_prompt, history, prompt = split_messages(messages)
    assert system_prompt == "Be Margaret."
    assert [t["role"] for t in history] == ["user", "assistant"]
    assert prompt == [
        {"type": "text", "text": "Where are we?"},
        {"type": "text", "text": "Reinforce."},
    ]


def test_split_messages_uses_trailing_system_when_history_ends_with_assistant():
    messages = [
        _text("system", "Be Margaret."),
        _text("user", "Hi"),
        _text("assistant", "Hello."),
        _text("system", "<instruct>Continue</instruct>"),
    ]
    _, history, prompt = split_messages(messages)
    assert len(history) == 2
    assert prompt == [{"type": "text", "text": "<instruct>Continue</instruct>"}]


def test_split_messages_raises_without_user_turn():
    messages = [_text("system", "Be Margaret."), _text("assistant", "Hello.")]
    with pytest.raises(RuntimeError, match="No user message"):
        split_messages(messages)


def test_to_blocks_converts_data_url_image():
    content = [
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,QUJD"}},
        {"type": "text", "text": "Look", "cache_control": {"type": "ephemeral"}},
    ]
    assert to_blocks(content) == [
        {
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": "QUJD"},
        },
        {"type": "text", "text": "Look"},
    ]


def test_to_entries_chains_parents_and_marks_assistant_messages():
    turns = [
        {"role": "user", "content": [{"type": "text", "text": "Hi"}]},
        {"role": "assistant", "content": [{"type": "text", "text": "Hello"}]},
    ]
    entries = to_entries(turns, "sid")
    assert entries[0]["parentUuid"] is None
    assert entries[1]["parentUuid"] == entries[0]["uuid"]
    assert entries[1]["type"] == "assistant"
    assert entries[1]["message"]["stop_reason"] == "end_turn"
    assert all(e["sessionId"] == "sid" for e in entries)


def test_to_completion_shapes_usage_like_openrouter():
    completion = to_completion(_result())
    assert completion["choices"][0]["message"]["content"] == "Hi"
    assert completion["choices"][0]["finish_reason"] == "stop"
    assert completion["usage"]["prompt_tokens"] == 35
    assert completion["usage"]["completion_tokens"] == 7
    assert completion["usage"]["prompt_tokens_details"]["cached_tokens"] == 20
    assert completion["usage"]["cost"] == 0.01


def test_to_completion_reports_length_on_max_tokens():
    completion = to_completion(_result(stop_reason="max_tokens"))
    assert completion["choices"][0]["finish_reason"] == "length"


def test_translate_params_maps_openrouter_params():
    body = {
        "model": "agent-sdk/claude-opus-5-5",
        "max_tokens": 500,
        "reasoning": {"effort": "low"},
        "provider": {"only": ["anthropic"]},
        "session_id": "alice_42",
        "messages": [],
    }
    assert translate_params(body) == {
        "model": "claude-opus-5-5",
        "effort": "low",
        "env": {
            "CLAUDE_CODE_SESSION_NAME": "simulacra",
            "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "500",
        },
    }


def test_translate_params_rejects_unsupported_params():
    body = {
        "model": "agent-sdk/claude-opus-5-5",
        "temperature": 0.7,
        "reasoning": {"effort": "low", "exclude": True},
    }
    with pytest.raises(ValueError, match=r"temperature, reasoning\.exclude"):
        translate_params(body)


@pytest.mark.asyncio
async def test_fetch_resumes_history():
    body = {
        "model": "agent-sdk/claude-opus-5-5",
        "messages": [
            _text("system", "Be Margaret."),
            _text("user", "Hi"),
            _text("assistant", "Hello."),
            _text("user", "Again"),
        ],
    }
    run = AsyncMock(return_value=_result(result="Reply"))
    with patch("src.agent_sdk_client.run_query", run):
        completion = await fetch_agent_sdk_completion(body)
    options, prompt = run.call_args.args
    assert completion["choices"][0]["message"]["content"] == "Reply"
    assert options.model == "claude-opus-5-5"
    assert options.system_prompt == "Be Margaret."
    assert options.tools == []
    assert options.resume is not None
    assert options.session_store is not None
    assert prompt == [{"type": "text", "text": "Again"}]


@pytest.mark.asyncio
async def test_fetch_without_history_does_not_resume():
    body = {
        "model": "agent-sdk/claude-opus-5-5",
        "messages": [_text("system", "Be Margaret."), _text("user", "Hi")],
    }
    run = AsyncMock(return_value=_result())
    with patch("src.agent_sdk_client.run_query", run):
        await fetch_agent_sdk_completion(body)
    options, _ = run.call_args.args
    assert options.resume is None
    assert options.session_store is None
