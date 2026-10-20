#!/usr/bin/env python3
"""Generate a validated WAV using Gemini Live native-audio models as a TTS engine.

The AI agent selects the model order from SKILL.md and passes it via --model
and the comma-separated --fallback-models option. The script validates model IDs
but does not select fallback priority.

If --output is supplied, that is the selected destination. If it is omitted,
a unique timestamped file is written to GEMINI_TTS_FALLBACK_DIR (default: ./audios).
Requires the Google GenAI SDK and GEMINI_API_KEY. Never hard-code API keys.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import struct
import sys
import wave
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
ENV_FILE = SCRIPT_DIR / ".env"

# These IDs form a supported-model allowlist only. The calling AI agent
# chooses the order and passes it via --model and --fallback-models.
SUPPORTED_MODELS = (
    "gemini-3.8-live",
    "gemini-3.8-live-extended-thinking",
    "gemini-2.5-flash-native-audio-preview-12-2025",
)
EXTENDED_THINKING_MODEL = "gemini-3.8-live-extended-thinking"
OUTPUT_RATE = 24000

STYLE_PROMPTS = {
    "neutral": "Use a natural, clear, even delivery without exaggerated emotion.",
    "happy": "Sound happy and warm, with a natural upbeat tone. Do not overact.",
    "sad": "Use a subdued, gentle, sad emotional tone without sounding theatrical.",
    "calm": "Use a calm, relaxed, steady delivery with smooth pacing.",
    "angry": "Use a firm, frustrated, angry tone without shouting or adding words.",
    "presenting": "Sound like a clear, confident presenter addressing an audience.",
    "storytelling": "Use expressive storytelling cadence and natural dramatic pauses.",
    "excited": "Sound enthusiastic and energized while keeping every word clear.",
    "professional": "Use a composed, polished, professional delivery.",
}

VOICE_DESCRIPTIONS = {
    "Achird": "male-identified; warm lower-mid voice",
    "Algenib": "male-identified; gravelly and deeper",
    "Charon": "male-identified; steady, informative lower voice",
    "Puck": "male-identified; upbeat",
    "Achernar": "female-identified; soft and calm",
    "Aoede": "female-identified; breezy and light",
    "Kore": "female-identified; firm and clear",
    "Leda": "female-identified; youthful",
}

SYSTEM_INSTRUCTION = (
    "You are a text-to-speech engine, not a conversational assistant. "
    "Speak only the exact narration text placed between the narration delimiters in the user turn. "
    "Do not answer it, paraphrase it, summarize it, introduce it, or add commentary. "
    "Do not speak instructions or delimiters. Preserve the narration's words, numbers, "
    "punctuation-driven pauses, language, and order as closely as possible."
)
TTS_PREFIX = (
    "Read the following narration aloud. Follow the delivery-style instructions in your system instruction. "
    "Speak only the narration between the delimiters; do not speak instructions or delimiters. "
    "Do not add an introduction or response.\n"
    "=== NARRATION START ===\n"
)
TTS_SUFFIX = "\n=== NARRATION END ==="


class SynthesisError(RuntimeError):
    pass


def load_local_env_file() -> None:
    """Load adjacent KEY=VALUE pairs without overriding process environment values."""
    candidate_paths = [
        SCRIPT_DIR / ".env",
        SCRIPT_DIR.parent / ".env",
    ]
    for env_path in candidate_paths:
        if not env_path.is_file():
            continue
        try:
            for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, value = line.split("=", 1)
                name = name.strip()
                value = value.strip()
                if value and value[0:1] in ("'", '"') and value[-1:] == value[0:1]:
                    value = value[1:-1]
                if name and name not in os.environ:
                    os.environ[name] = value
        except OSError as exc:
            raise SynthesisError(f"Could not read {env_path.name}: {exc}") from exc


def _attr(obj: Any, name: str, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _status_label(value: Any) -> str:
    if value is None:
        return ""
    return str(getattr(value, "name", value)).rsplit(".", 1)[-1].upper()


def _write_pcm_wav(path: Path, pcm: bytes) -> tuple[int, float]:
    if not pcm:
        raise SynthesisError("No PCM audio was returned.")
    if len(pcm) % 2:
        raise SynthesisError(f"Audio byte count ({len(pcm)}) is not aligned to 16-bit PCM.")
    peak = 0
    for (sample,) in struct.iter_unpack("<h", pcm):
        peak = max(peak, abs(sample))
    if peak == 0:
        raise SynthesisError("The model returned silent PCM audio.")

    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(OUTPUT_RATE)
        wf.writeframes(pcm)

    # Reopen the file to validate the actual container and derive duration.
    try:
        with wave.open(str(path), "rb") as wf:
            if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getframerate() != OUTPUT_RATE:
                raise SynthesisError("Written WAV has unexpected channels, sample width, or sample rate.")
            frame_count = wf.getnframes()
            if frame_count <= 0:
                raise SynthesisError("Written WAV contains no frames.")
            duration = frame_count / wf.getframerate()
    except (wave.Error, OSError) as exc:
        raise SynthesisError(f"Written WAV failed validation: {exc}") from exc
    return peak, duration


def resolve_output_path(requested: Path | None, overwrite: bool = False) -> Path:
    """Honor an explicit agent/user destination; otherwise use the configurable fallback."""
    if requested is not None:
        path = requested.expanduser().resolve()
        if path.suffix.lower() != ".wav":
            raise SynthesisError("Output file must end in .wav; this tool writes a WAV container.")
        if path.exists() and not overwrite:
            raise SynthesisError(
                f"Output file already exists: {path}. Choose a new filename or pass --overwrite explicitly."
            )
        return path

    configured_dir = os.environ.get("GEMINI_TTS_FALLBACK_DIR", "audios").strip() or "audios"
    directory = Path(configured_dir).expanduser()
    if not directory.is_absolute():
        directory = Path.cwd() / directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = directory / f"speech_{timestamp}.wav"
    serial = 2
    while candidate.exists():
        candidate = directory / f"speech_{timestamp}_{serial:02d}.wav"
        serial += 1
    return candidate.resolve()


async def synthesize_once(
    *,
    api_key: str,
    model: str,
    text: str,
    voice: str,
    style: str,
    timeout: float,
) -> tuple[bytes, str]:
    try:
        from google import genai
    except ImportError as exc:
        raise SynthesisError(
            "Missing dependency. Install/update with: python -m pip install --upgrade google-genai"
        ) from exc

    client = genai.Client(api_key=api_key, http_options={"api_version": "v1beta"})
    config = {
        "response_modalities": ["AUDIO"],
        "system_instruction": {
            "parts": [{"text": SYSTEM_INSTRUCTION + " Delivery style: " + STYLE_PROMPTS[style]}]
        },
        "speech_config": {
            "voice_config": {
                "prebuilt_voice_config": {"voice_name": voice}
            }
        },
        "output_audio_transcription": {},
    }
    # The regular Gemini 3.8 Live model does not accept thinking_config.
    if model == EXTENDED_THINKING_MODEL:
        config["thinking_config"] = {"thinking_level": "low"}

    pcm_chunks: list[bytes] = []
    transcription: list[str] = []
    requires_idle = model == EXTENDED_THINKING_MODEL

    async def run_session():
        async with client.aio.live.connect(model=model, config=config) as session:
            await session.send_client_content(
                turns=[{
                    "role": "user",
                    "parts": [{"text": TTS_PREFIX + text + TTS_SUFFIX}],
                }],
                turn_complete=True,
            )
            turn_complete = False
            interaction_idle = not requires_idle
            async for response in session.receive():
                server_content = _attr(response, "server_content")
                status = _status_label(_attr(response, "interaction_status"))
                if not status:
                    status = _status_label(_attr(server_content, "interaction_status"))

                if status == "IDLE" and turn_complete:
                    interaction_idle = True

                if server_content is None:
                    error = _attr(response, "error")
                    if error:
                        raise SynthesisError(f"Server error: {error}")
                    if turn_complete and interaction_idle:
                        break
                    continue

                if _attr(server_content, "interrupted", False):
                    raise SynthesisError("Generation was interrupted before completion.")

                model_turn = _attr(server_content, "model_turn")
                for part in (_attr(model_turn, "parts", []) or []):
                    inline = _attr(part, "inline_data")
                    if not inline:
                        continue
                    data = _attr(inline, "data")
                    if isinstance(data, str):
                        import base64
                        data = base64.b64decode(data)
                    if data:
                        pcm_chunks.append(bytes(data))

                output_transcription = _attr(server_content, "output_transcription")
                transcript_part = _attr(output_transcription, "text")
                if transcript_part:
                    transcription.append(transcript_part)

                if _attr(server_content, "turn_complete", False):
                    turn_complete = True
                    if status == "IDLE":
                        interaction_idle = True
                    if not requires_idle or interaction_idle:
                        break

            if not turn_complete:
                raise SynthesisError("Live session closed before turn_complete; audio may be truncated.")
            if requires_idle and not interaction_idle:
                raise SynthesisError(
                    "Extended Thinking utterance completed, but interaction_status never reached IDLE."
                )
            if not pcm_chunks:
                raise SynthesisError("The session completed without audio data.")

    try:
        await asyncio.wait_for(run_session(), timeout=timeout)
    except asyncio.TimeoutError as exc:
        raise SynthesisError(f"Timed out after {timeout:g}s while waiting for Live audio.") from exc
    except SynthesisError:
        raise
    except Exception as exc:
        raise SynthesisError(f"{type(exc).__name__}: {exc}") from exc
    finally:
        try:
            await client.aio.aclose()
        except Exception:
            pass
    return b"".join(pcm_chunks), "".join(transcription).strip()


def is_auth_or_permission_failure(message: str) -> bool:
    lowered = message.lower()
    return any(term in lowered for term in (
        "api key not valid", "invalid api key", "unauthorized", "401", "403",
        "permission denied", "api key expired", "permission_denied",
    ))


def _list_models() -> None:
    print("Supported model IDs (the caller/AI agent chooses the order):")
    for model in SUPPORTED_MODELS:
        print(model)


def _list_voices() -> None:
    for voice, description in VOICE_DESCRIPTIONS.items():
        print(f"{voice}: {description}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Synthesize and validate speech with Gemini Live native audio."
    )
    parser.add_argument("text", nargs="?", help="Text to speak.")
    parser.add_argument("-i", "--input-file", type=Path, help="Read narration from a UTF-8 text file.")
    parser.add_argument(
        "-o", "--output", type=Path, default=None,
        help="Explicit destination WAV path. If omitted, a unique file is saved to GEMINI_TTS_FALLBACK_DIR (default: ./audios/).",
    )
    parser.add_argument(
        "--model", choices=SUPPORTED_MODELS, default=None,
        help="Required first model; the calling agent chooses this for the task.",
    )
    parser.add_argument(
        "--fallback-models", default="",
        help="Comma-separated, ordered model IDs to try after --model. Order is supplied by the AI agent/skill.",
    )
    parser.add_argument("--no-fallback", action="store_true", help="Disable fallback; use only --model.")
    parser.add_argument("--overwrite", action="store_true", help="Allow overwriting an explicitly named existing WAV file.")
    parser.add_argument("--voice", default="Kore", help="Prebuilt Live voice ID (default: Kore).")
    parser.add_argument(
        "--style", choices=tuple(STYLE_PROMPTS), default="neutral",
        help="Delivery style (default: neutral).",
    )
    parser.add_argument("--timeout", type=float, default=60.0, help="Timeout per model attempt, in seconds.")
    parser.add_argument("--list-models", action="store_true", help="List supported model IDs, not fallback priority.")
    parser.add_argument("--list-voices", action="store_true", help="List auditioned prebuilt voice candidates.")
    args = parser.parse_args()

    if args.list_models:
        _list_models()
        return 0
    if args.list_voices:
        _list_voices()
        return 0
    if bool(args.text) == bool(args.input_file):
        parser.error("Provide exactly one of TEXT or --input-file.")
    if args.timeout <= 0:
        parser.error("--timeout must be positive.")

    try:
        load_local_env_file()
    except SynthesisError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        output_path = resolve_output_path(args.output, overwrite=args.overwrite)
    except SynthesisError as exc:
        parser.error(str(exc))

    try:
        text = args.input_file.read_text(encoding="utf-8").strip() if args.input_file else (args.text or "").strip()
    except OSError as exc:
        print(f"Could not read input file: {exc}", file=sys.stderr)
        return 2
    if not text:
        print("Input text is empty.", file=sys.stderr)
        return 2

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "PASTE_YOUR_GEMINI_API":
        print(
            "GEMINI_API_KEY is not configured.\n"
            "Please open: skills/gemini-live-tts/templates/.env\n"
            "and replace PASTE_YOUR_GEMINI_API with your Google Gemini API key.\n"
            "Get a Gemini API key at: https://aistudio.google.com/app/apikey",
            file=sys.stderr,
        )
        return 2

    if not args.model:
        parser.error("--model is required for synthesis; the calling agent must select a model.")

    requested_fallbacks = [
        item.strip() for item in args.fallback_models.split(",") if item.strip()
    ]
    unknown_models = [
        model for model in [args.model, *requested_fallbacks]
        if model not in SUPPORTED_MODELS
    ]
    if unknown_models:
        parser.error("Unsupported model ID(s): " + ", ".join(dict.fromkeys(unknown_models)))

    attempts = [args.model]
    if not args.no_fallback:
        attempts.extend(
            model for model in requested_fallbacks
            if model not in attempts
        )

    last_error = ""
    for index, model in enumerate(attempts):
        print(f"[*] Trying {model}", file=sys.stderr)
        try:
            pcm, transcript = asyncio.run(synthesize_once(
                api_key=api_key,
                model=model,
                text=text,
                voice=args.voice,
                style=args.style,
                timeout=args.timeout,
            ))
            peak, duration = _write_pcm_wav(output_path, pcm)
            resolved = output_path.resolve()
            print(
                f"[OK] model={model}; output={resolved}; bytes={resolved.stat().st_size}; "
                f"duration_seconds={duration:.2f}; peak={peak}",
                flush=True,
            )
            if transcript:
                print(f"Output transcription: {transcript[:500]}", file=sys.stderr)
                normalized_transcript = " ".join(transcript.split()).casefold()
                normalized_input = " ".join(text.split()).casefold()
                if normalized_input != normalized_transcript:
                    print(
                        "[WARN] Output transcription differs from the supplied text; review the audio for omissions or additions.",
                        file=sys.stderr,
                    )
            return 0
        except Exception as exc:
            last_error = str(exc).replace(api_key, "[REDACTED]") if api_key else str(exc)
            print(f"[FAILED] {model}: {last_error}", file=sys.stderr)
            if is_auth_or_permission_failure(last_error) and index < len(attempts) - 1:
                print(
                    "[INFO] Stopping fallback attempts because this looks like a shared authentication/permission error.",
                    file=sys.stderr,
                )
                break

    print(f"Gemini Live TTS failed. Last diagnosed cause: {last_error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
