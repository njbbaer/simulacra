from src.request_recorder import RequestRecorder
from src.yaml_config import yaml

PATH = "/last_request.yml"


def read() -> dict:
    with open(PATH) as file:
        return yaml.load(file)


class TestRequestRecorder:
    def test_records_an_exchange_under_its_key(self, fs):  # noqa: ARG002
        RequestRecorder(PATH).record({"model": "one"}, {"id": "gen"}, "response")
        assert read() == {
            "response": {"request": {"model": "one"}, "response": {"id": "gen"}}
        }

    def test_keeps_the_keys_recorded_before_it(self, fs):  # noqa: ARG002
        recorder = RequestRecorder(PATH)
        recorder.record({}, {}, "response_A")
        recorder.record({}, {}, "response_B")
        assert sorted(read()) == ["response_A", "response_B"]

    def test_reset_drops_the_previous_turn(self, fs):  # noqa: ARG002
        recorder = RequestRecorder(PATH)
        recorder.record({}, {}, "response")
        recorder.reset()
        recorder.record({}, {}, "post_process")
        assert list(read()) == ["post_process"]

    def test_reset_without_a_log_is_harmless(self, fs):  # noqa: ARG002
        RequestRecorder(PATH).reset()

    def test_truncates_long_urls(self, fs):  # noqa: ARG002
        url = "https://example.com/" + "x" * 100
        RequestRecorder(PATH).record({"url": url}, {}, "response")
        assert read()["response"]["request"]["url"].endswith("...")
