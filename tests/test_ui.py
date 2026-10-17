import sys
import tempfile
from pathlib import Path

from PySide6.QtWidgets import QMessageBox

from student_dictation.jobs import JobRunner


def test_first_launch_has_no_network_or_keyboard_features(window):
    assert window.offline.isChecked()
    assert not window.download.isEnabled()
    assert not window.record.isEnabled()
    assert not window.enable_shortcut.isChecked()
    assert not window.enable_paste.isChecked()
    assert not window.runner.busy
    assert window.editor.toPlainText() == ""


def test_translation_switches_to_supported_model(window):
    assert window.model.currentData() == "large-v3-turbo"
    window.task.setCurrentIndex(1)
    assert window.model.currentData() == "large-v3"
    assert not window.model.model().item(0).isEnabled()
    window.task.setCurrentIndex(0)
    assert window.model.model().item(0).isEnabled()


def test_success_appends_and_undo_preserves_existing_text(window):
    window.editor.setPlainText("Earlier draft.")
    window.pending_result = {"kind": "transcription", "text": "New words.", "language": "en"}
    window.state = "working"
    window._job_finished(True, "")
    assert window.editor.toPlainText() == "Earlier draft.\n\nNew words."
    window.editor.undo()
    assert window.editor.toPlainText() == "Earlier draft."
    assert window.state == "idle"


def test_failure_preserves_text_and_removes_temporary_audio(window, tmp_path):
    window.editor.setPlainText("Keep this.")
    window.recording_file = tempfile.TemporaryDirectory(dir=tmp_path)
    directory = Path(window.recording_file.name)
    (directory / "microphone.wav").write_bytes(b"temporary recording")
    window.state = "working"
    window._job_finished(False, "Out of memory")
    assert window.editor.toPlainText() == "Keep this."
    assert not directory.exists()
    assert "Out of memory" in window.status.text()
    assert window.state == "idle"


def test_cancelled_actual_subprocess_preserves_editor(window, qtbot):
    window.editor.setPlainText("Keep these notes.")
    window.runner.command = [sys.executable, str(Path(__file__).with_name("fixture_job.py"))]
    with qtbot.waitSignal(window.runner.event, timeout=5000):
        window._start_job({"operation": "transcribe", "mode": "sleep"})
    with qtbot.waitSignal(window.runner.finished, timeout=3000):
        window._cancel()
    assert window.editor.toPlainText() == "Keep these notes."
    assert window.state == "idle"
    assert "Cancelled" in window.status.text()


def test_no_speech_keeps_old_text(window):
    window.editor.setPlainText("Old text.")
    window.pending_result = {"kind": "transcription", "text": "", "language": "en"}
    window._job_finished(True, "")
    assert window.editor.toPlainText() == "Old text."
    assert "No speech" in window.status.text()


def test_paste_cannot_be_enabled_without_consent(window, monkeypatch):
    monkeypatch.setattr(
        QMessageBox, "question", lambda *_args, **_kwargs: QMessageBox.StandardButton.Cancel
    )
    window.enable_paste.setChecked(True)
    assert not window.enable_paste.isChecked()
    assert not window.paste.isEnabled()


def test_clear_can_be_undone(window):
    window.editor.setPlainText("Important text.")
    window._clear_text()
    assert window.editor.toPlainText() == ""
    window.editor.undo()
    assert window.editor.toPlainText() == "Important text."


def test_download_does_not_start_when_offline(window, monkeypatch):
    def unexpected(*_args):
        raise AssertionError("No dialog or worker should start while offline")

    monkeypatch.setattr(QMessageBox, "question", unexpected)
    monkeypatch.setattr(JobRunner, "start", unexpected)
    window._download_model()


def test_clipboard_change_cancels_pending_paste(window, monkeypatch, qapp):
    monkeypatch.setattr(
        QMessageBox, "question", lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes
    )
    window.editor.setPlainText("My transcript")
    window.enable_paste.setChecked(True)
    window._schedule_paste()
    window.paste_timer.stop()
    qapp.clipboard().setText("A different clipboard value")
    monkeypatch.setattr(type(qapp), "activeWindow", staticmethod(lambda: None))
    window.paste_seconds = 1
    window._paste_tick()
    assert "clipboard changed" in window.status.text()
    assert window.state == "idle"
