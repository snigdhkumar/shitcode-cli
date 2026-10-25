"""Linux Hardware Input Dispatcher with Display Server Detection.
Detects X11 vs Wayland and provides normalized keysym translations.
"""

from __future__ import annotations

import logging
import os
import sys

logger = logging.getLogger("shitcode.tools.desktop.input_linux")

# Linux X11 keysym mappings from Anthropic standard names
LINUX_KEY_MAP = {
    "return": "Return",
    "enter": "Return",
    "backspace": "BackSpace",
    "delete": "Delete",
    "tab": "Tab",
    "space": "space",
    "escape": "Escape",
    "esc": "Escape",
    "super_l": "Super_L",
    "super_r": "Super_R",
    "super": "Super_L",
    "win": "Super_L",
    "control_l": "Control_L",
    "control_r": "Control_R",
    "control": "Control_L",
    "ctrl": "Control_L",
    "alt_l": "Alt_L",
    "alt_r": "Alt_R",
    "alt": "Alt_L",
    "shift_l": "Shift_L",
    "shift_r": "Shift_R",
    "shift": "Shift_L",
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
    "page_up": "Page_Up",
    "page_down": "Page_Down",
    "home": "Home",
    "end": "End",
    "caps_lock": "Caps_Lock",
}


def get_linux_display_server() -> str:
    """Detect whether Linux session is running on X11 or Wayland."""
    if sys.platform != "linux":
        return "not_linux"
    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"
    return "headless"


def map_key_linux(key_name: str) -> str:
    """Normalize incoming key string to Linux X11 keysym or pyautogui key identifier."""
    cleaned = key_name.strip().lower()
    return LINUX_KEY_MAP.get(cleaned, cleaned)
