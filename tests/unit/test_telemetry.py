import asyncio
import json

from src.telemetry import Telemetry

PATH = "/base/telemetry.jsonl"


def read() -> list[dict]:
    with open(PATH) as file:
        return [json.loads(line) for line in file]


class TestTelemetry:
    def test_appends_one_line_per_record(self, fs):  # noqa: ARG002
        telemetry = Telemetry(PATH, deployment="development")
        telemetry.record(kind="request", cost=0.1)
        telemetry.record(kind="turn", cost=0.1)
        rows = read()
        assert [row["kind"] for row in rows] == ["request", "turn"]
        assert rows[0]["deployment"] == "development"
        assert rows[0]["ts"].endswith("+00:00")

    def test_without_a_path_records_nothing(self, fs):
        Telemetry(None).record(kind="turn")
        assert not fs.exists("/base")


class TestTimedRecord:
    def test_ok_writes_the_status_and_duration(self, fs):  # noqa: ARG002
        Telemetry(PATH).start(kind="request", stage="response").ok(cost=0.1)
        (row,) = read()
        assert row["status"] == "ok"
        assert row["stage"] == "response"
        assert row["cost"] == 0.1
        assert row["duration_ms"] >= 0

    def test_ts_is_the_start_time(self, fs, monkeypatch):  # noqa: ARG002
        import time

        record = Telemetry(PATH).start(kind="turn")
        monkeypatch.setattr(time, "monotonic", lambda: record._started + 1.5)
        record.ok()
        (row,) = read()
        assert row["duration_ms"] == 1500
        assert next(iter(row)) == "ts"

    def test_counts_attempts_only_when_retried(self, fs):  # noqa: ARG002
        telemetry = Telemetry(PATH)
        telemetry.start(kind="request").ok()
        record = telemetry.start(kind="request")
        record.retried()
        record.ok()
        first, second = read()
        assert "attempts" not in first
        assert second["attempts"] == 2

    def test_fail_describes_the_error(self, fs):  # noqa: ARG002
        Telemetry(PATH).start(kind="turn").fail(RuntimeError("Response was empty"))
        (row,) = read()
        assert row["status"] == "error"
        assert row["error"] == "RuntimeError: Response was empty"

    def test_cancellation_is_its_own_status(self, fs):  # noqa: ARG002
        Telemetry(PATH).start(kind="turn").fail(asyncio.CancelledError())
        (row,) = read()
        assert row["status"] == "cancelled"
        assert row["error"] == "CancelledError"
