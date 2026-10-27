"""Cross-Platform Window Discovery, Activation, and State Controller for Windows and Linux.
Provides deterministic window focus, geometry queries, and state management.
"""

from __future__ import annotations

import ctypes
import logging
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional

logger = logging.getLogger("shitcode.tools.desktop.windows")
_IS_WIN = sys.platform == "win32"
_IS_LINUX = sys.platform.startswith("linux")


def list_desktop_windows() -> List[Dict[str, Any]]:
    """List all open desktop windows with title, process name, PID, and geometry.
    Works natively on Windows (via win32gui) and Linux (via wmctrl).
    """
    windows: List[Dict[str, Any]] = []

    if _IS_WIN:
        try:
            import win32gui
            import win32process

            def _enum_cb(hwnd: int, extra: list) -> bool:
                try:
                    if win32gui.IsWindowVisible(hwnd):
                        title = win32gui.GetWindowText(hwnd).strip()
                        if title:
                            rect = win32gui.GetWindowRect(hwnd)
                            w = rect[2] - rect[0]
                            h = rect[3] - rect[1]
                            if w > 30 and h > 30:
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
            logger.debug(f"Win32 EnumWindows notice: {e}")

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
            logger.debug(f"Linux wmctrl notice: {e}")

    return windows


def focus_desktop_window(
    title: Optional[str] = None,
    window_id: Optional[int | str] = None,
) -> Dict[str, Any]:
    """Bring target application window to the foreground and activate it.
    
    Args:
        title: Substring matching the window title (case-insensitive).
        window_id: Exact window handle/ID.
    """
    if not title and not window_id:
        return {"success": False, "error": "Either 'title' or 'window_id' must be specified."}

    if _IS_WIN:
        try:
            import win32con
            import win32gui
            import win32process

            target_hwnd: Optional[int] = None
            if window_id:
                try:
                    target_hwnd = int(window_id)
                except ValueError:
                    pass

            if not target_hwnd and title:
                t_lower = title.lower().strip()

                def _find_cb(hwnd: int, extra: list) -> bool:
                    nonlocal target_hwnd
                    try:
                        if win32gui.IsWindowVisible(hwnd):
                            txt = win32gui.GetWindowText(hwnd).strip()
                            if txt and t_lower in txt.lower():
                                target_hwnd = hwnd
                                return False
                    except Exception:
                        pass
                    return True

                try:
                    win32gui.EnumWindows(_find_cb, [])
                except Exception:
                    pass

            if not target_hwnd:
                return {"success": False, "error": f"No visible window found matching '{title or window_id}'."}

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

                try:
                    win32gui.SetForegroundWindow(target_hwnd)
                except Exception:
                    pass
                try:
                    ctypes.windll.user32.BringWindowToTop(target_hwnd)
                except Exception:
                    pass
                try:
                    ctypes.windll.user32.SetFocus(target_hwnd)
                except Exception:
                    pass
            finally:
                if attached:
                    ctypes.windll.user32.AttachThreadInput(current_thread, target_thread, False)

            matched_title = win32gui.GetWindowText(target_hwnd)
            return {
                "success": True,
                "window_id": target_hwnd,
                "title": matched_title,
                "message": f"Successfully focused window '{matched_title}' (HWND: {target_hwnd}).",
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to focus window: {e}"}

    elif _IS_LINUX:
        try:
            if window_id:
                subprocess.check_call(["wmctrl", "-i", "-a", str(window_id)], stderr=subprocess.DEVNULL)
                return {"success": True, "window_id": window_id, "message": f"Focused window ID '{window_id}' via wmctrl."}
            elif title:
                subprocess.check_call(["wmctrl", "-a", title], stderr=subprocess.DEVNULL)
                return {"success": True, "title": title, "message": f"Focused window matching '{title}' via wmctrl."}
        except Exception as e:
            try:
                if title:
                    subprocess.check_call(["xdotool", "search", "--onlyvisible", "--name", title, "windowactivate"], stderr=subprocess.DEVNULL)
                    return {"success": True, "title": title, "message": f"Focused window matching '{title}' via xdotool."}
            except Exception:
                pass
            return {"success": False, "error": f"Failed to focus window on Linux: {e}"}

    return {"success": False, "error": f"Unsupported platform '{sys.platform}' for window management."}


def set_desktop_window_state(
    action: str,
    title: Optional[str] = None,
    window_id: Optional[int | str] = None,
) -> Dict[str, Any]:
    """Change window state (maximize, minimize, restore, close)."""
    act = (action or "").lower().strip()
    if act not in ("maximize", "minimize", "restore", "close"):
        return {"success": False, "error": f"Invalid state action '{action}'. Choices: maximize, minimize, restore, close."}

    if _IS_WIN:
        try:
            import win32con
            import win32gui

            target_hwnd: Optional[int] = None
            if window_id:
                target_hwnd = int(window_id)
            elif title:
                t_lower = title.lower().strip()

                def _find_cb(hwnd: int, extra: list) -> bool:
                    nonlocal target_hwnd
                    if win32gui.IsWindowVisible(hwnd):
                        txt = win32gui.GetWindowText(hwnd).strip()
                        if txt and t_lower in txt.lower():
                            target_hwnd = hwnd
                            return False
                    return True

                try:
                    win32gui.EnumWindows(_find_cb, [])
                except Exception:
                    pass

            if not target_hwnd:
                return {"success": False, "error": f"No window found matching '{title or window_id}'."}

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
                "window_id": target_hwnd,
                "title": matched_title,
                "action": act,
                "message": f"Window '{matched_title}' state changed to '{act}'.",
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to set window state: {e}"}

    elif _IS_LINUX:
        try:
            target = ["-r", title] if title else ["-i", "-r", str(window_id)]
            if act == "maximize":
                subprocess.check_call(["wmctrl"] + target + ["-b", "add,maximized_vert,maximized_horz"], stderr=subprocess.DEVNULL)
            elif act == "minimize":
                subprocess.check_call(["wmctrl"] + target + ["-b", "add,hidden"], stderr=subprocess.DEVNULL)
            elif act == "restore":
                subprocess.check_call(["wmctrl"] + target + ["-b", "remove,maximized_vert,maximized_horz,hidden"], stderr=subprocess.DEVNULL)
            elif act == "close":
                subprocess.check_call(["wmctrl"] + target + ["-c"], stderr=subprocess.DEVNULL)
            return {"success": True, "action": act, "message": f"Window '{title or window_id}' state set to '{act}' via wmctrl."}
        except Exception as e:
            return {"success": False, "error": f"Failed to set Linux window state: {e}"}

    return {"success": False, "error": f"Unsupported platform '{sys.platform}'."}
