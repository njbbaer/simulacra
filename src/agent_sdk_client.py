"""Serve a chat-completions request through the Claude Agent SDK.

Runs on a Claude subscription instead of OpenRouter, selected by an `agent-sdk/`
model prefix. Prior turns are replayed by resuming a synthetic session, and any
trailing system message is folded into the final user turn.
"""

import asyncio
import datetime
import os
import tempfile
import uuid
from collections.abc import AsyncIterator
from typing import Any, cast

from claude_agent_sdk import (
    ClaudeAgentOptions,
    InMemorySessionStore,
    ResultMessage,
    SessionKey,
    SessionStoreEntry,
    project_key_for_directory,
    query,
)

MODEL_PREFIX = "agent-sdk/"
IGNORED_KEYS = {"messages", "provider", "session_id"}
WORK_DIR = os.path.join(tempfile.gettempdir(), "simulacra-agent-sdk")
TIMEOUT_SECONDS = 180
CLI_ENV = {
    "CLAUDE_CODE_SESSION_NAME": "simulacra",
    # Disables telemetry, error reporting, and auto-updates
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
}


def is_agent_sdk_model(model: str) -> bool:
    return model.startswith(MODEL_PREFIX)


async def fetch_agent_sdk_completion(body: dict[str, Any]) -> dict[str, Any]:
    system_prompt, history, prompt = split_messages(body["messages"])
    os.makedirs(WORK_DIR, exist_ok=True)
    store, session_id = await replay(history) if history else (None, None)
    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        tools=[],
        max_turns=1,
        setting_sources=[],
        cwd=WORK_DIR,
        verbatim_prompts=True,
        extra_args={"no-session-persistence": None},
        session_store=store,
        resume=session_id,
        **translate_params(body),
    )
    async with asyncio.timeout(TIMEOUT_SECONDS):
        result = await run_query(options, prompt)
    return to_completion(result)


async def replay(turns: list[dict[str, Any]]) -> tuple[InMemorySessionStore, str]:
    """Return a session store holding the turns, and the session ID to resume."""
    session_id = str(uuid.uuid4())
    store = InMemorySessionStore()
    project_key = project_key_for_directory(WORK_DIR)
    key = SessionKey(project_key=project_key, session_id=session_id)
    await store.append(key, to_entries(turns, session_id))
    return store, session_id


def translate_params(body: dict[str, Any]) -> dict[str, Any]:
    """Map OpenRouter request params to `ClaudeAgentOptions` fields."""
    params = {k: v for k, v in body.items() if k not in IGNORED_KEYS}
    reasoning = params.pop("reasoning", {})
    env = dict(CLI_ENV)
    if "max_tokens" in params:
        env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(params.pop("max_tokens"))
    options = {"model": params.pop("model").removeprefix(MODEL_PREFIX), "env": env}
    if "effort" in reasoning:
        options["effort"] = reasoning.pop("effort")
    unsupported = [*params, *(f"reasoning.{k}" for k in reasoning)]
    if unsupported:
        raise ValueError(f"Unsupported by the Agent SDK: {', '.join(unsupported)}")
    return options


def split_messages(
    messages: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (system prompt, prior turns, final user content blocks)."""
    system_parts: list[str] = []
    turns: list[dict[str, Any]] = []
    for message in messages:
        blocks = to_blocks(message["content"])
        if message["role"] == "system":
            system_parts.append(_text_of(blocks))
        else:
            turns.append({"role": message["role"], "content": blocks})
    trailing = system_parts[1:]
    system_prompt = system_parts[0] if system_parts else ""
    if turns and turns[-1]["role"] == "user":
        prompt = turns.pop()["content"]
    elif trailing:
        prompt = []
    else:
        raise RuntimeError("No user message to send")
    prompt += [{"type": "text", "text": text} for text in trailing]
    return system_prompt, turns, prompt


def to_blocks(content: str | list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert chat-completions content to Anthropic content blocks."""
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    blocks = []
    for part in content:
        if part["type"] == "text":
            blocks.append({"type": "text", "text": part["text"]})
        elif part["type"] == "image_url":
            header, data = part["image_url"]["url"].split(",", 1)
            media_type = header.removeprefix("data:").split(";")[0]
            source = {"type": "base64", "media_type": media_type, "data": data}
            blocks.append({"type": "image", "source": source})
    return blocks


def to_entries(turns: list[dict[str, Any]], session_id: str) -> list[SessionStoreEntry]:
    """Build session transcript lines for prior turns."""
    entries: list[SessionStoreEntry] = []
    parent = None
    for turn in turns:
        entry_id = str(uuid.uuid4())
        message: dict[str, Any] = {"role": turn["role"], "content": turn["content"]}
        if turn["role"] == "assistant":
            message["type"] = "message"
            message["stop_reason"] = "end_turn"
        entry = {
            "type": turn["role"],
            "uuid": entry_id,
            "parentUuid": parent,
            "isSidechain": False,
            "message": message,
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            "sessionId": session_id,
            "cwd": WORK_DIR,
        }
        entries.append(cast(SessionStoreEntry, entry))
        parent = entry_id
    return entries


async def run_query(
    options: ClaudeAgentOptions, prompt: list[dict[str, Any]]
) -> ResultMessage:
    result = None
    async for message in query(prompt=_user_stream(prompt), options=options):
        if isinstance(message, ResultMessage):
            result = message
    if result is None:
        raise RuntimeError("Agent SDK returned no result")
    if result.is_error or result.subtype != "success":
        raise RuntimeError(result.result or f"Agent SDK error: {result.subtype}")
    return result


async def _user_stream(prompt: list[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
    yield {"type": "user", "message": {"role": "user", "content": prompt}}


def to_completion(result: ResultMessage) -> dict[str, Any]:
    """Shape the result like an OpenRouter chat-completions response."""
    usage = result.usage or {}
    cached = usage.get("cache_read_input_tokens", 0)
    prompt_tokens = (
        usage.get("input_tokens", 0)
        + cached
        + usage.get("cache_creation_input_tokens", 0)
    )
    return {
        "provider": "Agent SDK",
        "choices": [
            {
                "message": {"role": "assistant", "content": result.result},
                "finish_reason": (
                    "length" if result.stop_reason == "max_tokens" else "stop"
                ),
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": usage.get("output_tokens", 0),
            "prompt_tokens_details": {"cached_tokens": cached},
            "cost": 0.0,
            "cost_details": {"upstream_inference_cost": 0.0},
            "plan_cost": result.total_cost_usd or 0.0,
        },
    }


def _text_of(blocks: list[dict[str, Any]]) -> str:
    return "\n\n".join(b["text"] for b in blocks if b["type"] == "text")
