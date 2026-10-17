"""Module and installed command entry points, including the isolated worker."""

from __future__ import annotations

import argparse
import json
import multiprocessing
import shutil
import sys
from pathlib import Path


def main() -> int:
    if "--worker" in sys.argv:
        from .worker import main as worker_main

        return worker_main()

    parser = argparse.ArgumentParser(description="Local desktop speech recognition")
    parser.add_argument("--smoke", action="store_true", help="Open briefly and check dependencies")
    parser.add_argument("--smoke-report", type=Path, help="Write smoke-check JSON to this file")
    parser.add_argument("--screenshot", type=Path, help="Save a screenshot during a smoke check")
    args = parser.parse_args()

    from PySide6.QtCore import QLockFile, QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox

    from .core import apply_private_environment
    from .jobs import worker_command
    from .ui import MainWindow, apply_style, cache_directory

    apply_private_environment(offline=True)
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Student Dictation")
    app.setOrganizationName("StudentDictation")
    app.setApplicationVersion("0.1.0")
    apply_style(app)
    cache = cache_directory()
    lock = QLockFile(str(cache / "instance.lock"))
    if not args.smoke:
        if not lock.tryLock(0):
            QMessageBox.information(None, "Student Dictation", "Student Dictation is already open.")
            return 0
        # A crash can leave temporary microphone audio. The single-instance lock
        # ensures we never remove audio belonging to another running session.
        transient = cache / "transient"
        if transient.exists():
            for directory in transient.glob("recording-*"):
                if directory.is_dir() and not directory.is_symlink():
                    shutil.rmtree(directory, ignore_errors=True)
    window = MainWindow(cache)
    window.show()
    if args.smoke:
        import av
        import ctranslate2
        import faster_whisper
        import sounddevice

        command = worker_command()
        report = {
            "status": "ok",
            "version": "0.1.0",
            "frozen": bool(getattr(sys, "frozen", False)),
            "cache": str(cache),
            "worker": command,
            "worker_exists": Path(command[0]).is_file(),
            "faster_whisper": faster_whisper.__version__,
            "ctranslate2": ctranslate2.__version__,
            "av": av.__version__,
            "sounddevice": sounddevice.__version__,
            "cpu_compute_types": sorted(ctranslate2.get_supported_compute_types("cpu")),
        }

        def finish_smoke() -> None:
            if args.screenshot:
                args.screenshot.parent.mkdir(parents=True, exist_ok=True)
                window.grab().save(str(args.screenshot))
            if args.smoke_report:
                args.smoke_report.parent.mkdir(parents=True, exist_ok=True)
                args.smoke_report.write_text(json.dumps(report, indent=2), encoding="utf-8")
            if sys.stdout is not None:
                print(json.dumps(report))
            app.quit()

        QTimer.singleShot(500, finish_smoke)
    result = app.exec()
    if not args.smoke:
        lock.unlock()
    return result


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
