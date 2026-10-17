"""Desktop UI. Recognition happens in a killable child process."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QStandardPaths, Qt, QTimer, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices, QFont, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .audio import Recorder
from .core import LANGUAGES, MODEL_BY_KEY, MODELS, model_ready, validate_options
from .jobs import JobRunner


def cache_directory() -> Path:
    directory = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation))
    directory.mkdir(parents=True, exist_ok=True)
    return directory.resolve()


class MainWindow(QMainWindow):
    def __init__(self, cache: Path | None = None):
        super().__init__()
        self.setWindowTitle("Student Dictation")
        self.resize(930, 860)
        self.setMinimumSize(730, 620)
        self.cache = (cache or cache_directory()).resolve()
        self.cache.mkdir(parents=True, exist_ok=True)
        self.state = "idle"
        self.recorder = Recorder()
        self.runner = JobRunner(self)
        self.runner.event.connect(self._job_event)
        self.runner.finished.connect(self._job_finished)
        self.recording_file: tempfile.TemporaryDirectory | None = None
        self.pending_result: dict | None = None
        self.shortcut = None
        self.paste_seconds = 0
        self.paste_text = ""

        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self._recording_tick)
        self.paste_timer = QTimer(self)
        self.paste_timer.setInterval(1000)
        self.paste_timer.timeout.connect(self._paste_tick)
        self._build_ui()
        self._refresh_devices()
        self._update_controls()

    def _build_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 26, 30, 24)
        layout.setSpacing(16)

        top = QHBoxLayout()
        title_box = QVBoxLayout()
        eyebrow = QLabel("PRIVATE SPEECH TO TEXT")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Student Dictation")
        title.setObjectName("title")
        subtitle = QLabel("Dictate in your language or translate speech into English.")
        subtitle.setWordWrap(True)
        title_box.addWidget(eyebrow)
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        top.addLayout(title_box, 1)
        privacy = QPushButton("Privacy && help")
        privacy.clicked.connect(self._privacy)
        top.addWidget(privacy, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(top)

        recognition = QGroupBox("1   Choose recognition settings")
        recognition_layout = QVBoxLayout(recognition)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(10)
        self.model = QComboBox()
        self.model.setAccessibleName("Recognition model")
        for spec in MODELS:
            self.model.addItem(f"{spec.label}  ({spec.download_size})", spec.key)
        self.task = QComboBox()
        self.task.setAccessibleName("Recognition task")
        self.task.addItem("Transcribe in the spoken language", "transcribe")
        self.task.addItem("Translate speech into English", "translate")
        self.language = QComboBox()
        self.language.setAccessibleName("Input speech language")
        self.language.addItem("Auto detect", None)
        for code, label in sorted(LANGUAGES.items(), key=lambda item: item[1]):
            self.language.addItem(label, code)
        form.addRow("Model", self.model)
        form.addRow("Task", self.task)
        form.addRow("Input language", self.language)
        recognition_layout.addLayout(form)
        self.model_note = QLabel()
        self.model_note.setWordWrap(True)
        self.model_note.setObjectName("muted")
        recognition_layout.addWidget(self.model_note)
        download_row = QHBoxLayout()
        self.offline = QCheckBox("Offline mode")
        self.offline.setChecked(True)
        self.offline.setToolTip("Blocks model downloads. Recognition always uses local files.")
        self.download = QPushButton("Download model")
        self.download.clicked.connect(self._download_model)
        cache_button = QPushButton("Open model folder")
        cache_button.clicked.connect(self._open_cache)
        download_row.addWidget(self.offline)
        download_row.addStretch()
        download_row.addWidget(cache_button)
        download_row.addWidget(self.download)
        recognition_layout.addLayout(download_row)
        layout.addWidget(recognition)

        capture = QGroupBox("2   Record or import audio")
        capture_layout = QVBoxLayout(capture)
        mic_row = QHBoxLayout()
        mic_row.addWidget(QLabel("Microphone"))
        self.microphone = QComboBox()
        self.microphone.setAccessibleName("Microphone")
        mic_row.addWidget(self.microphone, 1)
        self.refresh_mics = QPushButton("Refresh")
        self.refresh_mics.clicked.connect(self._refresh_devices)
        mic_row.addWidget(self.refresh_mics)
        capture_layout.addLayout(mic_row)
        capture_buttons = QHBoxLayout()
        self.record = QPushButton("Record")
        self.record.setObjectName("primary")
        self.record.clicked.connect(self._record_clicked)
        self.import_audio = QPushButton("Import audio...")
        self.import_audio.clicked.connect(self._import_audio)
        self.cancel = QPushButton("Cancel")
        self.cancel.clicked.connect(self._cancel)
        self.record_time = QLabel("00:00 / 10:00")
        self.record_time.setObjectName("muted")
        self.level = QProgressBar()
        self.level.setAccessibleName("Microphone level")
        self.level.setRange(0, 100)
        self.level.setValue(0)
        self.level.setTextVisible(False)
        self.level.setFixedWidth(100)
        self.level.setFixedHeight(10)
        capture_buttons.addWidget(self.record)
        capture_buttons.addWidget(self.import_audio)
        capture_buttons.addWidget(self.cancel)
        capture_buttons.addStretch()
        capture_buttons.addWidget(self.record_time)
        capture_buttons.addWidget(self.level)
        capture_layout.addLayout(capture_buttons)
        self.status = QLabel("Choose a model to get started. No audio leaves your computer.")
        self.status.setWordWrap(True)
        self.status.setAccessibleName("Application status")
        capture_layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setAccessibleName("Recognition progress")
        self.progress.setFixedHeight(6)
        self.progress.setTextVisible(False)
        self.progress.hide()
        capture_layout.addWidget(self.progress)
        layout.addWidget(capture)

        transcript = QGroupBox("3   Review and use your text")
        transcript_layout = QVBoxLayout(transcript)
        self.editor = QTextEdit()
        self.editor.setAccessibleName("Transcript editor")
        self.editor.setAcceptRichText(False)
        self.editor.setMinimumHeight(165)
        self.editor.setPlaceholderText(
            "Your transcript appears here. New recordings are added below existing text.\n"
            "Review names, punctuation, and any translation before using the text."
        )
        self.editor.textChanged.connect(self._update_text_controls)
        transcript_layout.addWidget(self.editor, 1)
        text_buttons = QHBoxLayout()
        self.copy = QPushButton("Copy all")
        self.copy.setObjectName("primary")
        self.copy.clicked.connect(self._copy_text)
        self.paste = QPushButton("Paste in 3 seconds")
        self.paste.clicked.connect(self._schedule_paste)
        self.save = QPushButton("Save text...")
        self.save.clicked.connect(self._save_text)
        self.clear = QPushButton("Clear")
        self.clear.clicked.connect(self._clear_text)
        text_buttons.addWidget(self.copy)
        text_buttons.addWidget(self.paste)
        text_buttons.addStretch()
        text_buttons.addWidget(self.save)
        text_buttons.addWidget(self.clear)
        transcript_layout.addLayout(text_buttons)
        layout.addWidget(transcript, 1)

        optional = QHBoxLayout()
        self.enable_shortcut = QCheckBox("Enable global record shortcut")
        self.enable_shortcut.setToolTip("Control + Alt + Space. On Mac: Control + Option + Space.")
        self.enable_shortcut.toggled.connect(self._toggle_shortcut)
        self.enable_paste = QCheckBox("Enable paste to other apps")
        self.enable_paste.toggled.connect(self._toggle_paste)
        optional.addWidget(self.enable_shortcut)
        optional.addStretch()
        optional.addWidget(self.enable_paste)
        layout.addLayout(optional)
        footnote = QLabel(
            "Local CPU processing  ·  No account  ·  No automatic transcript history\n"
            "Audio and text stay here until you copy, save, or paste them."
        )
        footnote.setObjectName("muted")
        footnote.setWordWrap(True)
        layout.addWidget(footnote)
        scroll.setWidget(page)
        self.setCentralWidget(scroll)
        self.model.currentIndexChanged.connect(self._settings_changed)
        self.task.currentIndexChanged.connect(self._task_changed)
        self.language.currentIndexChanged.connect(self._settings_changed)
        self.offline.toggled.connect(self._settings_changed)

    def _settings_changed(self, *_args) -> None:
        self._update_controls()

    def _task_changed(self, *_args) -> None:
        translating = self.task.currentData() == "translate"
        turbo = self.model.model().item(0)
        turbo.setEnabled(not translating)
        if translating and self.model.currentData() == "large-v3-turbo":
            self.model.setCurrentIndex(1)
            self._set_status("English translation uses large-v3. Install it once before recording.")
        self._update_controls()

    def _model_directory(self) -> Path:
        return self.cache / "models" / self.model.currentData()

    def _valid_model(self) -> bool:
        try:
            validate_options(
                self.model.currentData(), self.task.currentData(), self.language.currentData()
            )
            return True
        except ValueError:
            return False

    def _update_controls(self) -> None:
        if not hasattr(self, "model"):
            return
        idle = self.state == "idle"
        ready = model_ready(self._model_directory())
        valid = self._valid_model()
        for widget in (
            self.model,
            self.task,
            self.language,
            self.offline,
            self.microphone,
            self.refresh_mics,
            self.enable_shortcut,
            self.enable_paste,
        ):
            widget.setEnabled(idle)
        self.download.setEnabled(idle and not self.offline.isChecked())
        self.download.setText("Repair model" if ready else "Download model")
        self.record.setEnabled((idle and ready and valid) or self.state == "recording")
        self.record.setText("Stop && transcribe" if self.state == "recording" else "Record")
        self.import_audio.setEnabled(idle and ready and valid)
        self.cancel.setEnabled(not idle)
        self.editor.setReadOnly(not idle)
        spec = MODEL_BY_KEY[self.model.currentData()]
        if not valid:
            try:
                validate_options(spec.key, self.task.currentData(), self.language.currentData())
            except ValueError as exc:
                self.model_note.setText(str(exc))
        elif ready:
            self.model_note.setText(
                "Installed and ready offline. Larger models use more memory and take longer on CPU."
            )
        elif self.offline.isChecked():
            self.model_note.setText(
                f"Model not installed ({spec.download_size}). Turn off Offline mode, then choose "
                "Download model. Recognition runs offline after installation."
            )
        else:
            self.model_note.setText(
                f"Model not installed. Download {spec.download_size} from Hugging Face once. "
                "No audio is sent with the download."
            )
        self._update_text_controls()

    def _update_text_controls(self) -> None:
        if not hasattr(self, "copy"):
            return
        enabled = self.state == "idle" and bool(self.editor.toPlainText().strip())
        for widget in (self.copy, self.save, self.clear):
            widget.setEnabled(enabled)
        self.paste.setEnabled(enabled and self.enable_paste.isChecked())

    def _set_status(self, message: str, error: bool = False) -> None:
        self.status.setText(message)
        self.status.setStyleSheet("color: #a22a22;" if error else "color: #17483f;")

    def _refresh_devices(self) -> None:
        selected = self.microphone.currentData()
        self.microphone.clear()
        self.microphone.addItem("System default input", None)
        try:
            for device, name in self.recorder.devices():
                self.microphone.addItem(name, device)
            index = self.microphone.findData(selected)
            self.microphone.setCurrentIndex(max(0, index))
        except Exception:
            self._set_status(
                "Microphone unavailable. Check OS microphone permission, then choose Refresh. "
                "You can still import an audio file.",
                error=True,
            )

    def _download_model(self) -> None:
        if self.state != "idle" or self.offline.isChecked():
            return
        spec = MODEL_BY_KEY[self.model.currentData()]
        answer = QMessageBox.question(
            self,
            "Download model?",
            f"Download {spec.label} ({spec.download_size}) from:\n"
            f"https://huggingface.co/{spec.repository}\n\n"
            "This connects to Hugging Face and its file delivery providers. "
            "They receive normal download connection data, including your IP address. "
            "Your audio and transcript are never uploaded.\n\n"
            f"Files are kept at:\n{self._model_directory()}\n\n"
            "Choose Cancel during a download to stop it. Partial files can be resumed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._start_job(
            {"operation": "download", "model": spec.key, "directory": str(self._model_directory())}
        )

    def _record_clicked(self) -> None:
        if self.state == "recording":
            self._stop_recording()
        elif self.state == "idle" and self.record.isEnabled():
            try:
                self.recorder.start(self.microphone.currentData())
            except Exception as exc:
                self._set_status(
                    "Could not open the microphone. Check OS microphone permission and "
                    f"select an input device. {exc}",
                    error=True,
                )
                return
            self.state = "recording"
            self.record_time.setText("00:00 / 10:00")
            self._set_status("Recording locally. Choose Stop & transcribe when you finish.")
            self.timer.start()
            self._update_controls()

    def _recording_tick(self) -> None:
        buffer = self.recorder.buffer
        if buffer is None:
            return
        seconds = int(buffer.seconds)
        self.record_time.setText(f"{seconds // 60:02d}:{seconds % 60:02d} / 10:00")
        self.level.setValue(min(100, int(buffer.level * 300)))
        if buffer.error:
            message = buffer.error
            self._cancel()
            self._set_status(message, error=True)
        elif buffer.full:
            self._stop_recording()
        elif self.recorder.stream is not None and not self.recorder.stream.active:
            self._cancel()
            self._set_status("The microphone disconnected. Check the input and try again.", True)

    def _stop_recording(self) -> None:
        self.timer.stop()
        self.level.setValue(0)
        buffer = None
        try:
            buffer = self.recorder.stop()
            work = self.cache / "transient"
            work.mkdir(parents=True, exist_ok=True)
            self.recording_file = tempfile.TemporaryDirectory(prefix="recording-", dir=work)
            audio = Path(self.recording_file.name) / "microphone.wav"
            # The temporary directory is private on POSIX; on Windows it inherits
            # the current user's cache permissions.
            os.chmod(self.recording_file.name, 0o700)
            buffer.write_wav(audio)
            os.chmod(audio, 0o600)
            self._transcribe_file(audio)
        except Exception as exc:
            self._cleanup_recording()
            self.state = "idle"
            self._set_status(str(exc), error=True)
            self._update_controls()
        finally:
            if buffer is not None:
                buffer.clear()

    def _import_audio(self) -> None:
        if self.state != "idle":
            return
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Choose audio",
            "",
            "Audio (*.wav *.mp3 *.m4a *.flac *.ogg *.opus *.aac *.mp4);;All files (*)",
        )
        if filename:
            self._transcribe_file(Path(filename))

    def _transcribe_file(self, audio: Path) -> None:
        try:
            validate_options(
                self.model.currentData(), self.task.currentData(), self.language.currentData()
            )
            if not model_ready(self._model_directory()):
                raise ValueError("Install the selected model before recording or importing audio.")
            self._start_job(
                {
                    "operation": "transcribe",
                    "audio": str(audio.resolve()),
                    "model": self.model.currentData(),
                    "task": self.task.currentData(),
                    "language": self.language.currentData(),
                    "directory": str(self._model_directory()),
                }
            )
        except Exception as exc:
            self._cleanup_recording()
            self.state = "idle"
            self._set_status(str(exc), error=True)
            self._update_controls()

    def _start_job(self, request: dict) -> None:
        self.pending_result = None
        self.state = "working"
        self.progress.setRange(0, 0)
        self.progress.show()
        self._set_status("Starting local worker...")
        self._update_controls()
        try:
            self.runner.start(request)
        except Exception as exc:
            self._job_finished(False, str(exc))

    def _job_event(self, event: dict) -> None:
        if event["type"] == "status":
            self._set_status(event["message"])
        elif event["type"] == "progress":
            self.progress.setRange(0, 100)
            self.progress.setValue(event["value"])
        elif event["type"] == "result":
            self.pending_result = event

    def _job_finished(self, success: bool, message: str) -> None:
        self.progress.hide()
        self.state = "idle"
        self._cleanup_recording()
        if success and self.pending_result:
            result = self.pending_result
            if result["kind"] == "download":
                self.offline.setChecked(True)
                self._set_status(
                    "Model installed. Offline mode is on. You can record or import audio."
                )
            elif result["text"]:
                cursor = self.editor.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.End)
                prefix = "\n\n" if self.editor.toPlainText().strip() else ""
                cursor.insertText(prefix + result["text"])
                self.editor.setTextCursor(cursor)
                code = result.get("language", "")
                language = LANGUAGES.get(code, code)
                self._set_status(
                    f"Added to your text. Detected input: {language}. Review before using."
                )
            else:
                self._set_status("No speech was detected. Try speaking closer to the microphone.")
        elif message:
            self._set_status(message, error=not message.startswith("Cancelled"))
        self.pending_result = None
        self._update_controls()

    def _cleanup_recording(self) -> None:
        if self.recording_file is not None:
            self.recording_file.cleanup()
            self.recording_file = None

    def _cancel(self) -> None:
        if self.state == "recording":
            self.timer.stop()
            self.recorder.discard()
            self.level.setValue(0)
            self.state = "idle"
            self._set_status("Recording discarded. Your previous text is still here.")
            self._update_controls()
        elif self.state == "working":
            self._set_status("Cancelling local worker...")
            self.cancel.setEnabled(False)
            self.runner.cancel()
        elif self.state == "pasting":
            self.paste_timer.stop()
            self.paste_text = ""
            self.state = "idle"
            self._set_status("Paste cancelled. The clipboard still contains your copied text.")
            self._update_controls()

    def _copy_text(self) -> None:
        QApplication.clipboard().setText(self.editor.toPlainText())
        self._set_status(
            "Copied. Your system clipboard may sync or retain text in clipboard history."
        )

    def _clear_text(self) -> None:
        cursor = self.editor.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.removeSelectedText()
        self.editor.setTextCursor(cursor)
        self._set_status("Text cleared. Use Undo to restore it while this app is open.")

    def _save_text(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save transcript", "transcript.txt", "Text files (*.txt)"
        )
        if filename:
            try:
                Path(filename).write_text(self.editor.toPlainText(), encoding="utf-8")
                self._set_status("Text saved to the file you chose.")
            except OSError as exc:
                self._set_status(f"Could not save the text: {exc}", True)

    def _toggle_shortcut(self, enabled: bool) -> None:
        if not enabled:
            if self.shortcut is not None:
                self.shortcut.stop()
                self.shortcut = None
            return
        answer = QMessageBox.question(
            self,
            "Enable global shortcut?",
            "Control + Alt + Space will start or stop microphone recording even when another app "
            "is active. On Mac, use Control + Option + Space. The app must stay open.\n\n"
            "This enables an OS keyboard listener. On macOS, grant Accessibility and Input "
            "Monitoring access if requested. This feature resets to off when the app closes.\n\n"
            "No recording starts until you press the shortcut or Record.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            try:
                from .shortcuts import GlobalShortcut

                self.shortcut = GlobalShortcut(self)
                self.shortcut.activated.connect(self._record_clicked)
                self.shortcut.start()
                QTimer.singleShot(500, self._check_shortcut)
                self._set_status("Global shortcut enabled: Control + Alt + Space.")
                return
            except Exception as exc:
                self._set_status(f"Shortcut could not start: {exc}", True)
        self.enable_shortcut.setChecked(False)

    def _check_shortcut(self) -> None:
        if self.shortcut and self.shortcut.listener and not self.shortcut.listener.is_alive():
            self.enable_shortcut.setChecked(False)
            self._set_status("The global shortcut stopped. Check OS keyboard permissions.", True)

    def _toggle_paste(self, enabled: bool) -> None:
        if enabled:
            answer = QMessageBox.question(
                self,
                "Enable paste to other apps?",
                "The Paste in 3 seconds button replaces your clipboard with all text in the "
                "editor, waits three seconds, then sends one paste shortcut to the app you have "
                "focused. Choose your destination during the countdown.\n\n"
                "This needs OS keyboard access and may paste into the wrong field if you focus "
                "another window. You can cancel during the countdown. Nothing is pasted "
                "automatically after recognition. This feature resets to off when the app closes.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self.enable_paste.setChecked(False)
        self._update_text_controls()

    def _schedule_paste(self) -> None:
        if not self.paste.isEnabled():
            return
        self.paste_text = self.editor.toPlainText()
        QApplication.clipboard().setText(self.paste_text)
        self.paste_seconds = 3
        self.state = "pasting"
        self._set_status("Pasting in 3 seconds. Focus the destination field now, or choose Cancel.")
        self._update_controls()
        self.paste_timer.start()

    def _paste_tick(self) -> None:
        self.paste_seconds -= 1
        if self.paste_seconds:
            self._set_status(
                f"Pasting in {self.paste_seconds} seconds. Focus the destination field."
            )
            return
        self.paste_timer.stop()
        try:
            if QApplication.activeWindow() is not None:
                raise RuntimeError("Focus a destination in another app before the countdown ends.")
            if QApplication.clipboard().text() != self.paste_text:
                raise RuntimeError("The clipboard changed during the countdown. Try again.")
            from .shortcuts import paste_clipboard

            paste_clipboard()
            self._set_status("Paste shortcut sent. Check the destination before continuing.")
        except Exception as exc:
            self._set_status(f"Paste cancelled: {exc}", True)
        finally:
            self.paste_text = ""
            self.state = "idle"
            self._update_controls()

    def _open_cache(self) -> None:
        models = self.cache / "models"
        models.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(models)))

    def _privacy(self) -> None:
        QMessageBox.information(
            self,
            "Privacy & help",
            "Recognition uses faster-whisper / CTranslate2 on this computer's CPU with int8 "
            "computation. No cloud speech API, account, telemetry, or automatic transcript "
            "history is included.\n\n"
            "The first model download contacts Hugging Face only after you confirm. "
            "Offline mode blocks model downloads. All recognition uses cached local files.\n\n"
            "Microphone audio stays in memory while recording, with a ten-minute limit. "
            "After Stop, a private temporary WAV is used by the local worker and deleted on "
            "completion, cancellation, or normal app exit. A crash can leave this WAV until "
            "the next launch. Imported audio stays in the file you selected.\n\n"
            "Text stays in the editor until you close or clear it. Copy, Save, and Paste are "
            "explicit actions. Your OS clipboard and destination apps may retain or sync text. "
            "Closing the app does not clear your system clipboard.\n\n"
            "For microphone problems, check OS microphone permission, select an input, and "
            "choose Refresh. For keyboard features, check Accessibility/Input Monitoring on "
            "Mac. Windows cannot paste into some elevated apps.\n\n"
            "Whisper can miss words, invent text in noisy audio, and mistranslate speech. "
            "Review the output. This version produces English translations only. "
            "Turbo supports transcription; use large-v3 for translation.\n\n"
            f"Model and temporary audio folder:\n{self.cache}",
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.state != "idle":
            answer = QMessageBox.question(
                self,
                "Close Student Dictation?",
                "Stop the current operation and close the app?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self.timer.stop()
        self.paste_timer.stop()
        self.recorder.discard()
        if self.shortcut is not None:
            self.shortcut.stop()
        self.runner.shutdown()
        self._cleanup_recording()
        event.accept()


def apply_style(app: QApplication) -> None:
    from PySide6.QtGui import QColor, QPalette

    app.setStyle("Fusion")
    palette = QPalette()
    for role, color in (
        (QPalette.ColorRole.Window, "#f2f5f4"),
        (QPalette.ColorRole.WindowText, "#1b2e30"),
        (QPalette.ColorRole.Base, "#ffffff"),
        (QPalette.ColorRole.Text, "#1b2e30"),
        (QPalette.ColorRole.Button, "#ffffff"),
        (QPalette.ColorRole.ButtonText, "#1b2e30"),
        (QPalette.ColorRole.Highlight, "#176b5b"),
        (QPalette.ColorRole.HighlightedText, "#ffffff"),
    ):
        palette.setColor(role, QColor(color))
    app.setPalette(palette)
    app.setFont(QFont(app.font().family(), 12))
    app.setStyleSheet("""
        QWidget { font-size: 14px; }
        QMainWindow, QScrollArea { background: #f2f5f4; }
        QLabel#title { font-size: 29px; font-weight: 700; color: #173b36; }
        QLabel#eyebrow { font-size: 11px; font-weight: 700; color: #32685d; }
        QLabel#muted { color: #526562; font-size: 12px; }
        QGroupBox { background: white; border: 1px solid #d5e0dc; border-radius: 10px;
                    margin-top: 12px; padding: 18px 14px 12px; font-weight: 600; }
        QGroupBox::title { subcontrol-origin: margin; left: 14px; top: 2px;
                          color: #264b43; padding: 0 5px; }
        QPushButton { background: white; border: 1px solid #c7d5cf; border-radius: 6px;
                      padding: 8px 13px; min-height: 18px; }
        QPushButton:hover { background: #edf5f1; border-color: #628d7b; }
        QPushButton#primary { color: white; background: #176b5b; border-color: #176b5b;
                              font-weight: 600; }
        QPushButton#primary:hover { background: #125244; }
        QPushButton#primary:disabled { color: #82918b; background: #edf1ef;
                                      border-color: #e0e7e3; }
        QPushButton:disabled { color: #82918b; background: #edf1ef; border-color: #e0e7e3; }
        QComboBox { padding: 7px; min-height: 18px; border: 1px solid #c7d5cf;
                    border-radius: 5px; background: white; }
        QComboBox:disabled { color: #82918b; background: #edf1ef; }
        QTextEdit { background: #fbfdfc; border: 1px solid #ccdcd4;
                    border-radius: 6px; padding: 10px; font-size: 16px; }
        QProgressBar { border: 0; border-radius: 3px; background: #e2ece6; }
        QProgressBar::chunk { background: #328f72; border-radius: 3px; }
        QCheckBox { spacing: 7px; }
    """)
