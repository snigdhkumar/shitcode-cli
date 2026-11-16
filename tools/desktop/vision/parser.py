"""Anthropic Computer Use Protocol Action Parser.
Validates and normalizes action dictionaries and parameters.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


VALID_ACTIONS = {
    "screenshot", "mouse_move", "left_click", "right_click", "double_click",
    "triple_click", "middle_click", "mouse_down", "mouse_up", "left_click_drag",
    "type", "key", "press_enter", "press_hotkey", "hotkey", "scroll", "wait", "cursor_position",
    "clipboard_write", "clipboard_read", "clipboard_paste", "window_focus", "window_state"
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

    raw_coord = coordinate or kwargs.get("coord") or kwargs.get("coords") or kwargs.get("point") or kwargs.get("position")
    coord: Optional[Tuple[int, int]] = None
    if raw_coord and len(raw_coord) >= 2:
        coord = (int(raw_coord[0]), int(raw_coord[1]))

    # Resolve text / value aliases per action
    val = text or kwargs.get("value") or ""
    if act == "window_focus" and not val:
        val = kwargs.get("title") or kwargs.get("window_id") or kwargs.get("app_name") or kwargs.get("name") or ""
    elif act == "window_state" and not val:
        val = kwargs.get("state") or kwargs.get("mode") or "restore"
    elif act == "wait" and not val:
        raw_ms = kwargs.get("ms") or kwargs.get("duration") or kwargs.get("time")
        if raw_ms is not None:
            val = str(raw_ms)
        elif kwargs.get("seconds") is not None:
            val = str(float(kwargs["seconds"]) * 1000.0)
    elif act == "scroll" and not val:
        raw_clicks = (
            kwargs.get("scroll")
            or kwargs.get("clicks")
            or kwargs.get("amount")
            or kwargs.get("delta_y")
            or kwargs.get("delta")
        )
        if raw_clicks is not None:
            val = str(raw_clicks)
    elif act in ("clipboard_write", "clipboard_paste", "type") and not val:
        val = kwargs.get("content") or kwargs.get("text") or ""

    return {
        "action": act,
        "coordinate": coord,
        "text": str(val) if val is not None else "",
        "options": kwargs,
    }
