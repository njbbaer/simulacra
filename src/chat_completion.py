from .logger import Logger


class ChatCompletion:
    def __init__(self, response, pricing):
        self.response = response
        self.pricing = pricing
        self.logger = Logger("log.yml")

    @classmethod
    async def generate(cls, client, content, parameters, pricing=None):
        response = await client.call_api(content, parameters)
        completion = cls(response, pricing)
        completion.validate()
        completion.logger.log(parameters, content, completion.content)
        return completion

    def validate(self):
        if self.error_message:
            raise Exception(self.error_message)
        if self.finish_reason == "length":
            raise Exception("Response exceeded maximum length")
        if self.content == "":
            raise Exception("Response was empty")

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
        return self.choice["finish_reason"]

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
