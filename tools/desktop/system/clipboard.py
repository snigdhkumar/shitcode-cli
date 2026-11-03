"""High-Speed Clipboard Operations & Instant Paste Engine for Windows and Linux.
Enables fast, error-free text and code clipboard exchange.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from typing import Any, Dict

logger = logging.getLogger("shitcode.tools.desktop.system.clipboard")


def copy_to_clipboard(text: str) -> Dict[str, Any]:
    """Copy text string to OS clipboard with native Win32 retry loop and pyperclip fallback."""
    copied = False
    last_err = None

    if sys.platform == "win32":
        for _ in range(5):
            try:
                import win32clipboard
                import win32con

                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
                win32clipboard.CloseClipboard()
                copied = True
                break
            except Exception as e:
                last_err = e
                time.sleep(0.03)

    if not copied:
        try:
            import pyperclip
            for _ in range(3):
                try:
                    pyperclip.copy(text)
                    copied = True
                    break
                except Exception as e:
                    last_err = e
                    time.sleep(0.03)
        except Exception as e:
            last_err = e

    time.sleep(0.02)
    if not copied:
        return {"success": False, "ok": False, "error": f"Failed to copy to clipboard: {last_err}."}

    return {
        "success": True,
        "ok": True,
        "text": text,
        "length": len(text),
        "message": f"Copied {len(text)} characters to system clipboard.",
    }


def read_from_clipboard() -> Dict[str, Any]:
    """Read current text from OS clipboard with native Win32 retry loop and pyperclip fallback."""
    content: str | None = None
    last_err = None

    if sys.platform == "win32":
        for _ in range(5):
            try:
                import win32clipboard
                import win32con

                win32clipboard.OpenClipboard()
                if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                    data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                    if data is not None:
                        content = data
                win32clipboard.CloseClipboard()
                if content is not None:
                    break
            except Exception as e:
                last_err = e
                time.sleep(0.03)

    if content is None:
        try:
            import pyperclip
            for _ in range(3):
                try:
                    p_val = pyperclip.paste()
                    if p_val is not None:
                        content = p_val
                        break
                except Exception as e:
                    last_err = e
                    time.sleep(0.03)
        except Exception as e:
            last_err = e

    if content is None:
        return {"success": False, "ok": False, "content": "", "text": "", "error": f"Failed to read clipboard: {last_err}"}

    return {
        "success": True,
        "ok": True,
        "content": content,
        "text": content,
        "length": len(content),
        "message": f"Read {len(content)} characters from system clipboard.",
    }


def paste_text_via_clipboard(text: str) -> Dict[str, Any]:
    """Copy text to clipboard and simulate Ctrl+V instant paste."""
    res = copy_to_clipboard(text)
    if not res.get("success"):
        return res
    from tools.desktop.input import InputController
    ctrl = InputController.get_instance()
    ctrl.hotkey("ctrl", "v")
    return {"success": True, "ok": True, "pasted": True, "length": len(text)}


async def clipboard_write(text: str = "", content: str = "") -> Dict[str, Any]:
    """Write text to system clipboard (supports both 'text' and 'content' args)."""
    payload = text if text else content
    return copy_to_clipboard(payload)


async def clipboard_read() -> Dict[str, Any]:
    """Read text from system clipboard."""
    return read_from_clipboard()
