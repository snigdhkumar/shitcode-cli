"""Unified Cross-Platform Desktop Input Controller for ShitCode.
Provides hardware mouse and keyboard simulation with failsafe safety.
"""

from __future__ import annotations

import logging
import sys
import time
from typing import Any, Optional, Sequence, Tuple

from tools.desktop.input.linux_input import get_linux_display_server, has_gui_display, map_key_linux
from tools.desktop.input.win_input import map_key_win

logger = logging.getLogger("shitcode.tools.desktop.input")

_IS_WINDOWS = sys.platform == "win32"
_IS_LINUX = sys.platform.startswith("linux")

_pyautogui: Optional[Any] = None
_pyautogui_error: Optional[str] = None


def get_pyautogui() -> Any:
    """Lazily load PyAutoGUI with display availability guards."""
    global _pyautogui, _pyautogui_error
    if _pyautogui is not None:
        return _pyautogui
    if _pyautogui_error is not None:
        raise RuntimeError(_pyautogui_error)
    if not has_gui_display():
        _pyautogui_error = "Desktop input automation is not available in headless Linux environment."
        raise RuntimeError(_pyautogui_error)
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0.05
        _pyautogui = pyautogui
        return _pyautogui
    except Exception as e:
        _pyautogui_error = f"Desktop input automation failed to initialize: {e}."
        raise RuntimeError(_pyautogui_error)


class InputController:
    """Dispatches physical mouse and keyboard events."""

    _instance: Optional[InputController] = None

    @classmethod
    def get_instance(cls) -> InputController:
        if cls._instance is None:
            cls._instance = InputController()
        return cls._instance

    def _normalize_key(self, key_name: str) -> str:
        if _IS_WINDOWS:
            return map_key_win(key_name)
        elif _IS_LINUX:
            return map_key_linux(key_name)
        return key_name.strip().lower()

    def get_cursor_position(self) -> Tuple[int, int]:
        try:
            ag = get_pyautogui()
            pos = ag.position()
            return int(pos.x), int(pos.y)
        except Exception:
            return 0, 0

    def mouse_move(self, x: int | float, y: int | float) -> Tuple[int, int]:
        ag = get_pyautogui()
        ag.moveTo(int(x), int(y))
        return int(x), int(y)

    def mouse_down(self, button: str = "left") -> None:
        get_pyautogui().mouseDown(button=button)

    def mouse_up(self, button: str = "left") -> None:
        get_pyautogui().mouseUp(button=button)

    def click(self, x: Optional[int | float] = None, y: Optional[int | float] = None, button: str = "left") -> Tuple[int, int]:
        ag = get_pyautogui()
        if x is not None and y is not None:
            ag.click(x=int(x), y=int(y), button=button)
            return int(x), int(y)
        ag.click(button=button)
        return self.get_cursor_position()

    def double_click(self, x: Optional[int | float] = None, y: Optional[int | float] = None) -> Tuple[int, int]:
        ag = get_pyautogui()
        if x is not None and y is not None:
            ag.doubleClick(x=int(x), y=int(y))
            return int(x), int(y)
        ag.doubleClick()
        return self.get_cursor_position()

    def triple_click(self, x: Optional[int | float] = None, y: Optional[int | float] = None) -> Tuple[int, int]:
        ag = get_pyautogui()
        if x is not None and y is not None:
            ag.tripleClick(x=int(x), y=int(y))
            return int(x), int(y)
        ag.tripleClick()
        return self.get_cursor_position()

    def drag_to(self, x: int | float, y: int | float) -> Tuple[int, int]:
        ag = get_pyautogui()
        ag.dragTo(int(x), int(y), button="left", duration=0.2)
        return int(x), int(y)

    def scroll(self, clicks: int = -3) -> None:
        get_pyautogui().scroll(clicks)

    def type_text(self, text: str) -> None:
        get_pyautogui().write(text, interval=0.01)

    def key_press(self, key: str) -> None:
        get_pyautogui().press(self._normalize_key(key))

    def key_down(self, key: str) -> None:
        get_pyautogui().keyDown(self._normalize_key(key))

    def key_up(self, key: str) -> None:
        get_pyautogui().keyUp(self._normalize_key(key))

    def hotkey(self, *keys: str) -> None:
        norm = [self._normalize_key(k) for k in keys]
        get_pyautogui().hotkey(*norm)


__all__ = [
    "has_gui_display",
    "get_linux_display_server",
    "map_key_win",
    "map_key_linux",
    "get_pyautogui",
    "InputController",
]
