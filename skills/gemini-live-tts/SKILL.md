---
name: gemini-live-tts
description: Generate and validate text-to-speech audio with Gemini Live native-audio models; choose voice, style, model order, and output path dynamically.
version: 3.1.0
author: Community-maintained
license: MIT
tags: [tts, gemini, live-api, websocket, voice, audio, agent-agnostic]
---

# Gemini Live API as a text-to-speech engine

This skill is agent-agnostic. Any AI agent with access to a runtime that can call Google's Gemini Live API can use it. Do not assume a particular agent, CLI, operating system, shell, configuration directory, or messaging provider.

## Intended use and model policy

This project intentionally uses Live native-audio dialogue models as a text-to-speech engine, even though Google offers dedicated TTS endpoints. Do not silently switch to GenerateContent TTS models.

The skill owns the model priority policy. For normal TTS, the preferred cascade is:

1. **Primary:** `gemini-3.8-live`
2. **Second fallback:** `gemini-3.8-live-extended-thinking`
3. **Last fallback:** `gemini-2.5-flash-native-audio-preview-12-2025`

**Do not rely on the Python script to decide this priority order.** The AI agent reads this skill, decides the model sequence for the task, and passes it to the script with `--model` and `--fallback-models`. The script contains a supported-ID allowlist for validation, but it does not choose the fallback order. Supply fallback IDs as an ordered comma-separated list. If the user explicitly requests a different supported model, start with that model and pass the other appropriate models in the order the skill calls for. Use `--no-fallback` only if the user asks for one model or retries are unsuitable.

Try the next model after generation, connection, timeout, interruption, empty-audio, silent-audio, or WAV-validation failure. Do not keep retrying after a missing/invalid API key, HTTP 401, or a shared permission/project error (typically HTTP 403). Report which model failed and whether a later fallback succeeded.

The 2.5 Live model is the final fallback. Google's deprecation page lists its shutdown date as November 17, 2026 at the time of this revision; verify the official page before future deployments.

## Mandatory dynamic output-path policy

**The AI agent chooses the destination for every task. Never force every audio file into one fixed folder.**

1. First inspect the user's explicit destination, current task/workspace context, existing project conventions, and any paths they mentioned. If a suitable output directory is clear, choose a sensible filename there and pass its full or workspace-relative path with `--output`. Respect an explicit user path.
2. If the correct destination is not clear, do not guess an unrelated project path. Omit `--output` and let the script use its fallback directory. By default this is relative `./audios/` under the runtime's current working directory, configurable using `GEMINI_TTS_FALLBACK_DIR`. This fallback is used only when the agent cannot infer a better destination.
3. The fallback filename is timestamped and collision-resistant. Never assume the script's own directory is the right output directory, and never hardcode a machine-specific absolute path in this skill.
4. After successful synthesis, **always tell the user the exact saved file path**, including the filename. Use the absolute `output=...` path printed by the script. If the runtime tool hides stdout, inspect the output location and report the verified absolute path. Never say the audio is saved unless that path exists and validation succeeded.
5. If an explicitly requested destination already exists, do not silently overwrite it or switch to an unrelated folder. Choose a different filename or ask/require explicit overwrite authorization.

Examples (the agent must supply the task's chosen model order as flags):

```sh
# Agent knows the correct task-specific destination.
python templates/gemini_tts.py "Hello there." --model gemini-3.8-live --fallback-models "gemini-3.8-live-extended-thinking,gemini-2.5-flash-native-audio-preview-12-2025" --output "path/to/task-artifact/intro.wav"

# Agent cannot infer a better destination; script falls back to ./audios/.
python templates/gemini_tts.py "Hello there." --model gemini-3.8-live --fallback-models "gemini-3.8-live-extended-thinking,gemini-2.5-flash-native-audio-preview-12-2025"
```

## Voice and delivery style: ask only when genuinely unclear

Before synthesis, the agent should resolve two separate preferences: **voice presentation/voice choice** and **delivery style**.

1. If the user explicitly specifies a male/female voice or a specific voice, select a suitable prebuilt voice ID and proceed. Do not infer the requested voice presentation from the user's name, gender, identity, or the narration's subject.
2. If the requested delivery is clear from the user's words or task (for example, they explicitly ask for a sad reading, or the text is clearly a celebratory announcement intended to sound excited), select the matching style and proceed without asking.
3. If task context establishes the speaker or style unambiguously, use that context; do not ask redundant questions. Keep the inference limited to what is genuinely clear.
4. If voice presentation is unclear and there is no previously established preference, ask a brief question before generating. If style is also unclear, ask about both in one compact question, for example: “Would you prefer a male or female voice, and what style—neutral, happy, sad, calm, angry, presenting, storytelling, excited, or professional?” If only one preference is unclear, ask only about that one.
5. If the user says to decide yourself or proceed with defaults, do so without more questions. Use a suitable voice and style based on task context, and describe the choices in the final response if helpful.
6. Do not repeatedly ask for preferences already answered in the conversation. Do not claim an auditioned voice has been user-approved unless they selected it.

Auditioned voice candidates:
- **Male-identified voices:** `Achird` (warm lower-mid), `Algenib` (gravelly/deeper), `Charon` (steady/informative lower voice), `Puck` (upbeat).
- **Female-identified voices:** `Achernar` (soft/calm), `Aoede` (breezy/light), `Kore` (firm/clear), `Leda` (youthful).

The script accepts voice IDs via `--voice`. Available tested delivery styles via `--style`: `neutral`, `happy`, `sad`, `calm`, `angry`, `presenting`, `storytelling`, `excited`, and `professional`. Style instructions must not be spoken as part of the narration. Whispering was not part of the completed audition and must not be described as tested.

## Protocol requirements

Use the official Google GenAI SDK where available. Install/update with:

```sh
python -m pip install --upgrade google-genai
```

Configure `GEMINI_API_KEY` in the process environment or a secure secret manager. A local ignored `.env` file may be loaded by the portable template, but never store an API key in a skill document, committed script, command history, issue, or log; never echo it during diagnostics.

Connect using `client.aio.live.connect(model=model_id, config=config)`. Configure:
- `response_modalities: ["AUDIO"]`
- A strict read-aloud-only system instruction that prohibits answering, paraphrasing, introducing, or commenting on the narration.
- `speech_config.voice_config.prebuilt_voice_config.voice_name` set to a supported voice.
- `output_audio_transcription: {}` when supported to help diagnose fidelity.
- API version `v1beta`.

For `gemini-3.8-live-extended-thinking`, use a low thinking level unless a specific reason requires otherwise, and wait for both completed narration and `interaction_status == IDLE`. A `turn_complete` alone does not necessarily mean an Extended Thinking interaction has completely finished. Do not set `thinking_config` on `gemini-3.8-live`.

Send one user text turn with `session.send_client_content(..., turn_complete=True)`. Process all parts in every response: Live responses can carry audio chunks and transcription metadata in the same event. Treat interruption, API error, timeout, early close, empty output, zero-level PCM, or invalid WAV as failure.

## Text-to-speech prompt strategy

Use both a system instruction and a per-turn wrapper. Put user narration between clear delimiters. Tell the model not to speak the instructions/delimiters or add, skip, or change words. Live dialogue models are not guaranteed to be perfectly verbatim; inspect output transcription when available, warn when it differs, and never claim perfect text fidelity without evidence.

## Audio format and validation

Live API audio output is raw little-endian signed 16-bit PCM at 24 kHz, not a WAV or MP3 container. Concatenate all chunks from a completed utterance in order and wrap them in a mono, 16-bit PCM WAV at 24,000 Hz. Do not use an MP3 extension unless a real encoder converts the audio to MP3.

A successful exit code is not enough. Confirm non-empty audio, non-zero sample peak, valid WAV structure, expected channel/sample-rate/sample-width, and plausible duration. Use a finite timeout.

## Error handling and fallback

- Invalid/missing API key or 401: check the secret, API enablement, key restrictions, and project. Do not try further models with the same bad credential.
- 403: likely permission, project, endpoint, or policy issue; do not blindly retry models with the same project/key.
- 404/model not found: the model ID may have changed, may not be enabled for the project, or may be unavailable on this endpoint.
- 400/invalid argument: verify current Live API configuration and model ID requirements.
- 429/resource exhausted: respect rate-limit/backoff guidance; do not infer unlimited availability from a UI quota display.
- Timeout/connection close: report the model and stage, then try the next model in the supplied sequence unless the error is auth/permission-related.
- Text but no audio: record the transcript and retry the next configured model.
- Silent/corrupt audio: inspect PCM byte count/alignment/sample peak/WAV header/channels/sample rate/extension, then try the next model.
- Report the diagnosed cause and whether fallback actually succeeded. Never claim success until the output file has been checked.

## Preflight, permissions, and API-key recovery

**Do not ask for blanket permission every time TTS is requested.** If the user asks for TTS and the connected tools already authorize running the local skill, execute the required checks and synthesis without an extra permission prompt. Respect actual tool/host confirmation gates and explicit user restrictions; never claim that an unavailable device or denied tool was used. If execution is blocked, explain the specific block and offer the next supported action. A previous failed remote command is not, by itself, a reason to refuse all future attempts: use an available authorized tool or report that access is currently unavailable.

Before attempting generation, perform a lightweight preflight:
1. Confirm the script exists and Python can run it; inspect `--help` or perform static checks when appropriate.
2. Check whether the API key is available without printing, logging, echoing, or exposing its value. The script reads `GEMINI_API_KEY` from the process environment first, then from a local `.env` beside `gemini_tts.py`.
3. When the user has requested TTS, make one short, bounded API generation attempt using the selected primary model and a benign short phrase, or use the requested narration itself if it is already short. Validate the WAV before reporting success. Do not run a broad audition/test sweep unless the user asks.
4. If preflight or generation fails, tell the user what actually failed, using the sanitized error and stage. Do not claim that a test ran if it did not. Do not blame the API without evidence.

### API key setup and failure handling

If the error indicates a missing key or invalid/expired API key:
- Explain that the key is missing or rejected, and ask the user to provide/configure a valid Google Gemini API key only if needed to proceed. Never ask them to paste a secret into a public/shared transcript if a local setup path is available.
- Prefer telling the user to set `GEMINI_API_KEY` in their environment or create a local `.env` file in the **same directory as `gemini_tts.py`**. The template already reads that adjacent file. Never place the key inside `SKILL.md`, the Python source, or logs.
- If the user explicitly asks the agent to configure it and an authorized local file-writing tool is available, create/update `.env` next to `gemini_tts.py` (or the actual directory containing the script), add `GEMINI_API_KEY=...`, and ensure that `.env` is gitignored. Never echo the value in tool output or a final response. If secure writing cannot be guaranteed, give the user manual steps instead.
- Do not keep retrying all fallback models when the error is a shared authentication, invalid-key, project, or permission problem (usually 401/403). Diagnose the credential/project issue first. After the key is configured, retry a single bounded preflight/generation attempt when authorized.

For 403, missing API enablement, invalid project restrictions, billing/quota, or a model-specific 404, explain the observed reason and the next step separately. Do not ask for a new key if the evidence points to a project permission, API enablement, billing, or model-availability issue. Never print or repeat secrets in logs or responses.

## Portable implementation

The included `templates/gemini_tts.py` supports validated model selection and agent-supplied fallback sequencing, voice and delivery-style selection, finite timeouts, a configurable no-destination-known fallback directory, unique fallback filenames, and WAV validation. It must not contain a real API key. The supported model IDs in the script are only an allowlist, not the default fallback policy.

Examples:

```sh
python templates/gemini_tts.py "A short narration." --model gemini-3.8-live --fallback-models "gemini-3.8-live-extended-thinking,gemini-2.5-flash-native-audio-preview-12-2025" --voice Kore --style neutral --output "some/task/output.wav"
python templates/gemini_tts.py "A short narration." --model gemini-3.8-live --fallback-models "gemini-3.8-live-extended-thinking,gemini-2.5-flash-native-audio-preview-12-2025" --voice Charon --style storytelling
python templates/gemini_tts.py --list-models
python templates/gemini_tts.py --list-voices
```

The agent decides the path and model sequence per task. The script prints the verified absolute output path and the model used; the agent must include the saved file path in its final response.

## Safe test checklist

1. Check Python, SDK import/version, CLI help, supported-model listing, voice listing, and static syntax without making API calls.
2. Only make audio-generation calls when the user asks for synthesis or testing. Use short benign narration and finite timeout.
3. Confirm each WAV opens successfully, is 24 kHz mono 16-bit PCM, has non-zero audio level, and has plausible duration.
4. Inspect output transcription (when available) for prompt leakage, additions, or omissions.
5. Capture model ID, pass/fail, sanitized API error, output path, file properties, and transcript mismatch. Never print credentials.
6. Do not make broad test sweeps because a UI quota column says “Unlimited.”

## Official references

- Live API quickstart: https://ai.google.dev/gemini-api/docs/live-api/get-started-sdk
- Live API capabilities and audio format: https://ai.google.dev/gemini-api/docs/live-api/capabilities
- Live API thinking and interaction status: https://ai.google.dev/gemini-api/docs/live-api/thinking
- Model availability and IDs: https://ai.google.dev/gemini-api/docs/models
- Model deprecations and shutdowns: https://ai.google.dev/gemini-api/docs/deprecations
