"""Desktop & OS Computer Automation Tools for ShitCode.
Unified suite providing accessibility, vision, window management, input, and system controls.
"""

from tools.desktop.accessibility import (
    desktop_interact,
    desktop_snapshot,
)
from tools.desktop.input import (
    InputController,
    has_gui_display,
)
from tools.desktop.system import (
    clipboard_read,
    clipboard_write,
    copy_to_clipboard,
    get_system_metrics,
    read_from_clipboard,
    system_info,
)
from tools.desktop.vision import (
    ScreenManager,
    computer,
    computer_actions,
    desktop_inspect,
)
from tools.desktop.window import (
    focus_desktop_window,
    list_desktop_windows,
    set_desktop_window_state,
    window_focus,
    window_state,
    windows_list,
)

__all__ = [
    # Primary Tools
    "desktop_snapshot",
    "desktop_interact",
    "computer",
    "computer_actions",
    "desktop_inspect",
    "windows_list",
    "window_focus",
    "window_state",
    "system_info",
    "clipboard_read",
    "clipboard_write",
    # Underlying services & controllers
    "ScreenManager",
    "InputController",
    "has_gui_display",
    "list_desktop_windows",
    "focus_desktop_window",
    "set_desktop_window_state",
    "copy_to_clipboard",
    "read_from_clipboard",
    "get_system_metrics",
]
