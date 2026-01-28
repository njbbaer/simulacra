import pytest

from src.chat_completion import ChatCompletion


def _make_response(**overrides):
    return {
        "choices": [{"message": {"content": "Hello"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        "details": {"upstream_inference_cost": 0.01},
    } | overrides


class TestChatCompletionProperties:
    def test_content(self):
        c = ChatCompletion(_make_response())
        assert c.content == "Hello"

    def test_token_counts(self):
        c = ChatCompletion(_make_response())
        assert c.prompt_tokens == 10
        assert c.completion_tokens == 5

    def test_cost(self):
        c = ChatCompletion(_make_response())
        assert c.cost == 0.01


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


class TestCacheDiscountString:
    def test_no_discount(self):
        c = ChatCompletion(_make_response())
        assert c.cache_discount_string == "N/A"

    def test_positive_discount(self):
        resp = _make_response()
        resp["details"]["cache_discount"] = 0.05
        c = ChatCompletion(resp)
        assert c.cache_discount_string == "$0.05"

    def test_negative_discount(self):
        resp = _make_response()
        resp["details"]["cache_discount"] = -0.03
        c = ChatCompletion(resp)
        assert c.cache_discount_string == "-$0.03"
