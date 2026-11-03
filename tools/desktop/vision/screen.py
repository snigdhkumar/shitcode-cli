"""High-Speed Screen Capture and Geometry Engine.
Uses mss for sub-10ms framebuffer capture with PIL downsampling and base64 export.
"""

from __future__ import annotations

import base64
import io
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import mss
from PIL import Image
from tools.desktop.accessibility.session import ensure_desktop_session

logger = logging.getLogger("shitcode.tools.desktop.vision.screen")

SCREENSHOTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


class ScreenManager:
    """Manages high-speed display capture and multi-monitor bounds."""

    _instance: Optional[ScreenManager] = None

    def __init__(self):
        self._sct: Optional[Any] = None

    @classmethod
    def get_instance(cls) -> ScreenManager:
        if cls._instance is None:
            cls._instance = ScreenManager()
        return cls._instance

    def _get_sct(self) -> Any:
        if self._sct is None:
            if sys.platform != "win32" and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
                raise RuntimeError("Screen capture requires an active graphical display (DISPLAY is not set).")
            self._sct = mss.mss()
        return self._sct

    def get_monitors(self) -> List[Dict[str, Any]]:
        try:
            return self._get_sct().monitors
        except Exception:
            return [{"left": 0, "top": 0, "width": 1920, "height": 1080}]

    def get_primary_monitor(self) -> Dict[str, int]:
        monitors = self.get_monitors()
        return monitors[1] if len(monitors) > 1 else monitors[0]

    def capture_screenshot(
        self,
        monitor_idx: Optional[int] = None,
        max_dimension: int = 1280,
        quality: int = 75,
    ) -> Dict[str, Any]:
        """Capture screen frame, downsample for AI vision context, and return standard MCP blocks."""
        ensure_desktop_session()
        monitors = self.get_monitors()
        target_mon = monitors[monitor_idx] if (monitor_idx is not None and monitor_idx < len(monitors)) else self.get_primary_monitor()

        raw_png_bytes = None
        try:
            sct = self._get_sct()
            sct_img = sct.grab(target_mon)
            raw_png_bytes = mss.tools.to_png(sct_img.rgb, sct_img.size)
        except Exception as e:
            logger.debug(f"mss grab fallback: {e}")
            try:
                from PIL import ImageGrab
                bbox = (target_mon["left"], target_mon["top"], target_mon["left"] + target_mon["width"], target_mon["top"] + target_mon["height"])
                pil_img = ImageGrab.grab(bbox=bbox, all_screens=True)
                buf = io.BytesIO()
                pil_img.save(buf, format="PNG")
                raw_png_bytes = buf.getvalue()
            except Exception as grab_err:
                logger.debug(f"PIL ImageGrab error: {grab_err}")
                return {"success": False, "ok": False, "error": f"Screen grab failed: {e}; fallback: {grab_err}"}

        if not raw_png_bytes:
            return {"success": False, "ok": False, "error": "Screen grab produced zero bytes."}

        try:
            # Optimize/resize image
            pil_img = Image.open(io.BytesIO(raw_png_bytes))
            orig_w, orig_h = pil_img.size
            scale = min(1.0, max_dimension / max(orig_w, orig_h))
            if scale < 1.0:
                pil_img = pil_img.resize((int(orig_w * scale), int(orig_h * scale)), Image.Resampling.LANCZOS)

            out_buf = io.BytesIO()
            pil_img.save(out_buf, format="JPEG", quality=quality, optimize=True)
            b64_data = base64.b64encode(out_buf.getvalue()).decode("utf-8")

            return {
                "success": True,
                "ok": True,
                "content": [
                    {"type": "text", "text": f"Screenshot taken: {orig_w}x{orig_h} (scaled to {pil_img.size[0]}x{pil_img.size[1]})."},
                    {"type": "image", "data": b64_data, "mime_type": "image/jpeg"},
                ],
                "display": {
                    "width": orig_w,
                    "height": orig_h,
                    "scaled_width": pil_img.size[0],
                    "scaled_height": pil_img.size[1],
                },
            }
        except Exception as proc_err:
            return {"success": False, "ok": False, "error": f"Image processing failed: {proc_err}"}
