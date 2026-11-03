"""Anthropic Computer Use Protocol Action Parser.
Validates and normalizes action dictionaries and parameters.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


VALID_ACTIONS = {
    "screenshot", "mouse_move", "left_click", "right_click", "double_click",
    "triple_click", "middle_click", "mouse_down", "mouse_up", "left_click_drag",
    "type", "key", "press_enter", "press_hotkey", "hotkey", "scroll", "wait", "cursor_position",
    "clipboard_write", "clipboard_read"
}


def parse_action_params(
    action: str,
    coordinate: Optional[List[int | float]] = None,
    text: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Normalize input action and parameters into standard execution dictionary."""
    act = (action or "").strip().lower()
    if act not in VALID_ACTIONS:
        raise ValueError(f"Unknown action '{action}'. Valid actions: {', '.join(sorted(VALID_ACTIONS))}")

    coord: Optional[Tuple[int, int]] = None
    if coordinate and len(coordinate) >= 2:
        coord = (int(coordinate[0]), int(coordinate[1]))

    return {
        "action": act,
        "coordinate": coord,
        "text": text or kwargs.get("value") or "",
        "options": kwargs,
    }
