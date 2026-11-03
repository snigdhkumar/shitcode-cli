"""Window manager forwarder for backward compatibility."""
from tools.desktop.window import (
    find_window_hwnd,
    focus_desktop_window,
    list_desktop_windows,
    set_desktop_window_state,
    window_focus,
    window_state,
    windows_list,
)

__all__ = [
    "windows_list",
    "window_focus",
    "window_state",
    "list_desktop_windows",
    "focus_desktop_window",
    "set_desktop_window_state",
    "find_window_hwnd",
]
