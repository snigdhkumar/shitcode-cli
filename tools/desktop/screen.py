"""High-Speed Screen Capture and Coordinate Rescaling Engine for ShitCode Desktop.
Captures screen frames via mss (direct C memory capture in ~10ms) and handles multi-monitor scaling.
"""

from __future__ import annotations

import base64
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import mss
from tools.media.optimizer import optimize_image_for_vision

logger = logging.getLogger("shitcode.tools.desktop.screen")

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
SCREENSHOTS_DIR = ROOT_DIR / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


class ScreenManager:
    """Manages high-speed display capture, multi-monitor bounds, and coordinate translation."""

    _instance: Optional[ScreenManager] = None

    def __init__(self):
        self._sct = mss.mss()
        self._last_scale_info: Dict[str, Any] = {}

    @classmethod
    def get_instance(cls) -> ScreenManager:
        if cls._instance is None:
            cls._instance = ScreenManager()
        return cls._instance

    def get_monitors(self) -> List[Dict[str, Any]]:
        """Return list of available monitor geometries."""
        return self._sct.monitors

    def get_primary_monitor(self) -> Dict[str, int]:
        """Return the primary monitor bounding box (index 1 in mss, or 0 for entire virtual desktop)."""
        monitors = self._sct.monitors
        if len(monitors) > 1:
            return monitors[1]
        return monitors[0]

    def capture_screenshot(
        self,
        monitor_idx: Optional[int] = None,
        max_dimension: int = 1280,
        quality: int = 75,
        save_file: bool = True,
    ) -> Dict[str, Any]:
        """Capture screen frame, downsample for AI vision context, and return standard MCP image blocks."""
        monitors = self._sct.monitors
        target_mon = monitors[monitor_idx] if (monitor_idx is not None and monitor_idx < len(monitors)) else self.get_primary_monitor()

        phys_w = target_mon["width"]
        phys_h = target_mon["height"]
        phys_left = target_mon["left"]
        phys_top = target_mon["top"]

        raw_png_bytes = None
        grab_error = None

        # 1. Primary: Sub-10ms raw pixel grab via mss
        try:
            sct_img = self._sct.grab(target_mon)
            raw_png_bytes = mss.tools.to_png(sct_img.rgb, sct_img.size)
        except Exception as e:
            grab_error = str(e)
            logger.debug(f"mss screen grab failed: {e}, attempting ImageGrab fallback...")

        # 1b. Fallback: PIL ImageGrab
        if raw_png_bytes is None:
            try:
                from PIL import ImageGrab
                import io
                bbox = (phys_left, phys_top, phys_left + phys_w, phys_top + phys_h)
                pil_img = ImageGrab.grab(bbox=bbox, all_screens=True)
                buf = io.BytesIO()
                pil_img.save(buf, format="PNG")
                raw_png_bytes = buf.getvalue()
            except Exception as e2:
                logger.debug(f"ImageGrab fallback also failed: {e2}")
                if not grab_error:
                    grab_error = str(e2)

        if raw_png_bytes is None:
            return {
                "success": False,
                "error": f"Screen capture unavailable: {grab_error}. Note: The desktop display may be locked, sleeping, or running inside a headless/non-interactive session.",
                "physical_resolution": f"{phys_w}x{phys_h}",
                "content": [
                    {
                        "type": "text",
                        "text": f"Screen capture unavailable: {grab_error}. The host desktop display may be locked, sleeping, or running inside a headless session. Ensure the desktop is awake and unlocked for visual GUI interaction.",
                    }
                ],
            }

        # 2. Downsample and compress to compact JPEG for AI vision context (~30-45 KB)
        opt_bytes, opt_mime, opt_note = optimize_image_for_vision(
            raw_png_bytes,
            max_dimension=max_dimension,
            quality=quality,
        )

        # Determine dimensions of downsampled image for coordinate translation
        try:
            from PIL import Image
            import io
            with Image.open(io.BytesIO(opt_bytes)) as im:
                down_w, down_h = im.size
        except Exception:
            down_w, down_h = phys_w, phys_h

        # Save scale info for remapping AI coordinates back to physical monitor pixels
        self._last_scale_info = {
            "physical_width": phys_w,
            "physical_height": phys_h,
            "physical_left": phys_left,
            "physical_top": phys_top,
            "image_width": down_w,
            "image_height": down_h,
            "scale_x": phys_w / float(down_w) if down_w else 1.0,
            "scale_y": phys_h / float(down_h) if down_h else 1.0,
            "timestamp": time.time(),
        }

        filename = f"desktop_{int(time.time())}.jpg"
        filepath = SCREENSHOTS_DIR / filename
        if save_file:
            try:
                filepath.write_bytes(opt_bytes)
            except Exception as e:
                logger.debug(f"Could not save local screenshot file: {e}")

        b64_data = base64.b64encode(opt_bytes).decode("ascii")

        return {
            "success": True,
            "filename": filename,
            "path": str(filepath),
            "physical_resolution": f"{phys_w}x{phys_h}",
            "ai_image_resolution": f"{down_w}x{down_h}",
            "payload_note": opt_note,
            "scale_info": self._last_scale_info,
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"Desktop screenshot captured ({phys_w}x{phys_h} physical display, "
                        f"AI coordinate canvas: {down_w}x{down_h}, payload: {opt_note})."
                    ),
                },
                {
                    "type": "image",
                    "data": b64_data,
                    "mimeType": opt_mime,
                },
            ],
        }

    def remap_coordinates(self, x: int | float, y: int | float) -> Tuple[int, int]:
        """Convert downsampled AI image coordinates back to physical monitor pixel coordinates."""
        info = self._last_scale_info
        if not info:
            # Fallback to current primary monitor if no scale info cached yet
            mon = self.get_primary_monitor()
            return int(x + mon["left"]), int(y + mon["top"])

        scale_x = info.get("scale_x", 1.0)
        scale_y = info.get("scale_y", 1.0)
        phys_left = info.get("physical_left", 0)
        phys_top = info.get("physical_top", 0)
        phys_w = info.get("physical_width", 1920)
        phys_h = info.get("physical_height", 1080)

        # Scale and offset
        target_x = int(round(float(x) * scale_x)) + phys_left
        target_y = int(round(float(y) * scale_y)) + phys_top

        # Clamp within physical display boundaries
        clamped_x = max(phys_left, min(phys_left + phys_w - 1, target_x))
        clamped_y = max(phys_top, min(phys_top + phys_h - 1, target_y))

        return clamped_x, clamped_y
