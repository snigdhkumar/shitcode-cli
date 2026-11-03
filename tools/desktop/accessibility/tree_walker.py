"""Cross-Platform Accessibility Tree Walker Coordinator.
Dispatches to Windows UIA or Linux AT-SPI with session guarantees.
"""

from __future__ import annotations

import logging
import sys
from typing import Any, Dict, List, Optional

from tools.desktop.accessibility.atspi_walker import walk_atspi_tree
from tools.desktop.accessibility.ref_map import allocate_snapshot_id
from tools.desktop.accessibility.session import ensure_desktop_session, get_win_uia
from tools.desktop.accessibility.uia_walker import walk_uia_tree
from tools.desktop.window.enumeration import find_window_hwnd

logger = logging.getLogger("shitcode.tools.desktop.accessibility.tree_walker")
_IS_WIN = sys.platform == "win32"
_IS_LINUX = sys.platform.startswith("linux")


async def capture_tree_snapshot(
    app_name: Optional[str] = None,
    window_id: Optional[str | int] = None,
    interactive_only: bool = True,
    max_elements: int = 60,
) -> Dict[str, Any]:
    """Capture accessibility snapshot for target window or topmost active application."""
    ensure_desktop_session()
    snap_id = allocate_snapshot_id()

    if _IS_WIN:
        try:
            import win32gui
            uia = get_win_uia()
            if not uia:
                return {"ok": False, "success": False, "error": "Windows UIAutomationCore interface is unavailable."}

            hwnd = find_window_hwnd(app_name=app_name, window_id=window_id)
            if not hwnd:
                return {
                    "ok": False,
                    "success": False,
                    "error": f"No active window found matching app_name='{app_name or ''}' or window_id='{window_id or ''}'."
                }

            window_title = win32gui.GetWindowText(hwnd).strip() or "Active Window"
            root_elem = uia.ElementFromHandle(hwnd)
            if not root_elem:
                return {"ok": False, "success": False, "error": f"Unable to attach UIAutomation to window '{window_title}' (HWND: {hwnd})."}

            walker = uia.ControlViewWalker
            elements = walk_uia_tree(
                walker=walker,
                root_elem=root_elem,
                hwnd=hwnd,
                interactive_only=interactive_only,
                max_elements=max_elements,
            )

            return {
                "ok": True,
                "success": True,
                "snapshot_id": snap_id,
                "window": window_title,
                "window_id": hwnd,
                "elements_count": len(elements),
                "elements": elements,
            }
        except Exception as e:
            return {"ok": False, "success": False, "error": f"Windows accessibility snapshot error: {e}"}

    elif _IS_LINUX:
        try:
            import pyatspi
            reg = pyatspi.Registry
            desktop = reg.getDesktop(0)
            elements = walk_atspi_tree(
                root_accessible=desktop,
                interactive_only=interactive_only,
                max_elements=max_elements,
            )
            return {
                "ok": True,
                "success": True,
                "snapshot_id": snap_id,
                "window": "Linux Desktop",
                "elements_count": len(elements),
                "elements": elements,
            }
        except Exception as e:
            return {"ok": False, "success": False, "error": f"Linux AT-SPI error: {e}"}

    return {"ok": False, "success": False, "error": f"Accessibility engine not supported on {sys.platform}."}
