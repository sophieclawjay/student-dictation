"""Bounded microphone recording. Audio stays in RAM until Stop is pressed."""

from __future__ import annotations

import threading
import wave
from pathlib import Path

import numpy as np


class RecordingBuffer:
    def __init__(self, samplerate: int, max_seconds: int = 600):
        self.samplerate = samplerate
        self.maximum = samplerate * max_seconds
        self.frames = 0
        self.chunks: list[np.ndarray] = []
        self.error = ""
        self.full = False
        self.level = 0.0
        self.lock = threading.Lock()

    def append(self, audio: np.ndarray, status: str = "") -> bool:
        with self.lock:
            if status:
                self.error = "Audio input lost samples. Check your microphone and try again."
                return False
            remaining = self.maximum - self.frames
            chunk = np.asarray(audio[:remaining], dtype=np.float32).reshape(-1).copy()
            if chunk.size:
                self.chunks.append(chunk)
                self.frames += chunk.size
                self.level = float(np.sqrt(np.mean(chunk * chunk)))
            self.full = self.frames >= self.maximum
            return not self.full

    @property
    def seconds(self) -> float:
        return self.frames / self.samplerate

    def write_wav(self, destination: Path) -> None:
        with self.lock:
            if self.error:
                raise RuntimeError(self.error)
            if self.frames < self.samplerate // 4:
                raise ValueError("Record at least a quarter second of audio.")
            with wave.open(str(destination), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(self.samplerate)
                for chunk in self.chunks:
                    pcm = (np.clip(chunk, -1, 1) * 32767).astype("<i2")
                    output.writeframesraw(pcm.tobytes())

    def clear(self) -> None:
        with self.lock:
            self.chunks.clear()
            self.frames = 0
            self.level = 0.0


class Recorder:
    def __init__(self):
        self.stream = None
        self.buffer: RecordingBuffer | None = None

    @staticmethod
    def devices() -> list[tuple[int, str]]:
        import sounddevice as sd

        devices = sd.query_devices()
        hosts = sd.query_hostapis()
        return [
            (i, f"{d['name']} ({hosts[d['hostapi']]['name']})")
            for i, d in enumerate(devices)
            if d["max_input_channels"] > 0
        ]

    def start(self, device: int | None = None) -> None:
        if self.stream is not None:
            raise RuntimeError("The microphone is already recording.")
        import sounddevice as sd

        info = sd.query_devices(device, "input")
        samplerate = int(info["default_samplerate"])
        buffer = RecordingBuffer(samplerate)
        self.buffer = buffer

        def callback(indata, _frames, _time, status):
            if not buffer.append(indata, str(status) if status else ""):
                raise sd.CallbackStop

        try:
            stream = sd.InputStream(
                device=device,
                samplerate=samplerate,
                channels=1,
                dtype="float32",
                blocksize=0,
                callback=callback,
            )
        except Exception:
            self.buffer = None
            raise
        try:
            stream.start()
        except Exception:
            stream.close()
            self.buffer = None
            raise
        self.stream = stream

    def stop(self) -> RecordingBuffer:
        if self.stream is None or self.buffer is None:
            raise RuntimeError("The microphone is not recording.")
        stream, self.stream = self.stream, None
        result, self.buffer = self.buffer, None
        try:
            try:
                stream.stop()
            finally:
                stream.close()
        except Exception:
            result.clear()
            raise
        return result

    def discard(self) -> None:
        if self.stream is not None:
            try:
                self.stop().clear()
            except Exception:
                self.stream = None
                if self.buffer is not None:
                    self.buffer.clear()
                    self.buffer = None
        elif self.buffer is not None:
            self.buffer.clear()
            self.buffer = None
