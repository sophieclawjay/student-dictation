# Verification record

2026-10-17. Synthetic audio only. No student recordings.

## Observed checks

- M5 Max, Python 3.12.13: faster-whisper 1.2.1 / CTranslate2 4.8.3 / PyAV 18.1.0, CPU int8 inference passed on English synthetic speech.
- Application worker explicitly downloaded the base model into a separate writable test directory and emitted a successful JSON result.
- Application worker then performed cached-only inference with offline environment settings and emitted the complete English transcript. Evidence: `output/fleet-app-model-download.jsonl` and `output/fleet-app-transcription.jsonl`.
- Actual Qt MainWindow and QProcess worker completed English base-model inference and inserted the result into the editor, returning to idle. Evidence: `output/fleet-gui-inference.json`.
- Default large-v3-turbo model downloaded and processed synthetic English, Korean and Vietnamese through the application worker. Per-file elapsed time including process startup and model loading was 3.19, 3.35 and 3.38 seconds on the M5 Max. These are short synthetic fixtures, not hardware recommendations or benchmark averages. Vietnamese retained the same word error observed with MLX. Evidence: `output/fleet-app-turbo-multilingual.jsonl`.
- Base-model Spanish speech translated into English through the application worker. Evidence: `output/fleet-app-translation.jsonl`. This verifies task execution, not translation quality across languages.
- Desktop window rendered on M5 Max, enumerated microphone choices and was visually inspected from its captured window image. No microphone recording or global key injection was exercised by this check.
- 41 automated tests passed independently on M5 Max; local lint passed. Tests cover task restrictions, offline configuration, PCM limits, audio overflow, worker protocol and cancellation, parent-process exit, editor preservation and clipboard changes.
- PyInstaller built the Apple Silicon macOS app. Frozen app dependency smoke passed. Real audio inference through its bundled worker passed with exit code zero and empty stderr after adding early multiprocessing freeze support. Evidence: `output/mac-frozen-smoke.json` and `output/fleet-frozen-worker-inference.jsonl`.
- Mac development archive produced: `output/student-dictation-darwin-arm64.zip`. Models are separate downloads. This archive is not a signed/notarized student installer.
- Final source passed 43 tests and lint. GitHub-hosted macOS ARM64 and Windows X64 runners both passed tests, source smoke, native packaging and frozen application smoke in [run 39020644763](https://github.com/sophieclawjay/student-dictation/actions/runs/39020644763). Both produced development archives. Windows CI verifies startup and dependencies, not actual microphone input or keyboard permissions.
- The local Mac bundle passed `codesign --verify --deep --strict`; its signature is an ad-hoc development signature, not a Developer ID/notarized distribution.
- Existing fleet MLX Whisper large-v3-turbo processed English, Korean and Vietnamese synthetic speech. Vietnamese had a word error. This is separate backend evidence, not an application benchmark.
- M5 Pro Qwen3.8 27B performed text-only architecture review. Raw response is retained; recommendations were checked rather than accepted as factual claims.

## Release checks still required

- Installed app microphone access on macOS and Windows, including denied permission and disconnected input devices.
- Global shortcuts and paste in actual student applications, including clipboard changes and target focus.
- Clean-machine packaging and dependency-license review; macOS signing/notarization and Windows signing decisions.
- Representative low-memory Windows laptop and Intel Mac performance. CPU int8 on the M5 Max does not establish speed on those machines.
- Accuracy comparison using Jay's actual VoiceInk engine/model/settings and consented samples, including names, numbers, accents and mixed languages. No 99% or parity claim is made.
- Translation quality against human-reviewed bilingual reference text. Whisper supports English output for its speech translation task; other target languages need an additional engine.

Future checks should record their actual commands, environment and outcomes. The repository's current pre-release remains separate from a broadly validated student installer.
