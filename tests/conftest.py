from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def model_directory(tmp_path: Path) -> Path:
    from student_dictation.core import MODEL_BY_KEY, mark_model_ready

    directory = tmp_path / "models" / "base"
    directory.mkdir(parents=True)
    for filename in ("model.bin", "config.json", "tokenizer.json", "vocabulary.json"):
        (directory / filename).write_bytes(b"fixture")
    mark_model_ready(directory, MODEL_BY_KEY["base"])
    return directory


@pytest.fixture
def window(qtbot, tmp_path, monkeypatch):
    from student_dictation.audio import Recorder
    from student_dictation.ui import MainWindow

    monkeypatch.setattr(Recorder, "devices", staticmethod(lambda: []))
    instance = MainWindow(cache=tmp_path)
    qtbot.addWidget(instance)
    yield instance
    instance.timer.stop()
    instance.paste_timer.stop()
    instance.runner.shutdown()
    instance.state = "idle"
    instance.close()
