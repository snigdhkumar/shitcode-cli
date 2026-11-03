"""Window State & Focus Manager.
Handles window foreground activation with AttachThreadInput and state changes.
"""

from __future__ import annotations

import ctypes
import logging
import subprocess
import sys
from typing import Any, Dict, Optional

from tools.desktop.window.enumeration import find_window_hwnd, list_desktop_windows

logger = logging.getLogger("shitcode.tools.desktop.window.manager")
_IS_WIN = sys.platform == "win32"
_IS_LINUX = sys.platform.startswith("linux")


def focus_desktop_window(
    title: Optional[str] = None,
    window_id: Optional[int | str] = None,
) -> Dict[str, Any]:
    """Bring target application window to foreground."""
    if not title and not window_id:
        return {"success": False, "ok": False, "error": "Either 'title' or 'window_id' must be specified."}

    if _IS_WIN:
        try:
            import win32con
            import win32gui
            import win32process

            target_hwnd = find_window_hwnd(app_name=title, window_id=window_id)
            if not target_hwnd:
                return {"success": False, "ok": False, "error": f"No visible window found matching '{title or window_id}'."}

            current_thread = ctypes.windll.kernel32.GetCurrentThreadId()
            target_thread, _ = win32process.GetWindowThreadProcessId(target_hwnd)

            attached = False
            try:
                if current_thread and target_thread and current_thread != target_thread:
                    attached = bool(ctypes.windll.user32.AttachThreadInput(current_thread, target_thread, True))

                if win32gui.IsIconic(target_hwnd):
                    win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
                else:
                    win32gui.ShowWindow(target_hwnd, win32con.SW_SHOW)

                win32gui.SetForegroundWindow(target_hwnd)
                ctypes.windll.user32.BringWindowToTop(target_hwnd)
            finally:
                if attached:
                    ctypes.windll.user32.AttachThreadInput(current_thread, target_thread, False)

            matched_title = win32gui.GetWindowText(target_hwnd)
            return {
                "success": True,
                "ok": True,
                "window_id": target_hwnd,
                "title": matched_title,
                "message": f"Successfully focused window '{matched_title}' (HWND: {target_hwnd}).",
            }
        except Exception as e:
            return {"success": False, "ok": False, "error": f"Failed to focus window: {e}"}

    elif _IS_LINUX:
        try:
            if window_id:
                subprocess.check_call(["wmctrl", "-i", "-a", str(window_id)], stderr=subprocess.DEVNULL)
                return {"success": True, "ok": True, "window_id": window_id, "message": f"Focused window ID '{window_id}'."}
            elif title:
                subprocess.check_call(["wmctrl", "-a", title], stderr=subprocess.DEVNULL)
                return {"success": True, "ok": True, "title": title, "message": f"Focused window matching '{title}'."}
        except Exception as e:
            return {"success": False, "ok": False, "error": f"Failed to focus window on Linux: {e}"}

    return {"success": False, "ok": False, "error": f"Unsupported platform '{sys.platform}'."}


def set_desktop_window_state(
    action: str,
    title: Optional[str] = None,
    window_id: Optional[int | str] = None,
) -> Dict[str, Any]:
    """Change window state (maximize, minimize, restore, close)."""
    act = (action or "").lower().strip()
    if act not in ("maximize", "minimize", "restore", "close"):
        return {"success": False, "ok": False, "error": f"Invalid state action '{action}'. Choices: maximize, minimize, restore, close."}

    if _IS_WIN:
        try:
            import win32con
            import win32gui

            target_hwnd = find_window_hwnd(app_name=title, window_id=window_id)
            if not target_hwnd:
                return {"success": False, "ok": False, "error": f"No visible window found matching '{title or window_id}'."}

            if act == "maximize":
                win32gui.ShowWindow(target_hwnd, win32con.SW_MAXIMIZE)
            elif act == "minimize":
                win32gui.ShowWindow(target_hwnd, win32con.SW_MINIMIZE)
            elif act == "restore":
                win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
            elif act == "close":
                win32gui.PostMessage(target_hwnd, win32con.WM_CLOSE, 0, 0)

            matched_title = win32gui.GetWindowText(target_hwnd)
            return {
                "success": True,
                "ok": True,
                "action": act,
                "window_id": target_hwnd,
                "title": matched_title,
                "message": f"Applied '{act}' to window '{matched_title}' (HWND: {target_hwnd}).",
            }
        except Exception as e:
            return {"success": False, "ok": False, "error": f"Failed to set window state: {e}"}

    elif _IS_LINUX:
        try:
            flag_map = {"maximize": "-b,add,maximized_vert,maximized_horz", "restore": "-b,remove,maximized_vert,maximized_horz", "close": "-c"}
            if act in flag_map and (window_id or title):
                cmd = ["wmctrl"] + (["-i", "-r", str(window_id)] if window_id else ["-r", str(title)]) + flag_map[act].split(",")
                subprocess.check_call(cmd, stderr=subprocess.DEVNULL)
                return {"success": True, "ok": True, "action": act, "message": f"Applied '{act}' via wmctrl."}
        except Exception as e:
            return {"success": False, "ok": False, "error": f"Failed to set window state on Linux: {e}"}

    return {"success": False, "ok": False, "error": f"Unsupported platform '{sys.platform}'."}
