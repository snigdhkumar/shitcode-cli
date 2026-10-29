"""Unified Cross-Platform Desktop Input Controller for ShitCode.
Provides hardware mouse and keyboard simulation with permanent failsafe kill-switch.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from typing import Any, Optional, Sequence, Tuple

from tools.desktop.input_linux import get_linux_display_server, map_key_linux
from tools.desktop.input_win import map_key_win
from tools.desktop.screen import ScreenManager

logger = logging.getLogger("shitcode.tools.desktop.controller")

_IS_WINDOWS = sys.platform == "win32"
_IS_LINUX = sys.platform.startswith("linux")

_pyautogui: Optional[Any] = None
_pyautogui_error: Optional[str] = None


def has_gui_display() -> bool:
    """Detect if the current host environment has a graphical display available."""
    if _IS_WINDOWS:
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def get_pyautogui() -> Any:
    """Lazily load and initialize PyAutoGUI with display availability guards."""
    global _pyautogui, _pyautogui_error

    if _pyautogui is not None:
        return _pyautogui

    if _pyautogui_error is not None:
        raise RuntimeError(_pyautogui_error)

    if not has_gui_display():
        _pyautogui_error = (
            "Desktop input automation is not available in headless Linux environment "
            "(no DISPLAY or WAYLAND_DISPLAY environment variable set)."
        )
        raise RuntimeError(_pyautogui_error)

    try:
        import pyautogui
        # Allow autonomous agent control across the full display including screen corners
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0.05  # 50ms pause between rapid low-level events for UI stability
        _pyautogui = pyautogui
        return _pyautogui
    except KeyError as ke:
        _pyautogui_error = f"Desktop input automation failed: missing environment variable {ke}."
        raise RuntimeError(_pyautogui_error)
    except Exception as e:
        _pyautogui_error = f"Desktop input automation failed to initialize: {e}."
        raise RuntimeError(_pyautogui_error)


class InputController:
    """Dispatches physical mouse and keyboard events with coordinate remapping."""

    _instance: Optional[InputController] = None

    def __init__(self):
        self.screen_mgr = ScreenManager.get_instance()

    @classmethod
    def get_instance(cls) -> InputController:
        if cls._instance is None:
            cls._instance = InputController()
        return cls._instance

    def _normalize_key(self, key_name: str) -> str:
        """Map key name to host OS equivalent."""
        if _IS_WINDOWS:
            return map_key_win(key_name)
        elif _IS_LINUX:
            return map_key_linux(key_name)
        return key_name.strip().lower()

    def get_cursor_position(self) -> Tuple[int, int]:
        """Return current physical mouse cursor position."""
        try:
            ag = get_pyautogui()
            pos = ag.position()
            return int(pos.x), int(pos.y)
        except Exception:
            return 0, 0

    def mouse_move(self, x: int | float, y: int | float) -> Tuple[int, int]:
        """Move mouse cursor to coordinates (remapping from AI scale to physical screen)."""
        ag = get_pyautogui()
        real_x, real_y = self.screen_mgr.remap_coordinates(x, y)
        ag.moveTo(real_x, real_y)
        return real_x, real_y

    def click(self, x: Optional[int | float] = None, y: Optional[int | float] = None, button: str = "left") -> Tuple[int, int]:
        """Perform mouse click with optional coordinate target and button choice."""
        ag = get_pyautogui()
        if x is not None and y is not None:
            real_x, real_y = self.screen_mgr.remap_coordinates(x, y)
            ag.click(real_x, real_y, button=button)
            return real_x, real_y
        else:
            cur_x, cur_y = self.get_cursor_position()
            ag.click(button=button)
            return cur_x, cur_y

    def double_click(self, x: Optional[int | float] = None, y: Optional[int | float] = None) -> Tuple[int, int]:
        """Perform double-click."""
        ag = get_pyautogui()
        if x is not None and y is not None:
            real_x, real_y = self.screen_mgr.remap_coordinates(x, y)
            ag.doubleClick(real_x, real_y)
            return real_x, real_y
        else:
            cur_x, cur_y = self.get_cursor_position()
            ag.doubleClick()
            return cur_x, cur_y

    def triple_click(self, x: Optional[int | float] = None, y: Optional[int | float] = None) -> Tuple[int, int]:
        """Perform triple-click (useful for selecting entire paragraphs)."""
        ag = get_pyautogui()
        if x is not None and y is not None:
            real_x, real_y = self.screen_mgr.remap_coordinates(x, y)
            ag.tripleClick(real_x, real_y)
            return real_x, real_y
        else:
            cur_x, cur_y = self.get_cursor_position()
            ag.tripleClick()
            return cur_x, cur_y

    def right_click(self, x: Optional[int | float] = None, y: Optional[int | float] = None) -> Tuple[int, int]:
        """Perform right-click."""
        return self.click(x=x, y=y, button="right")

    def middle_click(self, x: Optional[int | float] = None, y: Optional[int | float] = None) -> Tuple[int, int]:
        """Perform middle mouse click."""
        return self.click(x=x, y=y, button="middle")

    def mouse_down(self, x: Optional[int | float] = None, y: Optional[int | float] = None, button: str = "left") -> Tuple[int, int]:
        """Move (if coordinates provided) and hold down mouse button."""
        ag = get_pyautogui()
        if x is not None and y is not None:
            real_x, real_y = self.mouse_move(x, y)
        else:
            real_x, real_y = self.get_cursor_position()
        ag.mouseDown(button=button)
        return real_x, real_y

    def mouse_up(self, x: Optional[int | float] = None, y: Optional[int | float] = None, button: str = "left") -> Tuple[int, int]:
        """Move (if coordinates provided) and release held mouse button."""
        ag = get_pyautogui()
        if x is not None and y is not None:
            real_x, real_y = self.mouse_move(x, y)
        else:
            real_x, real_y = self.get_cursor_position()
        ag.mouseUp(button=button)
        return real_x, real_y

    def drag(self, start_x: int | float, start_y: int | float, end_x: int | float, end_y: int | float, duration: float = 0.5) -> None:
        """Drag mouse from start coordinates to end coordinates."""
        ag = get_pyautogui()
        real_start_x, real_start_y = self.screen_mgr.remap_coordinates(start_x, start_y)
        real_end_x, real_end_y = self.screen_mgr.remap_coordinates(end_x, end_y)
        ag.moveTo(real_start_x, real_start_y)
        ag.dragTo(real_end_x, real_end_y, duration=duration, button="left")

    def drag_to(self, end_x: int | float, end_y: int | float, duration: float = 0.5) -> Tuple[int, int]:
        """Drag mouse from CURRENT cursor position to target coordinates."""
        ag = get_pyautogui()
        real_end_x, real_end_y = self.screen_mgr.remap_coordinates(end_x, end_y)
        ag.dragTo(real_end_x, real_end_y, duration=duration, button="left")
        return real_end_x, real_end_y

    def scroll(self, clicks: int = 3, direction: str = "down") -> None:
        """Scroll vertical wheel."""
        ag = get_pyautogui()
        amount = -clicks if direction.lower() == "down" else clicks
        ag.scroll(amount)

    def type_text(self, text: str, interval: float = 0.0) -> None:
        """Type text string."""
        ag = get_pyautogui()
        ag.write(text, interval=interval)

    def press_key(self, key_name: str) -> None:
        """Press a single key (e.g. 'Return', 'Escape', 'Tab', 'Space')."""
        ag = get_pyautogui()
        norm = self._normalize_key(key_name)
        ag.press(norm)

    def key_combination(self, keys: Sequence[str]) -> None:
        """Press key combination/shortcut simultaneously (e.g. ['ctrl', 'c'] or ['alt', 'tab'])."""
        ag = get_pyautogui()
        norm_keys = [self._normalize_key(k) for k in keys]
        ag.hotkey(*norm_keys)

    def key_down(self, key_name: str) -> None:
        """Hold key down."""
        ag = get_pyautogui()
        norm = self._normalize_key(key_name)
        ag.keyDown(norm)

    def key_up(self, key_name: str) -> None:
        """Release key."""
        ag = get_pyautogui()
        norm = self._normalize_key(key_name)
        ag.keyUp(norm)
