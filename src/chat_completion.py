class ChatCompletion:
    def __init__(self, response, pricing):
        self.response = response
        self.pricing = pricing
        self.validate()

    def validate(self):
        if self.error_message:
            raise Exception(self.error_message)
        if self.finish_reason == "length":
            raise Exception("Response exceeded maximum length")
        if self.content == "":
            raise Exception("Response was empty")

    @property
    def cost(self):
        if self.pricing:
            return (self.prompt_tokens / 1_000_000 * self.pricing[0]) + (
                self.completion_tokens / 1_000_000 * self.pricing[1]
            )
        return 0

    @property
    def error_message(self):
        return self.response.get("error", {}).get("message", "")

    @property
    def cache_creation_input_tokens(self):
        return 0

    @property
    def cache_read_input_tokens(self):
        return 0


class AnthropicChatCompletion(ChatCompletion):
    @property
    def choice(self):
        return self.response["content"][0]

    @property
    def content(self):
        return self.choice["text"]

    @property
    def prompt_tokens(self):
        return self.response["usage"]["input_tokens"]

    @property
    def completion_tokens(self):
        return self.response["usage"]["output_tokens"]

    @property
    def cache_creation_input_tokens(self):
        return self.response["usage"]["cache_creation_input_tokens"]

    @property
    def cache_read_input_tokens(self):
        return self.response["usage"]["cache_read_input_tokens"]

    @property
    def finish_reason(self):
        return self.response["stop_reason"]


class OpenRouterChatCompletion(ChatCompletion):
    @property
    def choice(self):
        return self.response["choices"][0]

    @property
    def content(self):
        return self.choice["message"]["content"]

    @property
    def prompt_tokens(self):
        return self.response["usage"]["prompt_tokens"]

    @property
    def completion_tokens(self):
        return self.response["usage"]["completion_tokens"]

    @property
    def finish_reason(self):
        return self.choice.get("finish_reason")
