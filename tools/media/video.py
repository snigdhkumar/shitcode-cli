"""Paginated chunked video inspection engine with on-demand FFmpeg provisioning.
Processes videos in sequential temporal windows with sub-second keyframe fast seeking.
"""

from __future__ import annotations

import asyncio
import base64
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.ffmpeg_installer import ensure_ffmpeg_installed
from core.reporter import with_error_reporting
from tools.media.image import resolve_media_path
from tools.media.optimizer import optimize_image_for_vision

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
TEMP_DIR = ROOT_DIR / ".temp"


def parse_timestamp(val: Any) -> float:
    """Parse seconds, float string, or HH:MM:SS string to float seconds."""
    if val is None:
        return 0.0
    s = str(val).strip().strip("\"'")
    if not s:
        return 0.0
    if ":" in s:
        parts = s.split(":")
        try:
            if len(parts) == 3:
                return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
            elif len(parts) == 2:
                return float(parts[0]) * 60 + float(parts[1])
        except Exception:
            return 0.0
    try:
        return max(0.0, float(s))
    except Exception:
        return 0.0


def format_timestamp(seconds: float) -> str:
    """Convert float seconds to clean HH:MM:SS format."""
    total_sec = max(0.0, float(seconds))
    h = int(total_sec // 3600)
    m = int((total_sec % 3600) // 60)
    s = int(total_sec % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


@with_error_reporting("video_inspect")
async def video_inspect(
    path: str,
    start_time: Optional[str] = None,
    fps: float = 0.5,
    max_frames: int = 8,
    duration: Optional[str] = None,
) -> Any:
    """Inspect and visually analyze local video files in chunked temporal windows (default: 8 frames covering 16 seconds at 0.5 fps).
    
    Returns video metadata, individual frame timestamps, and a 'Next Window' pagination cursor
    to inspect subsequent segments or jump to specific timestamps without overflowing token context.
    """
    target = resolve_media_path(path)
    if not target.is_file():
        return f"Error: Video file not found at '{path}'."

    # 1. Ensure universal FFmpeg is ready on demand
    ok, ffmpeg_exe, was_fresh = await asyncio.to_thread(ensure_ffmpeg_installed)
    if not ok:
        return f"Error initializing video engine: {ffmpeg_exe}"

    install_notice = "[Notice: FFmpeg video engine was downloaded on demand for first-time use.] " if was_fresh else ""

    # 2. Extract video metadata
    dur_str = "unknown duration"
    res_str = "unknown resolution"
    total_sec = 0.0
    try:
        probe = subprocess.run([ffmpeg_exe, "-i", str(target)], capture_output=True, text=True, timeout=10)
        output_txt = probe.stderr or probe.stdout or ""
        dur_match = re.search(r"Duration:\s*(\d{2}):(\d{2}):(\d{2}\.\d+)", output_txt)
        res_match = re.search(r"Video:.*,\s*(\d{3,5}x\d{3,5})", output_txt)
        if dur_match:
            h, m, s = float(dur_match.group(1)), float(dur_match.group(2)), float(dur_match.group(3))
            total_sec = h * 3600 + m * 60 + s
            dur_str = format_timestamp(total_sec)
        if res_match:
            res_str = res_match.group(1)
    except Exception as meta_err:
        dur_str = f"notice: {meta_err}"

    # 3. Parameter validation and chunk boundaries
    max_frames = max(1, min(int(max_frames), 16))
    fps = max(0.05, min(float(fps), 5.0))
    start_sec = parse_timestamp(start_time)

    session_id = f"video_{int(time.time())}_{os.getpid()}"
    out_dir = TEMP_DIR / session_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # Fast seeking: place -ss before -i for instantaneous keyframe seeking
    cmd = [ffmpeg_exe, "-y"]
    if start_sec > 0:
        cmd.extend(["-ss", f"{start_sec:.3f}"])
    cmd.extend(["-i", str(target)])
    if duration:
        cmd.extend(["-t", str(duration).strip()])

    cmd.extend([
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
            return f"No frames could be extracted from video '{target.name}' at timestamp {format_timestamp(start_sec)}. {proc.stderr[:200]}"

        frame_interval = 1.0 / fps
        window_duration = len(frame_files) * frame_interval
        window_end_sec = start_sec + window_duration

        # Compute pagination cursor and remaining video duration
        has_more = False
        next_start_time = None
        remaining_desc = ""

        if total_sec > 0:
            if window_end_sec < total_sec - 0.5:
                has_more = True
                next_start_sec = round(window_end_sec, 2)
                next_start_time = format_timestamp(next_start_sec)
                remaining_sec = max(0.0, round(total_sec - window_end_sec, 1))
                remaining_desc = f" ({remaining_sec}s remaining after this window)"
            else:
                window_end_sec = min(total_sec, window_end_sec)
        elif len(frame_files) == max_frames:
            has_more = True
            next_start_sec = round(window_end_sec, 2)
            next_start_time = format_timestamp(next_start_sec)

        timeline_lines = []
        for i in range(len(frame_files)):
            f_sec = start_sec + (i * frame_interval)
            timeline_lines.append(f"- Frame {i + 1}: [{format_timestamp(f_sec)}]")
        timeline_text = "\n".join(timeline_lines)

        if has_more and next_start_time:
            pagination_text = (
                f"PAGINATION STATUS:\n"
                f"- Has More Frames: True{remaining_desc}\n"
                f"- Next Window Start Time: '{next_start_time}'\n"
                f"Tip: To inspect the next segment, call video_inspect with start_time='{next_start_time}'. "
                f"To jump to any specific moment, specify your desired start_time."
            )
        else:
            pagination_text = "PAGINATION STATUS:\n- Has More Frames: False (reached end of video)"

        intro_text = (
            f"{install_notice}Video '{target.name}' analyzed successfully (Chunk Window).\n"
            f"Metadata: Duration: {dur_str} | Resolution: {res_str}\n"
            f"Current Window: [{format_timestamp(start_sec)}] to [{format_timestamp(window_end_sec)}] "
            f"({len(frame_files)} frames at {fps} fps, ~{frame_interval:.1f}s interval):\n\n"
            f"Frame Timestamps:\n{timeline_text}\n\n"
            f"{pagination_text}"
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
