# Live TTS protocol

The AI agent chooses the model sequence per task. The normal skill preference is:
1. `gemini-3.8-live`
2. `gemini-3.8-live-extended-thinking`
3. `gemini-2.5-flash-native-audio-preview-12-2025`

Pass the selected first model with `--model` and ordered remaining model IDs with comma-separated `--fallback-models`. These IDs are validated against a supported-model allowlist in the script; the retry order is not hardcoded into the script.

Use the Google GenAI Python SDK and Live API v1beta. Configure `response_modalities=["AUDIO"]`, strict TTS system instructions, `speech_config.voice_config.prebuilt_voice_config.voice_name`, and `output_audio_transcription={}` when available.

Only for `gemini-3.8-live-extended-thinking`, set `thinking_config` (default low) and wait for both utterance completion and `interaction_status == IDLE`. A `turn_complete` event alone can be an intermediate utterance. For `gemini-3.8-live`, do not set thinking configuration. Process every audio part and transcription; treat interruption, timeout, early close, absent audio, silent PCM, or malformed output as failure.

Ask about voice presentation and delivery style only if they cannot be resolved from the request or context. If only one is unclear, ask only about that one. If either is clear, proceed without asking about it. Never infer gender presentation from the user's name or identity.

The agent chooses the audio destination for each task. Pass an explicit `--output` WAV path whenever the correct user/workspace location is known. If no suitable destination can be inferred, omit it to use `GEMINI_TTS_FALLBACK_DIR` (default relative `./audios/`). The fallback filename is unique and timestamped. Always report the exact verified absolute path printed by the program.

Live audio is raw little-endian signed 16-bit PCM at 24 kHz. Concatenate chunks in order and wrap them as mono 16-bit WAV at 24 kHz. Verify WAV validity, non-zero peak, plausible duration, and output-transcription fidelity when available.

Error diagnosis: 401 = authentication; 403 = access/project permission; 404 = model ID/access/endpoint; 400 = invalid schema/config; 429 = quota/rate limit. Stop retries for shared authentication/permission failures. Never print credentials.

Official references:
- https://ai.google.dev/gemini-api/docs/live-api/capabilities
- https://ai.google.dev/gemini-api/docs/live-api/get-started-sdk
- https://ai.google.dev/gemini-api/docs/live-api/thinking
- https://ai.google.dev/gemini-api/docs/deprecations
