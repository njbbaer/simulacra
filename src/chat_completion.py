class ChatCompletion:
    def __init__(self, response, pricing):
        self.response = response
        self.pricing = pricing
        self._validate()

    def _validate(self):
        if self._error_message:
            raise Exception(self.error_message)
        if self._finish_reason == "length":
            raise Exception("Response exceeded maximum length")
        if not self.content:
            raise Exception("Response was empty")

    @property
    def _choice(self):
        return self.response["choices"][0]

    @property
    def content(self):
        return self._choice["message"]["content"]

    @property
    def _prompt_tokens(self):
        return self.response["usage"]["prompt_tokens"]

    @property
    def _completion_tokens(self):
        return self.response["usage"]["completion_tokens"]

    @property
    def _finish_reason(self):
        return self._choice.get("finish_reason")

    @property
    def _error_message(self):
        return self.response.get("error", {}).get("message", "")

    @property
    def _cache_discount(self):
        return self.response["details"]["cache_discount"]

    @property
    def cache_discount_string(self):
        sign = "-" if self._cache_discount < 0 else ""
        amount = f"${abs(self._cache_discount):.2f}"
        return f"{sign}{amount}"

    @property
    def cost(self):
        return self.response["details"]["total_cost"]
