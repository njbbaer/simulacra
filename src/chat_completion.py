from typing import Any


class ChatCompletion:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self._validate()

    @property
    def content(self) -> str:
        return self._choice["message"]["content"].strip()

    @property
    def prompt_tokens(self) -> int:
        return self._usage["prompt_tokens"]

    @property
    def completion_tokens(self) -> int:
        return self._usage["completion_tokens"]

    @property
    def cached_tokens(self) -> int:
        return self._usage["prompt_tokens_details"]["cached_tokens"]

    @property
    def cost(self) -> float:
        return (
            self._usage["cost"]
            or self._usage["cost_details"]["upstream_inference_cost"]
        )

    def _validate(self) -> None:
        if self._error_message:
            raise RuntimeError(self._error_message)
        if self._finish_reason == "length":
            raise RuntimeError("Response exceeded maximum length")
        if not self.content:
            raise RuntimeError("Response was empty")

    @property
    def _usage(self) -> dict[str, Any]:
        return self.response["usage"]

    @property
    def _choice(self) -> dict[str, Any]:
        return self.response["choices"][0]

    @property
    def _finish_reason(self) -> str | None:
        return self._choice.get("finish_reason")

    @property
    def _error_message(self) -> str:
        return self.response.get("error", {}).get("message", "")
