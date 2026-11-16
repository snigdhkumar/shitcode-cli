r"""Desktop Session & Thread Attachment.
Connects the worker thread to the interactive desktop session (WinSta0\Default or X11/AT-SPI).
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys
import threading
from typing import Any, Optional

logger = logging.getLogger("shitcode.tools.desktop.accessibility.session")
_IS_WIN = sys.platform == "win32"
_IS_LINUX = sys.platform.startswith("linux")

_LOCAL = threading.local()


def ensure_desktop_session() -> bool:
    """Ensure the calling thread is attached to the interactive user desktop session."""
    if _IS_WIN:
        try:
            # Check if thread is already attached to interactive desktop
            h_current = ctypes.windll.user32.GetThreadDesktop(ctypes.windll.kernel32.GetCurrentThreadId())
            if h_current:
                return True
            # Fallback for unattached worker/service threads
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
    if not _IS_WIN:
        return None

    client = getattr(_LOCAL, "uia_client", None)
    if client is not None:
        return client

    ensure_desktop_session()
    try:
        import comtypes
        try:
            comtypes.CoInitialize()
        except Exception:
            pass
        import comtypes.client
        comtypes.client.GetModule("UIAutomationCore.dll")
        from comtypes.gen.UIAutomationClient import CUIAutomation, IUIAutomation
        client = comtypes.client.CreateObject(CUIAutomation, interface=IUIAutomation)
        _LOCAL.uia_client = client
        return client
    except Exception as e:
        logger.debug(f"Failed to initialize Windows UIAutomation: {e}")
        return None
