import wave

import numpy as np
import pytest

from student_dictation.audio import Recorder, RecordingBuffer


def test_buffer_stops_at_limit_without_extra_audio(tmp_path):
    buffer = RecordingBuffer(samplerate=100, max_seconds=1)
    assert buffer.append(np.ones((60, 1), dtype=np.float32))
    assert not buffer.append(np.ones((80, 1), dtype=np.float32))
    assert buffer.full
    assert buffer.frames == 100
    assert buffer.seconds == 1
    destination = tmp_path / "recording.wav"
    buffer.write_wav(destination)
    with wave.open(str(destination), "rb") as audio:
        assert audio.getnframes() == 100
        assert audio.getnchannels() == 1
        assert audio.getframerate() == 100
        assert audio.getsampwidth() == 2


def test_overflow_is_an_error_and_prevents_transcribing_partial_audio(tmp_path):
    buffer = RecordingBuffer(16000)
    buffer.append(np.ones((8000, 1), dtype=np.float32))
    assert not buffer.append(np.ones((1000, 1), dtype=np.float32), "input overflow")
    with pytest.raises(RuntimeError, match="lost samples"):
        buffer.write_wav(tmp_path / "partial.wav")
    assert not (tmp_path / "partial.wav").exists()


def test_short_recording_requires_speech_length(tmp_path):
    buffer = RecordingBuffer(16000)
    buffer.append(np.zeros((100, 1), dtype=np.float32))
    with pytest.raises(ValueError, match="quarter second"):
        buffer.write_wav(tmp_path / "short.wav")


def test_buffer_copies_input_and_clips_pcm(tmp_path):
    buffer = RecordingBuffer(100)
    samples = np.full((50, 1), 2, dtype=np.float32)
    buffer.append(samples)
    samples.fill(0)
    destination = tmp_path / "clipped.wav"
    buffer.write_wav(destination)
    with wave.open(str(destination), "rb") as audio:
        pcm = np.frombuffer(audio.readframes(50), dtype="<i2")
        assert np.all(pcm == 32767)
    buffer.clear()
    assert buffer.frames == 0
    assert buffer.chunks == []


def test_device_stop_failure_still_releases_stream_and_audio():
    class BrokenStream:
        closed = False

        def stop(self):
            raise RuntimeError("Device disconnected")

        def close(self):
            self.closed = True

    recorder = Recorder()
    stream = BrokenStream()
    recorder.stream = stream
    recorder.buffer = RecordingBuffer(16000)
    buffer = recorder.buffer
    buffer.append(np.ones((8000, 1), dtype=np.float32))
    with pytest.raises(RuntimeError, match="disconnected"):
        recorder.stop()
    assert stream.closed
    assert recorder.stream is None
    assert recorder.buffer is None
    assert buffer.chunks == []
