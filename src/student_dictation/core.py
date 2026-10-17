"""Dependency-light policy shared by the desktop app and isolated worker."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ModelSpec:
    key: str
    label: str
    repository: str
    download_size: str
    translates: bool = True


MODELS = (
    ModelSpec(
        "large-v3-turbo",
        "Whisper large-v3-turbo",
        "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
        "about 1.6 GB",
        False,
    ),
    ModelSpec("large-v3", "Whisper large-v3", "Systran/faster-whisper-large-v3", "about 3.1 GB"),
    ModelSpec("small", "Whisper small", "Systran/faster-whisper-small", "about 490 MB"),
    ModelSpec("base", "Whisper base", "Systran/faster-whisper-base", "about 150 MB"),
)
MODEL_BY_KEY = {model.key: model for model in MODELS}

# Whisper language codes. A fixed list keeps the settings screen usable without
# importing the inference stack or contacting a model hub.
LANGUAGES = {
    "af": "Afrikaans",
    "sq": "Albanian",
    "am": "Amharic",
    "ar": "Arabic",
    "hy": "Armenian",
    "as": "Assamese",
    "az": "Azerbaijani",
    "ba": "Bashkir",
    "eu": "Basque",
    "be": "Belarusian",
    "bn": "Bengali",
    "bs": "Bosnian",
    "br": "Breton",
    "bg": "Bulgarian",
    "my": "Burmese",
    "yue": "Cantonese",
    "ca": "Catalan",
    "zh": "Chinese (Mandarin)",
    "hr": "Croatian",
    "cs": "Czech",
    "da": "Danish",
    "nl": "Dutch",
    "en": "English",
    "et": "Estonian",
    "fo": "Faroese",
    "fi": "Finnish",
    "fr": "French",
    "gl": "Galician",
    "ka": "Georgian",
    "de": "German",
    "el": "Greek",
    "gu": "Gujarati",
    "ht": "Haitian Creole",
    "ha": "Hausa",
    "haw": "Hawaiian",
    "he": "Hebrew",
    "hi": "Hindi",
    "hu": "Hungarian",
    "is": "Icelandic",
    "id": "Indonesian",
    "it": "Italian",
    "ja": "Japanese",
    "jw": "Javanese",
    "kn": "Kannada",
    "kk": "Kazakh",
    "km": "Khmer",
    "ko": "Korean",
    "lo": "Lao",
    "la": "Latin",
    "lv": "Latvian",
    "ln": "Lingala",
    "lt": "Lithuanian",
    "lb": "Luxembourgish",
    "mk": "Macedonian",
    "mg": "Malagasy",
    "ms": "Malay",
    "ml": "Malayalam",
    "mt": "Maltese",
    "mi": "Maori",
    "mr": "Marathi",
    "mn": "Mongolian",
    "ne": "Nepali",
    "no": "Norwegian",
    "nn": "Norwegian Nynorsk",
    "oc": "Occitan",
    "ps": "Pashto",
    "fa": "Persian",
    "pl": "Polish",
    "pt": "Portuguese",
    "pa": "Punjabi",
    "ro": "Romanian",
    "ru": "Russian",
    "sa": "Sanskrit",
    "sr": "Serbian",
    "sn": "Shona",
    "sd": "Sindhi",
    "si": "Sinhala",
    "sk": "Slovak",
    "sl": "Slovenian",
    "so": "Somali",
    "es": "Spanish",
    "su": "Sundanese",
    "sw": "Swahili",
    "sv": "Swedish",
    "tl": "Tagalog",
    "tg": "Tajik",
    "ta": "Tamil",
    "tt": "Tatar",
    "te": "Telugu",
    "th": "Thai",
    "bo": "Tibetan",
    "tr": "Turkish",
    "tk": "Turkmen",
    "uk": "Ukrainian",
    "ur": "Urdu",
    "uz": "Uzbek",
    "vi": "Vietnamese",
    "cy": "Welsh",
    "yi": "Yiddish",
    "yo": "Yoruba",
}


def model_ready(directory: Path) -> bool:
    """Require a complete download, including the tokenizer for offline use.

    The marker is written only after snapshot_download finishes and all required
    files are present. Merely finding model.bin cannot identify a partial model.
    """
    required = ("model.bin", "config.json", "tokenizer.json", ".complete.json")
    if not all(
        (directory / name).is_file() and (directory / name).stat().st_size > 0 for name in required
    ):
        return False
    return any(p.is_file() and p.stat().st_size for p in directory.glob("vocabulary.*"))


def mark_model_ready(directory: Path, model: ModelSpec) -> None:
    required = ("model.bin", "config.json", "tokenizer.json")
    if not all(
        (directory / name).is_file() and (directory / name).stat().st_size > 0 for name in required
    ):
        raise ValueError("The download is incomplete. Choose Download model to resume it.")
    if not any(directory.glob("vocabulary.*")):
        raise ValueError("The downloaded model is missing its vocabulary. Retry the download.")
    temporary = directory / ".complete.tmp"
    temporary.write_text(
        json.dumps({"repository": model.repository, "format": 1}), encoding="utf-8"
    )
    temporary.replace(directory / ".complete.json")


def validate_options(model_key: str, task: str, language: str | None) -> ModelSpec:
    if model_key not in MODEL_BY_KEY:
        raise ValueError("Choose one of the supplied Whisper models.")
    if task not in {"transcribe", "translate"}:
        raise ValueError("Choose transcribe or translate to English.")
    model = MODEL_BY_KEY[model_key]
    if task == "translate" and not model.translates:
        raise ValueError("Turbo does not support translation. Choose large-v3, small, or base.")
    if language is not None and language not in LANGUAGES:
        raise ValueError("Choose a supported input language or Auto detect.")
    # Cantonese's dedicated language token was added in the large-v3 vocabulary.
    if language == "yue" and model_key in {"small", "base"}:
        raise ValueError("Cantonese requires large-v3 or large-v3-turbo.")
    return model


def private_environment(*, offline: bool) -> dict[str, str]:
    """Explicitly suppress hub telemetry and ambient authentication."""
    result = {
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1",
        "DO_NOT_TRACK": "1",
        "TOKENIZERS_PARALLELISM": "false",
        "HF_HUB_OFFLINE": "1" if offline else "0",
        "TRANSFORMERS_OFFLINE": "1" if offline else "0",
    }
    return result


def apply_private_environment(*, offline: bool) -> None:
    os.environ.update(private_environment(offline=offline))
