# Student Dictation

A local desktop app for dictation and speech translation on macOS and Windows.
Record a microphone or import audio, review the transcript, then copy, save, or
paste it into another app. Speech recognition runs on your computer using
[faster-whisper](https://github.com/SYSTRAN/faster-whisper) and CTranslate2 CPU int8.

**Version 0.1.0 is a pre-release.** Source use and development builds are available.
Microphone permissions, global shortcuts, and paste behavior still need end-to-end
testing on each target OS and hardware configuration. Windows hardware testing is
pending. There is no claimed accuracy or feature parity with commercial dictation
apps. Speech and translation output need review, especially names and noisy audio.

## Run from source

Use Python 3.12 for the simplest supported setup. Python 3.11 to 3.13 is supported
by the project metadata; dependency wheel availability varies by platform.
Use 64-bit Windows on x86-64, or a supported Intel / Apple Silicon Mac. This app
uses CPU inference on both platforms. Apple Metal and CUDA acceleration are outside
this release.

macOS:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
student-dictation
```

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\python.exe -m student_dictation
```

PortAudio is included in the sounddevice wheels on macOS and Windows. Source
installations of sounddevice may need a separate PortAudio installation. PyAV
handles supported audio formats; installing a separate `ffmpeg` executable is
unnecessary for the wheel-based setup. `av<19` is deliberate: faster-whisper 1.2.1
passes an audio-decoder argument removed in PyAV 19. PyAV 18 has been exercised
with actual local inference during this project's validation.

## First recording

1. Choose a model. **large-v3-turbo** is the default for multilingual transcription.
   **base** is a smaller download for trying the workflow on modest hardware.
2. Turn off **Offline mode**, then choose **Download model** and confirm the source
   and approximate download size. This downloads model files from Hugging Face.
   No recording or transcript is sent. Allow extra disk space for partial files
   during installation. Model weights are stored at their upstream precision;
   int8 refers to inference computation.
3. When installation finishes, Offline mode turns back on automatically. Choose
   your input language or leave **Auto detect** selected. Language selection often
   helps short recordings.
4. Choose **Record**, grant microphone permission if needed, speak, then choose
   **Stop & transcribe**. Recordings stop automatically after ten minutes. The
   microphone level meter helps confirm input. Import supports common WAV, MP3,
   M4A, FLAC, OGG, and other audio formats handled by PyAV.
5. Review the result in the editable text area. New results append below existing
   text. **Copy all** changes your system clipboard. **Save text** writes a UTF-8
   file only after you choose a destination. **Clear** supports Undo while open.

Model downloads are roughly 150 MB (base), 490 MB (small), 1.6 GB (large-v3-turbo),
and 3.1 GB (large-v3). These approximate download sizes exclude runtime memory.
Large models need several GB of RAM and may process slower than real time on CPU.
The app loads a fresh model process for each operation to allow reliable hard
cancellation and release model memory afterward. Model load latency is expected.

## Translate speech into English

Choose **Translate speech into English**. The UI switches from turbo to
**large-v3**, which requires its own download. **small** and **base** also support
translation. The language setting describes the **input speech**. Whisper's
translation task produces English text only; it does not produce arbitrary target
languages. Transcription preserves the spoken language.

Whisper turbo is not trained for translation. The app prevents using it for the
translation task. Cantonese's dedicated language token requires a large-v3 model.
Accuracy varies across languages, accents, microphones, and noise conditions.

## Optional keyboard features

Both features start off on every app launch and require an explicit confirmation.

- **Global record shortcut:** Control + Alt + Space starts or stops recording while
  another app is active. On Mac use Control + Option + Space. The app must stay
  open, and the selected model must already be installed. During recognition the
  shortcut has no effect. Some OS shortcuts or accessibility tools may conflict.
- **Paste to other apps:** Enable this feature, then choose **Paste in 3 seconds**.
  The app copies all editor text, starts a visible countdown, and sends one paste
  shortcut. Focus the intended destination during the countdown. Cancel stops the
  pending paste. If the app still has focus or the clipboard changes, paste is
  cancelled. No paste runs automatically after transcription.

macOS may require **System Settings > Privacy & Security > Microphone** for audio,
and **Accessibility / Input Monitoring** for keyboard features. Source runs may
need permission for your terminal or Python interpreter. Restart after granting
keyboard permissions. Windows requires microphone access for desktop apps.
Pasting into elevated Windows applications may be blocked. Clipboard managers,
remote desktops, and secure input fields can affect clipboard and shortcut use.

## Privacy and offline behavior

- No cloud speech API, account, analytics, telemetry code, transcript database, or
  automatic transcript history is included. There is no AI writing cleanup service.
- Every recognition job sets Hugging Face offline flags and loads an absolute local
  model path with `local_files_only=True`. A downloaded tokenizer is required so
  missing tokenizer files cannot silently trigger a download.
- The separate **Download model** action is the only network operation in the app.
  It requires Offline mode to be off and a confirmation. Hugging Face and its file
  delivery providers receive ordinary connection information, including your IP.
  Hub telemetry and implicit authentication are disabled. Downloads can be cancelled
  and resumed. No credentials are required for the supplied public models.
- Microphone audio stays in RAM while recording. After Stop, a private temporary WAV
  passes audio to the local worker. It is removed after completion, cancellation, or
  normal exit. If the app crashes, the WAV can remain until the next normal launch,
  when stale recording folders are removed. Deletion is ordinary file deletion.
  OS swap, backups, crash capture, and filesystem recovery are outside app control.
- Imported audio remains in its original file. Text remains in editor memory until
  cleared or closed. Copy, Save, and Paste explicitly share text with the destination
  you choose. Your OS clipboard or destination app may retain or sync it. Exiting
  Student Dictation does not clear the system clipboard.
- The app writes model files, their download metadata, and an instance lock in its
  per-user Qt cache folder. Use **Open model folder** to find or remove a model while
  idle. No audio or transcript is written to a diagnostic log by the app.

The app relies on your operating system's access controls and ordinary file
deletion. Review output before sharing sensitive or student information.

## Cancellation and recovery

**Cancel** discards an active microphone recording or kills the separate recognition
or download worker. It leaves the previous editor text intact. The desktop stays
responsive during model loading, decoding, and downloading. Audio overflow and a
disconnected microphone produce an error instead of a silently incomplete result.

If a download fails, turn off Offline mode and choose Download model again to resume.
If a downloaded model is corrupt, choose **Repair model** while online. A complete
download marker plus required files controls readiness; corruption that preserves
file sizes may only become visible when the inference engine loads the files. If
repair does not help, close the app, remove that model's directory, and download it
again. Disk space, network errors, unsupported input, memory exhaustion, or missing
native dependencies are reported in the status area. Existing text stays intact.

## Tests and packaging

```sh
python -m pip install -e ".[dev,build]"
python -m ruff check .
python -m pytest -q
python -m student_dictation --smoke --smoke-report build/source-smoke.json
python packaging/collect_licenses.py
python -m PyInstaller packaging/student-dictation.spec --noconfirm
python packaging/archive.py
```

For a headless smoke check set `QT_QPA_PLATFORM=offscreen`. Add
`--screenshot build/preview.png` to save the rendered window. Smoke checks import
the inference dependencies and report supported CPU compute types; they do not
download a model, exercise a real microphone, or measure recognition accuracy.
Automated tests use fake inference backends and subprocess fixtures to cover task
policy, offline flags, audio limits, successful and failed jobs, cancellation, and
editor preservation. Real speech / translation validation is a separate check.

Build on the operating system and CPU architecture you plan to distribute to.
Cross-compiling between Windows and macOS is unsupported. PyInstaller produces a
directory bundle with a GUI executable, a separate pipe-enabled worker, shared
libraries, and license texts. Keep the entire directory / `.app` together.
Models are downloaded at first use and excluded from archives. The macOS bundle
includes `NSMicrophoneUsageDescription` for the permission prompt.

`.github/workflows/build.yml` runs tests and builds native macOS and Windows
development archives on pushes to `main`, version tags, PRs, and manual dispatch.
It smoke-checks the frozen app and uploads complete zip files plus smoke reports.
CI artifacts are unsigned. macOS signing / notarization and Windows signing /
installer packaging are release work. Test OS permissions, actual audio, keyboard
hooks, cancellation, and clipboard behavior on target machines before student use.

## License

The project's source is [MIT licensed](LICENSE). Binary dependencies and separately
downloaded models retain their own licenses. Read [THIRD_PARTY.md](THIRD_PARTY.md)
for the dependency inventory, Qt / pynput LGPL obligations, and binary distribution
notes. Keep the collected license texts with any build you redistribute.
