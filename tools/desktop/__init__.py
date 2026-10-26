"""Desktop & Computer Control Automation Package for ShitCode.
Exports Anthropic-standard computer control, compound batch actions, and high-speed desktop visual inspection tools.
"""

from __future__ import annotations

from tools.desktop.actions import (
    clipboard_read,
    clipboard_write,
    computer,
    computer_actions,
    desktop_inspect,
    system_info,
    window_focus,
    window_state,
    windows_list,
)
from tools.desktop.controller import InputController
from tools.desktop.screen import ScreenManager

__all__ = [
    "computer",
    "computer_actions",
    "desktop_inspect",
    "windows_list",
    "window_focus",
    "window_state",
    "clipboard_write",
    "clipboard_read",
    "system_info",
    "InputController",
    "ScreenManager",
]
