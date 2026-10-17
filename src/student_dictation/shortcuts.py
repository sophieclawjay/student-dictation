"""Optional keyboard access. Imported only after the user opts in."""

from __future__ import annotations

import sys

from PySide6.QtCore import QObject, Signal


class GlobalShortcut(QObject):
    activated = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.listener = None

    def start(self) -> None:
        from pynput import keyboard

        if sys.platform == "darwin" and not keyboard.Listener.IS_TRUSTED:
            raise RuntimeError(
                "macOS keyboard access is unavailable. Allow this app under System Settings > "
                "Privacy & Security > Accessibility and Input Monitoring, then restart the app."
            )
        self.listener = keyboard.GlobalHotKeys({"<ctrl>+<alt>+<space>": self.activated.emit})
        self.listener.start()

    def stop(self) -> None:
        if self.listener is not None:
            self.listener.stop()
            self.listener = None


def paste_clipboard() -> None:
    """Send one paste keystroke to the application the user has focused."""
    from pynput import keyboard

    if sys.platform == "darwin" and not keyboard.Listener.IS_TRUSTED:
        raise RuntimeError("Allow Accessibility access for this app, then try again.")
    controller = keyboard.Controller()
    modifier = keyboard.Key.cmd if sys.platform == "darwin" else keyboard.Key.ctrl
    with controller.pressed(modifier):
        controller.press("v")
        controller.release("v")
