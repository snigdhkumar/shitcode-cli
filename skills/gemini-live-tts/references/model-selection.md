# Gemini Live model selection for TTS

This skill intentionally uses Live native-audio models for text-to-speech, even though dedicated TTS models exist.

The default model priority is set in `SKILL.md`:
1. Primary: `gemini-3.8-live`
2. Second fallback: `gemini-3.8-live-extended-thinking`
3. Last fallback: `gemini-2.5-flash-native-audio-preview-12-2025`

The AI agent chooses the order per task and passes it through `--model` and comma-separated `--fallback-models` arguments. The script's model ID allowlist validates supported models but does not decide their retry sequence. Stop fallback for shared authentication or project-permission failures.

Gemini 3.8 Live Extended Thinking must wait for `interaction_status == IDLE` because an utterance completion can be followed by continued reasoning. Do not set thinking configuration on regular `gemini-3.8-live`.

The 2.5 Flash Native Audio model is retained only as the final fallback. Google's deprecation page lists its shutdown date as November 17, 2026 at the time this file was revised; verify that page for later updates.

Official sources:
- https://ai.google.dev/gemini-api/docs/models
- https://ai.google.dev/gemini-api/docs/deprecations
- https://ai.google.dev/gemini-api/docs/live-api/thinking
- https://ai.google.dev/gemini-api/docs/live-api/capabilities
