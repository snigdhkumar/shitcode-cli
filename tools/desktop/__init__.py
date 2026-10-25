"""Desktop & Computer Control Automation Package for ShitCode.
Exports Anthropic-standard computer control, compound batch actions, and high-speed desktop visual inspection tools.
"""

from __future__ import annotations

from tools.desktop.actions import computer, computer_actions, desktop_inspect
from tools.desktop.controller import InputController
from tools.desktop.screen import ScreenManager

__all__ = [
    "computer",
    "computer_actions",
    "desktop_inspect",
    "InputController",
    "ScreenManager",
]
