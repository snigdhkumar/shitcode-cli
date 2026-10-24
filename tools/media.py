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


@with_error_reporting("image_inspect")
async def image_inspect(path: str, max_dimension: int = 1920) -> Any:
    """Inspect and visually analyze any local image file on the host machine.
    
    Returns standard MCP multimodal image blocks directly to the AI vision encoder.
    """
    target = _resolve_media_path(path)
    if not target.is_file():
        return f"Error: Image file not found at '{path}'."

    ext = target.suffix.lower()
    valid_exts = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
        ".svg": "image/svg+xml",
    }
    mime_type = valid_exts.get(ext) or mimetypes.guess_type(str(target))[0] or "image/png"

    try:
        raw_bytes = target.read_bytes()
        size_kb = len(raw_bytes) // 1024

        b64_data = base64.b64encode(raw_bytes).decode("ascii")

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Image '{target.name}' loaded successfully ({size_kb} KB, format: {ext.lstrip('.')}, MIME: {mime_type})."
                },
                {
                    "type": "image",
                    "data": b64_data,
                    "mimeType": mime_type
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
                b64_frame = base64.b64encode(frame_bytes).decode("ascii")
                content_list.append({
                    "type": "image",
                    "data": b64_frame,
                    "mimeType": "image/jpeg",
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
