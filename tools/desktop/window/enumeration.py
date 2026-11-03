"""Window Enumeration & Active Window Census.
Filters non-agent visible windows (cloaked DWM frames, zero-size, tool windows).
"""

from __future__ import annotations

import ctypes
import logging
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

from tools.desktop.accessibility.session import ensure_desktop_session

logger = logging.getLogger("shitcode.tools.desktop.window.enumeration")
_IS_WIN = sys.platform == "win32"
_IS_LINUX = sys.platform.startswith("linux")

DWMWA_CLOAKED = 14
WS_EX_TOOLWINDOW = 0x00000080
GWL_EXSTYLE = -20


def is_window_cloaked(hwnd: int) -> bool:
    """Check if window is cloaked by DWM (e.g. suspended UWP apps or virtual desktops)."""
    if not _IS_WIN:
        return False
    try:
        cloaked = ctypes.c_int(0)
        res = ctypes.windll.dwmapi.DwmGetWindowAttribute(
            hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
        )
        return res == 0 and cloaked.value != 0
    except Exception:
        return False


def is_tool_window(hwnd: int) -> bool:
    """Check if window is an auxiliary tool window (WS_EX_TOOLWINDOW)."""
    if not _IS_WIN:
        return False
    try:
        ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        return bool(ex_style & WS_EX_TOOLWINDOW)
    except Exception:
        return False


def list_desktop_windows() -> List[Dict[str, Any]]:
    """Enumerate top-level user windows passing census criteria."""
    ensure_desktop_session()
    windows: List[Dict[str, Any]] = []

    if _IS_WIN:
        try:
            import win32gui
            import win32process

            def _enum_cb(hwnd: int, extra: list) -> bool:
                try:
                    if win32gui.IsWindowVisible(hwnd):
                        rect = win32gui.GetWindowRect(hwnd)
                        w = rect[2] - rect[0]
                        h = rect[3] - rect[1]
                        if w > 10 and h > 10 and not is_window_cloaked(hwnd) and not is_tool_window(hwnd):
                            title = win32gui.GetWindowText(hwnd).strip()
                            if title:
                                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                                extra.append({
                                    "id": hwnd,
                                    "title": title,
                                    "pid": pid,
                                    "bounds": [rect[0], rect[1], w, h],
                                })
                except Exception:
                    pass
                return True

            win32gui.EnumWindows(_enum_cb, windows)
        except Exception as e:
            logger.debug(f"EnumWindows error: {e}")

    elif _IS_LINUX:
        try:
            out = subprocess.check_output(["wmctrl", "-l", "-G", "-p"], text=True, stderr=subprocess.DEVNULL)
            for line in out.strip().splitlines():
                parts = line.split(maxsplit=8)
                if len(parts) >= 8:
                    windows.append({
                        "id": parts[0],
                        "desktop": parts[1],
                        "pid": int(parts[2]),
                        "bounds": [int(parts[3]), int(parts[4]), int(parts[5]), int(parts[6])],
                        "title": parts[7] if len(parts) > 7 else "",
                    })
        except Exception as e:
            logger.debug(f"Linux wmctrl error: {e}")

    return windows


def find_window_hwnd(app_name: Optional[str] = None, window_id: Optional[str | int] = None) -> Optional[int]:
    """Find target window HWND by app name, window ID, or top-level active window."""
    if not _IS_WIN:
        return None
    try:
        import win32gui

        if window_id:
            try:
                hwnd = int(str(window_id), 0)
                if win32gui.IsWindow(hwnd):
                    return hwnd
            except ValueError:
                pass
            return None

        if app_name:
            app_lower = app_name.lower().strip()
            for win in list_desktop_windows():
                if app_lower in win["title"].lower():
                    return win["id"]
            return None

        # Default when neither app_name nor window_id is specified: Topmost census window
        census = list_desktop_windows()
        if census:
            fg = win32gui.GetForegroundWindow()
            for win in census:
                if win["id"] == fg:
                    return fg
            return census[0]["id"]
    except Exception as e:
        logger.debug(f"find_window_hwnd error: {e}")
    return None
