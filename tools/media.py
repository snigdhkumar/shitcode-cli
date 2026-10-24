"""Multimodal Vision & Video Engine Tool for ShitCode.
Provides direct image and video inspection capabilities for AI chatbots (ChatGPT, Claude, etc.)
using standard MCP image content blocks and on-demand universal FFmpeg provisioning.
"""

from __future__ import annotations

import asyncio
import base64
import json
import mimetypes
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.ffmpeg_installer import ensure_ffmpeg_installed
from core.reporter import with_error_reporting

ROOT_DIR = Path(__file__).resolve().parent.parent
TEMP_DIR = ROOT_DIR / ".temp"


def _resolve_media_path(path_str: str) -> Path:
    """Resolve relative or absolute media path safely."""
    p = Path(path_str.strip().strip("\"'"))
    if not p.is_absolute():
        p = (Path.cwd() / p).resolve()
    return p


def optimize_image_for_vision(
    raw_bytes: bytes,
    max_dimension: int = 1280,
    quality: int = 75,
    max_payload_kb: int = 100,
) -> tuple[bytes, str, str]:
    """Downsample and compress image bytes to keep payload under max_payload_kb (~50-80KB).
    Prevents overflowing LLM context windows while preserving high visual fidelity for vision encoders.
    Returns: (optimized_bytes, mime_type, optimization_note)
    """
    try:
        from PIL import Image
        import io

        im = Image.open(io.BytesIO(raw_bytes))
        orig_w, orig_h = im.size
        orig_kb = len(raw_bytes) // 1024

        # If already lightweight (< max_payload_kb) and within bounds, keep original
        if orig_kb <= max_payload_kb and max(orig_w, orig_h) <= max_dimension:
            fmt = (im.format or "JPEG").lower()
            mime = "image/jpeg" if fmt in ("jpeg", "jpg") else f"image/{fmt}"
            return raw_bytes, mime, f"{orig_kb} KB, {orig_w}x{orig_h}"

        # Convert transparency/palette to clean white-background RGB for JPEG compression
        if im.mode in ("RGBA", "LA", "P"):
            rgb = Image.new("RGB", im.size, (255, 255, 255))
            if im.mode == "RGBA":
                rgb.paste(im, mask=im.split()[3])
            else:
                rgb.paste(im.convert("RGBA"))
            im = rgb
        elif im.mode != "RGB":
            im = im.convert("RGB")

        # Resize keeping aspect ratio if larger than max_dimension
        if max(im.size) > max_dimension:
            im.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

        new_w, new_h = im.size
        out = io.BytesIO()
        im.save(out, format="JPEG", quality=quality, optimize=True)
        compressed_bytes = out.getvalue()
        comp_kb = len(compressed_bytes) // 1024

        note = f"{comp_kb} KB (optimized from {orig_kb} KB, {new_w}x{new_h})"
        return compressed_bytes, "image/jpeg", note
    except Exception as e:
        # Fallback if PIL is unavailable or encounters error
        kb = len(raw_bytes) // 1024
        return raw_bytes, "image/jpeg", f"{kb} KB"


@with_error_reporting("image_inspect")
async def image_inspect(path: str, max_dimension: int = 1280) -> Any:
    """Inspect and visually analyze any local image file on the host machine.
    
    Returns standard MCP multimodal image blocks directly to the AI vision encoder,
    automatically optimized and compressed to prevent overflowing LLM conversation limits.
    """
    target = _resolve_media_path(path)
    if not target.is_file():
        return f"Error: Image file not found at '{path}'."

    try:
        raw_bytes = target.read_bytes()
        opt_bytes, opt_mime, note = optimize_image_for_vision(raw_bytes, max_dimension=max_dimension)
        b64_data = base64.b64encode(opt_bytes).decode("ascii")

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Image '{target.name}' loaded successfully ({note}, MIME: {opt_mime})."
                },
                {
                    "type": "image",
                    "data": b64_data,
                    "mimeType": opt_mime
                }
            ]
        }
    except Exception as e:
        return f"Error reading image '{target.name}': {e}"


@with_error_reporting("video_inspect")
async def video_inspect(
    path: str,
    fps: float = 0.5,
    max_frames: int = 8,
    start_time: Optional[str] = None,
    duration: Optional[str] = None,
) -> Any:
    """Inspect and visually analyze any local video file using on-demand FFmpeg.
    
    Extracts sequential sample keyframes and returns them as chronological
    MCP image blocks for AI visual analysis of motion, UI transitions, or video bugs.
    """
    target = _resolve_media_path(path)
    if not target.is_file():
        return f"Error: Video file not found at '{path}'."

    # 1. Ensure universal FFmpeg is ready on demand
    ok, ffmpeg_exe, was_fresh = await asyncio.to_thread(ensure_ffmpeg_installed)
    if not ok:
        return f"Error initializing video engine: {ffmpeg_exe}"

    install_notice = "[Notice: FFmpeg video engine was downloaded on demand for first-time use.] " if was_fresh else ""

    # 2. Extract video metadata
    metadata_summary = ""
    try:
        probe = subprocess.run([ffmpeg_exe, "-i", str(target)], capture_output=True, text=True, timeout=10)
        output_txt = probe.stderr or probe.stdout or ""
        dur_match = re.search(r"Duration:\s*(\d{2}:\d{2}:\d{2}\.\d+)", output_txt)
        res_match = re.search(r"Video:.*,\s*(\d{3,5}x\d{3,5})", output_txt)
        dur_str = dur_match.group(1) if dur_match else "unknown duration"
        res_str = res_match.group(1) if res_match else "unknown resolution"
        metadata_summary = f"Duration: {dur_str}, Resolution: {res_str}"
    except Exception as meta_err:
        metadata_summary = f"Metadata notice: {meta_err}"

    # 3. Extract sample frames into temporary directory
    max_frames = max(1, min(int(max_frames), 20))
    fps = max(0.05, min(float(fps), 5.0))

    session_id = f"video_{int(time.time())}_{os.getpid()}"
    out_dir = TEMP_DIR / session_id
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [ffmpeg_exe, "-y"]
    if start_time:
        cmd.extend(["-ss", str(start_time).strip()])
    if duration:
        cmd.extend(["-t", str(duration).strip()])

    cmd.extend([
        "-i", str(target),
        "-vf", f"fps={fps}",
        "-vframes", str(max_frames),
        "-q:v", "3",
        str(out_dir / "frame_%03d.jpg"),
    ])

    try:
        proc = await asyncio.to_thread(
            subprocess.run,
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0 and not list(out_dir.glob("frame_*.jpg")):
            return f"Error extracting video frames: {proc.stderr[:400]}"

        # Read generated frames
        frame_files = sorted(out_dir.glob("frame_*.jpg"))
        if not frame_files:
            return f"No frames could be extracted from video '{target.name}'. {proc.stderr[:200]}"

        interval_desc = f"~{1/fps:.1f}s interval" if fps < 1 else f"{fps} fps"
        intro_text = (
            f"{install_notice}Video '{target.name}' analyzed successfully.\n"
            f"File info: {metadata_summary}\n"
            f"Extracted {len(frame_files)} sample frames ({interval_desc}):"
        )

        content_list: List[Dict[str, Any]] = [
            {"type": "text", "text": intro_text}
        ]

        for i, f_path in enumerate(frame_files):
            try:
                frame_bytes = f_path.read_bytes()
                opt_frame, opt_mime, _ = optimize_image_for_vision(frame_bytes, max_dimension=960, quality=70)
                b64_frame = base64.b64encode(opt_frame).decode("ascii")
                content_list.append({
                    "type": "image",
                    "data": b64_frame,
                    "mimeType": opt_mime,
                })
            except Exception:
                pass

        return {"content": content_list}

    except subprocess.TimeoutExpired:
        return f"Error: Frame extraction timed out after 30 seconds for '{target.name}'."
    except Exception as e:
        return f"Error processing video '{target.name}': {e}"
    finally:
        # Clean up extracted frame files
        try:
            shutil.rmtree(out_dir, ignore_errors=True)
        except Exception:
            pass
