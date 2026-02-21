import pytest

from src.chat_completion import ChatCompletion


def _make_response(**overrides):
    return {
        "choices": [{"message": {"content": "Hello"}, "finish_reason": "stop"}],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "cost": 0.01,
            "prompt_tokens_details": {"cached_tokens": 0},
        },
    } | overrides


class TestChatCompletionProperties:
    def test_content(self):
        c = ChatCompletion(_make_response())
        assert c.content == "Hello"

    def test_token_counts(self):
        c = ChatCompletion(_make_response())
        assert c.prompt_tokens == 10
        assert c.completion_tokens == 5

    def test_cost_from_usage(self):
        c = ChatCompletion(_make_response())
        assert c.cost == 0.01

    def test_cost_falls_back_to_upstream_inference_cost(self):
        c = ChatCompletion(
            _make_response(
                usage={
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "cost": 0,
                    "prompt_tokens_details": {"cached_tokens": 0},
                    "cost_details": {"upstream_inference_cost": 0.02},
                }
            )
        )
        assert c.cost == 0.02


class TestChatCompletionValidation:
    def test_error_message_raises(self):
        with pytest.raises(Exception, match="something broke"):
            ChatCompletion(_make_response(error={"message": "something broke"}))

    def test_length_exceeded_raises(self):
        resp = _make_response()
        resp["choices"][0]["finish_reason"] = "length"
        with pytest.raises(Exception, match="exceeded maximum length"):
            ChatCompletion(resp)

    def test_empty_content_raises(self):
        resp = _make_response()
        resp["choices"][0]["message"]["content"] = ""
        with pytest.raises(Exception, match="empty"):
            ChatCompletion(resp)


class TestCachedTokens:
    def test_cached_tokens(self):
        c = ChatCompletion(_make_response())
        assert c.cached_tokens == 0

    def test_with_cached_tokens(self):
        c = ChatCompletion(
            _make_response(
                usage={
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "cost": 0.01,
                    "prompt_tokens_details": {"cached_tokens": 42},
                }
            )
        )
        assert c.cached_tokens == 42
