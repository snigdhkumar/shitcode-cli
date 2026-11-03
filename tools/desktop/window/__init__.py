"""Window Enumeration, Focus & State Services.
"""

from typing import Any, Dict, List, Optional

from tools.desktop.window.enumeration import (
    find_window_hwnd,
    list_desktop_windows,
)
from tools.desktop.window.manager import (
    focus_desktop_window,
    set_desktop_window_state,
)


async def windows_list() -> List[Dict[str, Any]]:
    """List open desktop application windows with id, title, and bounds."""
    return list_desktop_windows()


async def window_focus(title: Optional[str] = None, window_id: Optional[int | str] = None) -> Dict[str, Any]:
    """Bring target window to foreground."""
    return focus_desktop_window(title=title, window_id=window_id)


async def window_state(action: str, title: Optional[str] = None, window_id: Optional[int | str] = None) -> Dict[str, Any]:
    """Change window state (maximize, minimize, restore, close)."""
    return set_desktop_window_state(action=action, title=title, window_id=window_id)


__all__ = [
    "windows_list",
    "window_focus",
    "window_state",
    "list_desktop_windows",
    "find_window_hwnd",
    "focus_desktop_window",
    "set_desktop_window_state",
]
