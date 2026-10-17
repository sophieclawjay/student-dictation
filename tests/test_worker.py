import io
import json
import subprocess
import sys
from types import SimpleNamespace

import pytest

from student_dictation import worker
from student_dictation.core import model_ready


def test_successful_download_returns_result_and_complete_marker(tmp_path, monkeypatch, capsys):
    def snapshot_download(**kwargs):
        assert kwargs["token"] is False
        assert "model.bin" in kwargs["allow_patterns"]
        directory = tmp_path / "base"
        for filename in ("model.bin", "config.json", "tokenizer.json", "vocabulary.json"):
            (directory / filename).write_bytes(b"complete fixture")

    monkeypatch.setitem(
        sys.modules, "huggingface_hub", SimpleNamespace(snapshot_download=snapshot_download)
    )
    worker.download({"model": "base", "directory": str(tmp_path / "base")})
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert events[-1] == {"type": "result", "kind": "download"}
    assert model_ready(tmp_path / "base")


def test_partial_download_failure_has_no_complete_marker(tmp_path, monkeypatch):
    def failed_download(**kwargs):
        (tmp_path / "base" / "model.bin").write_bytes(b"partial")
        raise OSError("Network disconnected")

    monkeypatch.setitem(
        sys.modules, "huggingface_hub", SimpleNamespace(snapshot_download=failed_download)
    )
    with pytest.raises(OSError, match="Network"):
        worker.download({"model": "base", "directory": str(tmp_path / "base")})
    assert not model_ready(tmp_path / "base")


def test_transcribe_uses_local_cpu_int8_and_preserves_task(
    model_directory,
    tmp_path,
    monkeypatch,
    capsys,
):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"fixture")

    class FakeWhisper:
        def __init__(self, path, **kwargs):
            assert path == str(model_directory)
            assert kwargs["local_files_only"] is True
            assert kwargs["device"] == "cpu"
            assert kwargs["compute_type"] == "int8"

        def transcribe(self, path, **kwargs):
            assert path == str(audio)
            assert kwargs["task"] == "translate"
            assert kwargs["language"] == "ko"
            assert kwargs["vad_filter"] is True
            return iter(
                [SimpleNamespace(text=" Hello", end=1), SimpleNamespace(text=" world.", end=2)]
            ), SimpleNamespace(
                duration=2,
                language="ko",
                language_probability=0.95,
            )

    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=FakeWhisper))
    worker.transcribe(
        {
            "model": "base",
            "directory": str(model_directory),
            "audio": str(audio),
            "task": "translate",
            "language": "ko",
        }
    )
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    result = events[-1]
    assert result["type"] == "result"
    assert result["kind"] == "transcription"
    assert result["text"] == "Hello world."
    assert events[-2]["value"] == 99


def test_missing_tokenizer_fails_before_loading_inference(model_directory, tmp_path):
    (model_directory / "tokenizer.json").unlink()
    with pytest.raises(ValueError, match="installed completely"):
        worker.transcribe(
            {
                "model": "base",
                "task": "transcribe",
                "language": None,
                "directory": str(model_directory),
                "audio": str(tmp_path / "a.wav"),
            }
        )


def test_invalid_request_is_a_structured_error(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"operation":"unknown"}\n'))
    assert worker.main() == 1
    assert json.loads(capsys.readouterr().out)["type"] == "error"


def test_worker_exits_if_parent_pipe_is_closed():
    code = (
        "from student_dictation.worker import exit_when_parent_closes_pipe;"
        "import threading,time;"
        "threading.Thread(target=exit_when_parent_closes_pipe,daemon=True).start();"
        "print('ready',flush=True);time.sleep(30)"
    )
    process = subprocess.Popen(
        [sys.executable, "-c", code], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True
    )
    try:
        assert process.stdout.readline().strip() == "ready"
        process.stdin.close()
        assert process.wait(timeout=5) == 2
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        process.stdout.close()
