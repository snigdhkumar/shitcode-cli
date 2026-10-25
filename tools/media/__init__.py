"""Multimodal Vision & Video Engine Package for ShitCode.
Exports local image inspection, paginated chunked video inspection, and intelligent downsampling tools.
"""

from __future__ import annotations

from tools.media.optimizer import optimize_image_for_vision
from tools.media.image import image_inspect, resolve_media_path
from tools.media.video import video_inspect, parse_timestamp, format_timestamp

__all__ = [
    "image_inspect",
    "video_inspect",
    "optimize_image_for_vision",
    "resolve_media_path",
    "parse_timestamp",
    "format_timestamp",
]
