import sys
from pathlib import Path

import pytest

from student_dictation.jobs import JobRunner


def runner_command():
    return [sys.executable, str(Path(__file__).with_name("fixture_job.py"))]


def test_successful_job_returns_events_and_can_be_reused(qtbot):
    runner = JobRunner(command=runner_command())
    events = []
    runner.event.connect(events.append)
    for _ in range(2):
        with qtbot.waitSignal(runner.finished, timeout=5000) as result:
            runner.start({"operation": "transcribe"})
        assert result.args == [True, ""]
        assert not runner.busy
    assert events[-1]["text"] == "New words."


@pytest.mark.parametrize(
    "mode,expected",
    [
        ("error", "Fixture failure"),
        ("invalid", "invalid response"),
        ("crash", "stopped unexpectedly"),
    ],
)
def test_worker_failures_are_reported(qtbot, mode, expected):
    runner = JobRunner(command=runner_command())
    with qtbot.waitSignal(runner.finished, timeout=5000) as result:
        runner.start({"operation": "transcribe", "mode": mode})
    assert result.args[0] is False
    assert expected in result.args[1]
    assert not runner.busy


def test_killing_worker_cancels_without_waiting_for_native_work(qtbot):
    runner = JobRunner(command=runner_command())
    with qtbot.waitSignal(runner.event, timeout=5000):
        runner.start({"operation": "transcribe", "mode": "sleep"})
    assert runner.busy
    with qtbot.waitSignal(runner.finished, timeout=3000) as result:
        runner.cancel()
    assert result.args[0] is False
    assert result.args[1].startswith("Cancelled")
    assert not runner.busy


def test_worker_launch_failure_leaves_runner_idle(qtbot, tmp_path):
    runner = JobRunner(command=[str(tmp_path / "missing-executable")])
    with qtbot.waitSignal(runner.finished, timeout=5000) as result:
        runner.start({"operation": "transcribe"})
    assert result.args[0] is False
    assert "could not start" in result.args[1]
    assert not runner.busy


def test_concurrent_jobs_are_rejected(qtbot):
    runner = JobRunner(command=runner_command())
    try:
        runner.start({"operation": "transcribe", "mode": "sleep"})
        with pytest.raises(RuntimeError, match="already running"):
            runner.start({"operation": "transcribe"})
    finally:
        runner.shutdown()
