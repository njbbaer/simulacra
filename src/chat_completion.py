from .logger import Logger


class ChatCompletion:
    MODEL_PRICES = {
        "gpt-4": [0.03, 0.06],
        "gpt-4-0314": [0.03, 0.06],
        "gpt-4-1106-preview": [0.01, 0.02],
        "gpt-4-vision-preview": [0.01, 0.02],
        "gpt-3.5-turbo": [0.0015, 0.002],
        "gpt-3.5-turbo-16k": [0.003, 0.004],
        "gpt-3.5-turbo-instruct": [0.0015, 0.002],
        "anthropic/claude-3-opus:beta": [0.015, 0.075],
        "meta-llama/llama-3-70b-instruct": [0.0008, 0.0008],
    }

    def __init__(self, response, model):
        self.response = response
        self.pricing = self.MODEL_PRICES.get(model, [0, 0])
        self.logger = Logger("log.yml")

    @classmethod
    async def generate(cls, client, content, parameters):
        response = await client.call_api(content, parameters)
        completion = cls(response, parameters.get("model"))
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
        return (self.prompt_tokens / 1000 * self.pricing[0]) + (
            self.completion_tokens / 1000 * self.pricing[1]
        )

    @property
    def error_message(self):
        return self.response.get("error", {}).get("message", "")
