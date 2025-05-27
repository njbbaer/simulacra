from typing import Any, Dict, Optional


class ChatCompletion:
    def __init__(self, response: Dict[str, Any]) -> None:
        self.response = response
        self._validate()

    def _validate(self) -> None:
        if self._error_message:
            raise Exception(self._error_message)
        if self._finish_reason == "length":
            raise Exception("Response exceeded maximum length")
        if not self.content:
            raise Exception("Response was empty")

    @property
    def content(self) -> str:
        return self._choice["message"]["content"]

    @property
    def prompt_tokens(self) -> int:
        return self.response["usage"]["prompt_tokens"]

    @property
    def completion_tokens(self) -> int:
        return self.response["usage"]["completion_tokens"]

    @property
    def cache_discount_string(self) -> str:
        sign = "-" if self._cache_discount < 0 else ""
        amount = f"${abs(self._cache_discount):.2f}"
        return f"{sign}{amount}"

    @property
    def cost(self) -> float:
        return self.response["details"]["total_cost"]

    @property
    def _choice(self) -> Dict[str, Any]:
        return self.response["choices"][0]

    @property
    def _finish_reason(self) -> Optional[str]:
        return self._choice.get("finish_reason")

    @property
    def _error_message(self) -> str:
        return self.response.get("error", {}).get("message", "")

    @property
    def _cache_discount(self) -> float:
        return self.response["details"]["cache_discount"]
