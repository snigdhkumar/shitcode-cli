"""Multimodal Image Inspection Tool for ShitCode.
Provides direct image analysis capabilities returning standard MCP image content blocks.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from core.reporter import with_error_reporting
from tools.media.optimizer import optimize_image_for_vision


def resolve_media_path(path_str: str) -> Path:
    """Resolve relative or absolute media path safely."""
    p = Path(path_str.strip().strip("\"'"))
    if not p.is_absolute():
        p = (Path.cwd() / p).resolve()
    return p


@with_error_reporting("image_inspect")
async def image_inspect(path: str, max_dimension: int = 1280) -> Any:
    """Inspect and visually analyze any local image file on the host machine.
    
    Returns standard MCP multimodal image blocks directly to the AI vision encoder,
    automatically optimized and compressed to prevent overflowing LLM conversation limits.
    """
    target = resolve_media_path(path)
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
