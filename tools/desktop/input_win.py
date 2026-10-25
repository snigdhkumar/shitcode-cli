"""Windows Hardware Input Dispatcher with Per-Monitor DPI Awareness.
Uses pyautogui and Win32 SendInput with accurate high-DPI coordinate positioning.
"""

from __future__ import annotations

import ctypes
import logging
import sys
from typing import Optional, Sequence

logger = logging.getLogger("shitcode.tools.desktop.input_win")

# Windows virtual key mappings from Anthropic/X11 standard names
WIN_KEY_MAP = {
    "return": "enter",
    "enter": "enter",
    "backspace": "backspace",
    "delete": "delete",
    "tab": "tab",
    "space": "space",
    "escape": "esc",
    "esc": "esc",
    "super_l": "win",
    "super_r": "win",
    "super": "win",
    "win": "win",
    "control_l": "ctrl",
    "control_r": "ctrl",
    "control": "ctrl",
    "ctrl": "ctrl",
    "alt_l": "alt",
    "alt_r": "alt",
    "alt": "alt",
    "shift_l": "shift",
    "shift_r": "shift",
    "shift": "shift",
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
    "page_up": "pageup",
    "page_down": "pagedown",
    "home": "home",
    "end": "end",
    "caps_lock": "capslock",
    "num_lock": "numlock",
    "scroll_lock": "scrolllock",
    "print_screen": "printscreen",
    "f1": "f1",
    "f2": "f2",
    "f3": "f3",
    "f4": "f4",
    "f5": "f5",
    "f6": "f6",
    "f7": "f7",
    "f8": "f8",
    "f9": "f9",
    "f10": "f10",
    "f11": "f11",
    "f12": "f12",
}


def init_windows_dpi():
    """Enable Per-Monitor DPI Awareness on Windows so physical pixel coordinates match display resolution."""
    if sys.platform != "win32":
        return
    try:
        # PROCESS_PER_MONITOR_DPI_AWARE = 2
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        logger.debug("Enabled Windows Per-Monitor DPI Awareness (v2).")
    except Exception:
        try:
            # Fallback to system DPI aware
            ctypes.windll.user32.SetProcessDPIAware()
            logger.debug("Enabled Windows System DPI Awareness.")
        except Exception as e:
            logger.debug(f"DPI awareness initialization notice: {e}")


# Initialize DPI awareness as soon as module is imported on Windows
init_windows_dpi()


def map_key_win(key_name: str) -> str:
    """Normalize incoming key string to Windows pyautogui key identifier."""
    cleaned = key_name.strip().lower()
    return WIN_KEY_MAP.get(cleaned, cleaned)
