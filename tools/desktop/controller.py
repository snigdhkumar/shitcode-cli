"""Input controller forwarder for backward compatibility."""
from tools.desktop.input import (
    InputController,
    get_linux_display_server,
    get_pyautogui,
    has_gui_display,
    map_key_linux,
    map_key_win,
)

__all__ = [
    "InputController",
    "has_gui_display",
    "get_pyautogui",
    "map_key_win",
    "map_key_linux",
    "get_linux_display_server",
]
