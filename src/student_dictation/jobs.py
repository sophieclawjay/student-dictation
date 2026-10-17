"""Qt process runner with bounded protocol parsing and deterministic cancellation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal

from .core import private_environment


def worker_command() -> list[str]:
    if getattr(sys, "frozen", False):
        suffix = ".exe" if sys.platform == "win32" else ""
        worker = Path(sys.executable).with_name(f"StudentDictationWorker{suffix}")
        return [str(worker), "--worker"]
    return [sys.executable, "-m", "student_dictation", "--worker"]


class JobRunner(QObject):
    event = Signal(dict)
    finished = Signal(bool, str)

    def __init__(self, parent: QObject | None = None, command: list[str] | None = None):
        super().__init__(parent)
        self.command = command
        self.process: QProcess | None = None
        self._buffer = bytearray()
        self._error = ""
        self._result = False
        self._cancelled = False

    @property
    def busy(self) -> bool:
        return self.process is not None

    def start(self, request: dict) -> None:
        if self.busy:
            raise RuntimeError("A job is already running.")
        self._buffer.clear()
        self._error = ""
        self._result = False
        self._cancelled = False
        process = QProcess(self)
        self.process = process
        environment = QProcessEnvironment.systemEnvironment()
        for name, value in private_environment(offline=request["operation"] != "download").items():
            environment.insert(name, value)
        # Prevent a frozen child from reusing the parent's application lifetime context.
        environment.insert("PYINSTALLER_RESET_ENVIRONMENT", "1")
        process.setProcessEnvironment(environment)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        process.readyReadStandardOutput.connect(self._read_output)
        process.readyReadStandardError.connect(self._drain_error)
        process.errorOccurred.connect(self._process_error)
        process.finished.connect(self._process_finished)
        process.started.connect(lambda: process.write((json.dumps(request) + "\n").encode("utf-8")))
        command = self.command or worker_command()
        process.start(command[0], command[1:])
        # Keep stdin open: EOF tells the worker that its parent is gone.

    def cancel(self) -> None:
        if self.process is not None:
            self._cancelled = True
            self.process.kill()

    def shutdown(self) -> None:
        if self.process is not None:
            self._cancelled = True
            self.process.kill()
            self.process.waitForFinished(3000)

    def _read_output(self) -> None:
        if self.process is None:
            return
        self._buffer.extend(bytes(self.process.readAllStandardOutput()))
        if len(self._buffer) > 16 * 1024 * 1024:
            self._error = "The recognition result was too large. Try a shorter audio file."
            self.process.kill()
            return
        while b"\n" in self._buffer:
            line, _, remainder = self._buffer.partition(b"\n")
            self._buffer = bytearray(remainder)
            try:
                event = json.loads(line)
                if not isinstance(event, dict) or "type" not in event:
                    raise ValueError("Invalid event")
            except (ValueError, UnicodeDecodeError):
                self._error = "The local worker returned an invalid response. Restart the app."
                self.process.kill()
                return
            if event["type"] == "result":
                self._result = True
            elif event["type"] == "error":
                self._error = str(event.get("message", "Local recognition failed."))
            if not self._cancelled:
                self.event.emit(event)

    def _drain_error(self) -> None:
        if self.process is not None:
            # Native libraries may write diagnostics. Discard them instead of making
            # a persistent log that could include input file paths.
            self.process.readAllStandardError()

    def _process_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self._error = "The local worker could not start. Reinstall the app or its dependencies."
            self._finish(False)

    def _process_finished(self, code: int, _status: QProcess.ExitStatus) -> None:
        self._read_output()
        self._finish(code == 0 and self._result and not self._error)

    def _finish(self, successful: bool) -> None:
        if self.process is None:
            return
        process, self.process = self.process, None
        process.deleteLater()
        if self._cancelled:
            self.finished.emit(False, "Cancelled. Your previous text is still here.")
        elif successful:
            self.finished.emit(True, "")
        else:
            self.finished.emit(False, self._error or "The local worker stopped unexpectedly.")
