r"""Desktop Session & Thread Attachment.
Connects the worker thread to the interactive desktop session (WinSta0\Default or X11/AT-SPI).
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys
from typing import Any, Optional

logger = logging.getLogger("shitcode.tools.desktop.accessibility.session")
_IS_WIN = sys.platform == "win32"
_IS_LINUX = sys.platform.startswith("linux")

_UIA_CLIENT: Optional[Any] = None


def ensure_desktop_session() -> bool:
    """Ensure the calling thread is attached to the interactive user desktop session."""
    if _IS_WIN:
        try:
            # 0x01FF = GENERIC_ALL access for desktop
            h_desk = ctypes.windll.user32.OpenDesktopW("Default", 0, False, 0x01FF)
            if h_desk:
                ctypes.windll.user32.SetThreadDesktop(h_desk)
                return True
        except Exception as e:
            logger.debug(f"OpenDesktopW notice: {e}")
            return False
    elif _IS_LINUX:
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    return True


def get_win_uia() -> Optional[Any]:
    """Lazily initialize Windows CUIAutomation COM client attached to interactive desktop."""
    global _UIA_CLIENT
    if not _IS_WIN:
        return None
    if _UIA_CLIENT is not None:
        return _UIA_CLIENT

    ensure_desktop_session()
    try:
        import comtypes.client
        comtypes.client.GetModule("UIAutomationCore.dll")
        from comtypes.gen.UIAutomationClient import CUIAutomation, IUIAutomation
        _UIA_CLIENT = comtypes.client.CreateObject(CUIAutomation, interface=IUIAutomation)
        return _UIA_CLIENT
    except Exception as e:
        logger.debug(f"Failed to initialize Windows UIAutomation: {e}")
        return None
