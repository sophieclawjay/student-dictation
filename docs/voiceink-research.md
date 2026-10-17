# VoiceInk pipeline and implementation choices

Source inspected on 2026-10-17: Beingpax/VoiceInk commit `9ce98ec81f96517868717d7a7a47818b71281d3f`.

## What VoiceInk actually does

VoiceInk is an existing GPL-3.0 macOS application. Its public source supports several local engines, including Whisper through whisper.cpp and Parakeet through FluidAudio, as well as cloud providers. The model and provider selected in Jay's installed app have not been established.

The Whisper service loads a downloaded local model, converts recorded PCM audio to float samples, sets the source language and prompt, and calls whisper.cpp. Its audio utility uses 16 kHz mono. The inspected decoder uses greedy sampling, temperature 0.2, no previous context, and up to eight CPU threads. Optional VAD uses a 0.5 speech threshold. The model catalog includes large-v3, large-v3-turbo and a quantized turbo variant.

The broader pipeline applies filtering, formatting, word replacements and optional AI enhancement before delivery. These stages can affect perceived accuracy. A model alone will not reproduce all of VoiceInk's behavior.

The inspected Whisper path explicitly sets `translate = false`. Speech-to-text in the spoken language and translation into another language are separate tasks.

## Our first implementation

This project is an independent implementation with its own source and interface. It does not copy VoiceInk source, branding, or assets. It uses faster-whisper with the same Whisper model family through CTranslate2. CPU int8 is the portable baseline for macOS and Windows. This choice does not use Apple's Metal acceleration; it prioritizes shared behavior for the first version. An MLX or whisper.cpp accelerated Mac backend remains a future performance option.

Models download with explicit user action. Inference then uses cached local files. Whisper turbo is appropriate for multilingual transcription; English translation requires a model trained for translation, such as large-v3. Whisper's speech translation target is English. Translation to Korean, Vietnamese or other target languages would require an additional translation engine.

No parity claim is justified yet. Measure word error rate, names and numbers, language-specific errors, latency and peak memory using consented or synthetic recordings on representative student hardware. Compare raw transcripts separately from AI cleanup. Include silence, background noise, mixed-language speech and microphone failure.

## Fleet evidence

M5 Max: existing MLX Whisper large-v3-turbo transcribed a synthetic English sentence. Input and output are in `output/english.aiff` and `output/fleet-mlx-english.txt`. It preserved the wording and rendered spoken “three thirty” as “3.30”. This is a smoke test of the existing fleet backend, not a test of this app's faster-whisper backend or a multilingual accuracy benchmark.

Additional synthetic Korean and Vietnamese recordings were processed on the same host. Korean wording was preserved, with a spoken number rendered as a digit. Vietnamese produced “mái tính” where the fixture said “máy tính”. These samples demonstrate a real error even in clear synthetic speech. Outputs are retained in `output/fleet-mlx-korean.txt` and `output/fleet-mlx-vietnamese.txt`.

The first faster-whisper runtime check failed because PyAV 19 removed the `metadata_errors` argument used by faster-whisper 1.2.1. Pinning PyAV below 19 is required for this version. This failure was discovered through real audio inference, before packaging.

M5 Pro supplied an architecture review through Qwen3.8 27B, retained as raw JSON in `output/sophie-architecture-review.json`. It was a text-only review of the proposed design. Its suggestions were checked by the orchestrator; its claims about Metal acceleration, exact audio APIs and timing thresholds were not accepted as evidence.

## Primary sources

- VoiceInk: https://github.com/Beingpax/VoiceInk
- Decoder: https://github.com/Beingpax/VoiceInk/blob/9ce98ec81f96517868717d7a7a47818b71281d3f/VoiceInk/Infrastructure/Providers/Transcription/Whisper/LibWhisper.swift
- Pipeline: https://github.com/Beingpax/VoiceInk/blob/9ce98ec81f96517868717d7a7a47818b71281d3f/VoiceInk/Features/Recording/Workflows/TranscriptionPipeline.swift
- Whisper tasks and turbo limitations: https://github.com/openai/whisper
- faster-whisper runtime: https://github.com/SYSTRAN/faster-whisper

If VoiceInk code is incorporated later, preserve its copyright notices and comply with its GPL license. Dependency and model licenses also need to accompany distributions.
