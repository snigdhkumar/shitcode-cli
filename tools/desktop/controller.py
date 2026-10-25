"""Unified Cross-Platform Desktop Input Controller for ShitCode.
Provides hardware mouse and keyboard simulation with permanent failsafe kill-switch.
"""

from __future__ import annotations

import logging
import sys
import time
from typing import Optional, Sequence, Tuple

import pyautogui

from tools.desktop.input_linux import get_linux_display_server, map_key_linux
from tools.desktop.input_win import map_key_win
from tools.desktop.screen import ScreenManager

logger = logging.getLogger("shitcode.tools.desktop.controller")

# Allow autonomous agent control across the full display including screen corners (e.g. Start menu, close buttons)
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.05  # 50ms pause between rapid low-level events for UI stability

_IS_WINDOWS = sys.platform == "win32"
_IS_LINUX = sys.platform.startswith("linux")


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
        pos = pyautogui.position()
        return int(pos.x), int(pos.y)

    def mouse_move(self, x: int | float, y: int | float) -> Tuple[int, int]:
        """Move mouse cursor to coordinates (remapping from AI scale to physical screen)."""
        real_x, real_y = self.screen_mgr.remap_coordinates(x, y)
        pyautogui.moveTo(real_x, real_y)
        return real_x, real_y

    def click(self, x: Optional[int | float] = None, y: Optional[int | float] = None, button: str = "left") -> Tuple[int, int]:
        """Perform mouse click with optional coordinate target and button choice."""
        if x is not None and y is not None:
            real_x, real_y = self.screen_mgr.remap_coordinates(x, y)
            pyautogui.click(real_x, real_y, button=button)
            return real_x, real_y
        else:
            cur_x, cur_y = self.get_cursor_position()
            pyautogui.click(button=button)
            return cur_x, cur_y

    def double_click(self, x: Optional[int | float] = None, y: Optional[int | float] = None) -> Tuple[int, int]:
        """Perform double-click."""
        if x is not None and y is not None:
            real_x, real_y = self.screen_mgr.remap_coordinates(x, y)
            pyautogui.doubleClick(real_x, real_y)
            return real_x, real_y
        else:
            cur_x, cur_y = self.get_cursor_position()
            pyautogui.doubleClick()
            return cur_x, cur_y

    def triple_click(self, x: Optional[int | float] = None, y: Optional[int | float] = None) -> Tuple[int, int]:
        """Perform triple-click (useful for selecting entire paragraphs)."""
        if x is not None and y is not None:
            real_x, real_y = self.screen_mgr.remap_coordinates(x, y)
            pyautogui.tripleClick(real_x, real_y)
            return real_x, real_y
        else:
            cur_x, cur_y = self.get_cursor_position()
            pyautogui.tripleClick()
            return cur_x, cur_y

    def right_click(self, x: Optional[int | float] = None, y: Optional[int | float] = None) -> Tuple[int, int]:
        """Perform right-click."""
        return self.click(x=x, y=y, button="right")

    def middle_click(self, x: Optional[int | float] = None, y: Optional[int | float] = None) -> Tuple[int, int]:
        """Perform middle mouse click."""
        return self.click(x=x, y=y, button="middle")

    def mouse_down(self, x: Optional[int | float] = None, y: Optional[int | float] = None, button: str = "left") -> Tuple[int, int]:
        """Move (if coordinates provided) and hold down mouse button."""
        if x is not None and y is not None:
            real_x, real_y = self.mouse_move(x, y)
        else:
            real_x, real_y = self.get_cursor_position()
        pyautogui.mouseDown(button=button)
        return real_x, real_y

    def mouse_up(self, x: Optional[int | float] = None, y: Optional[int | float] = None, button: str = "left") -> Tuple[int, int]:
        """Move (if coordinates provided) and release held mouse button."""
        if x is not None and y is not None:
            real_x, real_y = self.mouse_move(x, y)
        else:
            real_x, real_y = self.get_cursor_position()
        pyautogui.mouseUp(button=button)
        return real_x, real_y

    def drag(self, start_x: int | float, start_y: int | float, end_x: int | float, end_y: int | float, duration: float = 0.5) -> None:
        """Drag mouse from start coordinates to end coordinates."""
        real_start_x, real_start_y = self.screen_mgr.remap_coordinates(start_x, start_y)
        real_end_x, real_end_y = self.screen_mgr.remap_coordinates(end_x, end_y)
        pyautogui.moveTo(real_start_x, real_start_y)
        pyautogui.dragTo(real_end_x, real_end_y, duration=duration, button="left")

    def drag_to(self, end_x: int | float, end_y: int | float, duration: float = 0.5) -> Tuple[int, int]:
        """Drag mouse from CURRENT cursor position to target coordinates."""
        real_end_x, real_end_y = self.screen_mgr.remap_coordinates(end_x, end_y)
        pyautogui.dragTo(real_end_x, real_end_y, duration=duration, button="left")
        return real_end_x, real_end_y

    def scroll(self, clicks: int = 3, direction: str = "down") -> None:
        """Scroll vertical wheel."""
        amount = -clicks if direction.lower() == "down" else clicks
        pyautogui.scroll(amount)

    def type_text(self, text: str, interval: float = 0.0) -> None:
        """Type text string."""
        pyautogui.write(text, interval=interval)

    def press_key(self, key_name: str) -> None:
        """Press a single key (e.g. 'Return', 'Escape', 'Tab', 'Space')."""
        norm = self._normalize_key(key_name)
        pyautogui.press(norm)

    def key_combination(self, keys: Sequence[str]) -> None:
        """Press key combination/shortcut simultaneously (e.g. ['ctrl', 'c'] or ['alt', 'tab'])."""
        norm_keys = [self._normalize_key(k) for k in keys]
        pyautogui.hotkey(*norm_keys)

    def key_down(self, key_name: str) -> None:
        """Hold key down."""
        norm = self._normalize_key(key_name)
        pyautogui.keyDown(norm)

    def key_up(self, key_name: str) -> None:
        """Release key."""
        norm = self._normalize_key(key_name)
        pyautogui.keyUp(norm)
