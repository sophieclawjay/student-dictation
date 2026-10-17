from pathlib import Path

import pytest

from student_dictation.core import (
    MODEL_BY_KEY,
    mark_model_ready,
    model_ready,
    private_environment,
    validate_options,
)


def test_turbo_translation_is_rejected():
    with pytest.raises(ValueError, match="Turbo"):
        validate_options("large-v3-turbo", "translate", "vi")


@pytest.mark.parametrize("model", ["large-v3", "small", "base"])
def test_multilingual_translation_models(model):
    assert validate_options(model, "translate", "ko").translates


@pytest.mark.parametrize(
    "model,task,language",
    [
        ("made-up-model", "transcribe", None),
        ("base", "write-essay", None),
        ("base", "transcribe", "invalid"),
        ("base", "transcribe", "yue"),
    ],
)
def test_invalid_options(model, task, language):
    with pytest.raises(ValueError):
        validate_options(model, task, language)


def test_cantonese_with_large_v3():
    assert validate_options("large-v3", "transcribe", "yue")


def test_partial_download_and_missing_tokenizer_are_not_ready(model_directory):
    assert model_ready(model_directory)
    (model_directory / "tokenizer.json").unlink()
    assert not model_ready(model_directory)


def test_download_requires_completion_marker(model_directory):
    (model_directory / ".complete.json").unlink()
    assert not model_ready(model_directory)
    mark_model_ready(model_directory, MODEL_BY_KEY["base"])
    assert model_ready(model_directory)


def test_empty_weights_cannot_be_marked_ready(model_directory):
    (model_directory / "model.bin").write_bytes(b"")
    with pytest.raises(ValueError, match="incomplete"):
        mark_model_ready(model_directory, MODEL_BY_KEY["base"])
    assert not model_ready(model_directory)


def test_empty_vocabulary_cannot_be_marked_ready(model_directory):
    (model_directory / "vocabulary.json").write_bytes(b"")
    with pytest.raises(ValueError, match="vocabulary"):
        mark_model_ready(model_directory, MODEL_BY_KEY["base"])
    assert not model_ready(model_directory)


def test_missing_directory_is_not_ready(tmp_path: Path):
    assert not model_ready(tmp_path / "missing")


def test_recognition_is_forced_offline_and_hub_telemetry_disabled():
    flags = private_environment(offline=True)
    assert flags["HF_HUB_OFFLINE"] == "1"
    assert flags["TRANSFORMERS_OFFLINE"] == "1"
    assert flags["HF_HUB_DISABLE_TELEMETRY"] == "1"
    assert flags["HF_HUB_DISABLE_IMPLICIT_TOKEN"] == "1"
    assert private_environment(offline=False)["HF_HUB_OFFLINE"] == "0"
