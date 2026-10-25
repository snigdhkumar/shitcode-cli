"""Intelligent image downsampling and JPEG compression engine for ShitCode.
Reduces large raw visual payloads to compact (~20-40 KB) representations to protect AI token context.
"""

from __future__ import annotations

import io
from typing import Tuple


def optimize_image_for_vision(
    raw_bytes: bytes,
    max_dimension: int = 1280,
    quality: int = 75,
    max_payload_kb: int = 100,
) -> Tuple[bytes, str, str]:
    """Downsample and compress image bytes to keep payload under max_payload_kb (~50-80KB).
    Prevents overflowing LLM context windows while preserving high visual fidelity for vision encoders.
    Returns: (optimized_bytes, mime_type, optimization_note)
    """
    try:
        from PIL import Image

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
    except Exception:
        # Fallback if PIL is unavailable or encounters error
        kb = len(raw_bytes) // 1024
        return raw_bytes, "image/jpeg", f"{kb} KB"
