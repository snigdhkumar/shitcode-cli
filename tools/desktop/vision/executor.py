"""Vision & Coordinate Computer Action Executor.
Dispatches Anthropic-compatible coordinate actions and batch commands.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from tools.desktop.input import InputController
from tools.desktop.system.clipboard import copy_to_clipboard, read_from_clipboard
from tools.desktop.vision.parser import parse_action_params
from tools.desktop.vision.screen import ScreenManager

logger = logging.getLogger("shitcode.tools.desktop.vision.executor")


async def execute_atomic_action(
    action: str,
    coordinate: Optional[List[int | float]] = None,
    text: Optional[str] = None,
    **kwargs: Any,
) -> Any:
    """Execute single Anthropic Computer Use action."""
    params = parse_action_params(action, coordinate, text, **kwargs)
    act = params["action"]
    coord = params["coordinate"]
    txt = params["text"]

    screen_mgr = ScreenManager.get_instance()
    ctrl = InputController.get_instance()

    if act == "screenshot":
        return await asyncio.to_thread(screen_mgr.capture_screenshot)

    if act == "mouse_move" and coord:
        pos = ctrl.mouse_move(coord[0], coord[1])
        return {"success": True, "ok": True, "position": pos}

    if act == "left_click":
        pos = ctrl.click(coord[0] if coord else None, coord[1] if coord else None, button="left")
        return {"success": True, "ok": True, "position": pos}

    if act == "right_click":
        pos = ctrl.click(coord[0] if coord else None, coord[1] if coord else None, button="right")
        return {"success": True, "ok": True, "position": pos}

    if act == "middle_click":
        pos = ctrl.click(coord[0] if coord else None, coord[1] if coord else None, button="middle")
        return {"success": True, "ok": True, "position": pos}

    if act == "double_click":
        pos = ctrl.double_click(coord[0] if coord else None, coord[1] if coord else None)
        return {"success": True, "ok": True, "position": pos}

    if act == "triple_click":
        pos = ctrl.triple_click(coord[0] if coord else None, coord[1] if coord else None)
        return {"success": True, "ok": True, "position": pos}

    if act == "mouse_down":
        ctrl.mouse_down(button=kwargs.get("button", "left"))
        return {"success": True, "ok": True}

    if act == "mouse_up":
        ctrl.mouse_up(button=kwargs.get("button", "left"))
        return {"success": True, "ok": True}

    if act == "left_click_drag" and coord:
        pos = ctrl.drag_to(coord[0], coord[1])
        return {"success": True, "ok": True, "position": pos}

    if act == "type":
        ctrl.type_text(txt)
        return {"success": True, "ok": True, "typed": txt}

    if act in ("key", "hotkey", "press_hotkey"):
        if "+" in txt:
            keys = [k.strip() for k in txt.split("+")]
            ctrl.hotkey(*keys)
        else:
            ctrl.key_press(txt)
        return {"success": True, "ok": True, "key": txt}

    if act == "press_enter":
        ctrl.key_press("enter")
        return {"success": True, "ok": True}

    if act == "scroll":
        clicks = int(txt) if txt else -3
        ctrl.scroll(clicks)
        return {"success": True, "ok": True, "scroll": clicks}

    if act == "wait":
        ms = float(txt) if txt else 500.0
        await asyncio.sleep(ms / 1000.0)
        return {"success": True, "ok": True, "waited_ms": ms}

    if act == "cursor_position":
        pos = ctrl.get_cursor_position()
        return {"success": True, "ok": True, "position": pos}

    if act == "clipboard_write":
        return copy_to_clipboard(txt)

    if act == "clipboard_read":
        return read_from_clipboard()

    return {"success": False, "ok": False, "error": f"Unhandled action '{act}'."}


async def execute_batch_actions(actions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Execute compound sequence of atomic computer actions."""
    results = []
    for item in actions:
        res = await execute_atomic_action(
            action=item.get("action", ""),
            coordinate=item.get("coordinate"),
            text=item.get("text"),
            **{k: v for k, v in item.items() if k not in ("action", "coordinate", "text")}
        )
        results.append(res)
        await asyncio.sleep(0.05)

    # Grab final screenshot
    screen_mgr = ScreenManager.get_instance()
    shot = await asyncio.to_thread(screen_mgr.capture_screenshot)
    return {
        "success": True,
        "ok": True,
        "completed_steps": len(results),
        "actions_executed": len(results),
        "step_reports": results,
        "results": results,
        "screenshot": shot,
    }
