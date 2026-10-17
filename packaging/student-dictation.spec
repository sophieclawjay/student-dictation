# Build on the target OS: python -m PyInstaller packaging/student-dictation.spec --noconfirm
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata

project = Path(SPECPATH).parent
datas = [(str(project / "LICENSE"), "licenses"),
         (str(project / "THIRD_PARTY.md"), "licenses")]
notices = project / "build" / "third-party-licenses"
if notices.is_dir():
    datas.append((str(notices), "licenses/third-party"))
binaries = []
hiddenimports = []
for package in ("faster_whisper", "ctranslate2", "av", "tokenizers", "onnxruntime"):
    package_datas, package_binaries, package_imports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_imports
for distribution in ("faster-whisper", "huggingface-hub", "sounddevice", "pynput"):
    datas += copy_metadata(distribution)
if sys.platform == "darwin":
    hiddenimports += ["pynput.keyboard._darwin", "pynput.mouse._darwin"]
elif sys.platform == "win32":
    hiddenimports += ["pynput.keyboard._win32", "pynput.mouse._win32"]

a = Analysis([str(project / "packaging" / "launch.py")],
             pathex=[str(project / "src")],
             binaries=binaries, datas=datas, hiddenimports=hiddenimports,
             hookspath=[], runtime_hooks=[],
             excludes=["tkinter", "matplotlib", "IPython", "pytest", "PyQt5", "PyQt6"])
pyz = PYZ(a.pure)
desktop = EXE(pyz, a.scripts, [], exclude_binaries=True, name="StudentDictation",
              debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
              console=False, disable_windowed_traceback=False)
# A separate console-enabled worker preserves standard pipes in Windows frozen
# builds. The desktop invokes it with QProcess, which creates no console window.
worker = EXE(pyz, a.scripts, [], exclude_binaries=True, name="StudentDictationWorker",
             debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
             console=True, hide_console="hide-early")
collection = COLLECT(desktop, worker, a.binaries, a.datas,
                     strip=False, upx=False, name="StudentDictation")
if sys.platform == "darwin":
    bundle = BUNDLE(collection, name="Student Dictation.app",
                    bundle_identifier="org.studentdictation.desktop", version="0.1.0",
                    info_plist={
                        "NSPrincipalClass": "NSApplication",
                        "NSMicrophoneUsageDescription":
                            "Record your speech for private on-device dictation.",
                        "NSHighResolutionCapable": True,
                    })
