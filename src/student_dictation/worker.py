"""Short-lived inference/download process, killed safely when the user cancels.

Only newline-delimited JSON is written to stdout. The desktop process retains
the previous transcript until a successful final result arrives.
"""

from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path
from typing import Any

from .core import apply_private_environment, mark_model_ready, model_ready, validate_options


def emit(event_type: str, **payload: Any) -> None:
    print(json.dumps({"type": event_type, **payload}, ensure_ascii=False), flush=True)


def exit_when_parent_closes_pipe() -> None:
    """Avoid an orphan model process if the desktop app crashes or is killed."""
    try:
        sys.stdin.read(1)
    finally:
        os._exit(2)


def download(request: dict[str, Any]) -> None:
    model = validate_options(request["model"], "transcribe", None)
    destination = Path(request["directory"])
    destination.mkdir(parents=True, exist_ok=True)
    emit("status", message="Downloading model files. You can cancel and resume later.")
    from huggingface_hub import snapshot_download

    snapshot_download(
        repo_id=model.repository,
        local_dir=str(destination),
        allow_patterns=[
            "config.json",
            "preprocessor_config.json",
            "model.bin",
            "tokenizer.json",
            "vocabulary.*",
        ],
        token=False,
        max_workers=2,
    )
    mark_model_ready(destination, model)
    emit("result", kind="download")


def transcribe(request: dict[str, Any]) -> None:
    validate_options(request["model"], request["task"], request.get("language"))
    directory = Path(request["directory"])
    if not model_ready(directory):
        raise ValueError("This model is not installed completely. Download it first.")
    audio = Path(request["audio"])
    if not audio.is_file():
        raise ValueError("The audio file is unavailable. Choose it again.")
    emit("status", message="Loading local model on CPU. Large models can take a moment.")
    from faster_whisper import WhisperModel

    model = WhisperModel(
        str(directory),
        device="cpu",
        compute_type="int8",
        local_files_only=True,
        cpu_threads=max(1, min(8, (os.cpu_count() or 4) - 1)),
        num_workers=1,
    )
    emit("status", message="Recognizing speech locally...")
    segments, info = model.transcribe(
        str(audio),
        language=request.get("language"),
        task=request["task"],
        beam_size=5,
        vad_filter=True,
        condition_on_previous_text=False,
    )
    text_parts: list[str] = []
    for segment in segments:
        text_parts.append(segment.text)
        duration = info.duration or 0
        percent = min(99, int(100 * segment.end / duration)) if duration else 0
        emit("progress", value=percent)
    # Do not stream partial text to the editor: cancellation leaves earlier work intact.
    emit(
        "result",
        kind="transcription",
        text="".join(text_parts).strip(),
        language=info.language,
        probability=info.language_probability,
    )


def main() -> int:
    try:
        request = json.loads(sys.stdin.readline())
        operation = request.get("operation")
        if operation not in {"download", "transcribe"}:
            raise ValueError("Unknown worker operation.")
        threading.Thread(target=exit_when_parent_closes_pipe, daemon=True).start()
        apply_private_environment(offline=operation != "download")
        if operation == "download":
            download(request)
        else:
            transcribe(request)
        return 0
    except Exception as exc:
        # The desktop keeps this in memory only. Never dump a request or audio data.
        emit("error", message=f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
