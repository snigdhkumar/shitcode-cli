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
from tools.desktop.window.manager import focus_desktop_window, set_desktop_window_state

logger = logging.getLogger("shitcode.tools.desktop.vision.executor")


async def execute_atomic_action(
    action: str,
    coordinate: Optional[List[int | float]] = None,
    text: Optional[str] = None,
    **kwargs: Any,
) -> Any:
    """Execute single Anthropic Computer Use action."""
    params = parse_action_params(action, coordinate, text, **kwargs)
    act, coord, txt = params["action"], params["coordinate"], params["text"]
    screen_mgr, ctrl = ScreenManager.get_instance(), InputController.get_instance()

    if act == "screenshot":
        return await asyncio.to_thread(screen_mgr.capture_screenshot)
    if act == "mouse_move" and coord:
        return {"success": True, "ok": True, "position": ctrl.mouse_move(coord[0], coord[1])}
    if act in ("left_click", "right_click", "middle_click"):
        btn = act.replace("_click", "")
        return {"success": True, "ok": True, "position": ctrl.click(coord[0] if coord else None, coord[1] if coord else None, button=btn)}
    if act == "double_click":
        return {"success": True, "ok": True, "position": ctrl.double_click(coord[0] if coord else None, coord[1] if coord else None)}
    if act == "triple_click":
        return {"success": True, "ok": True, "position": ctrl.triple_click(coord[0] if coord else None, coord[1] if coord else None)}
    if act == "mouse_down":
        pos = ctrl.mouse_down(coord[0] if coord else None, coord[1] if coord else None, button=kwargs.get("button", "left"))
        return {"success": True, "ok": True, "position": pos}
    if act == "mouse_up":
        pos = ctrl.mouse_up(coord[0] if coord else None, coord[1] if coord else None, button=kwargs.get("button", "left"))
        return {"success": True, "ok": True, "position": pos}
    if act == "left_click_drag" and coord:
        from_c = kwargs.get("from_coordinate") or kwargs.get("start_coordinate")
        pos = ctrl.drag_to(coord[0], coord[1], from_x=from_c[0] if from_c else None, from_y=from_c[1] if from_c else None)
        return {"success": True, "ok": True, "position": pos}
    if act == "type":
        ctrl.type_text(txt)
        return {"success": True, "ok": True, "typed": txt}
    if act in ("key", "hotkey", "press_hotkey"):
        ctrl.hotkey(*[k.strip() for k in txt.split("+")]) if "+" in txt else ctrl.key_press(txt)
        return {"success": True, "ok": True, "key": txt}
    if act == "press_enter":
        ctrl.key_press("enter")
        return {"success": True, "ok": True}
    if act == "scroll":
        raw_scroll = (
            kwargs.get("scroll")
            or kwargs.get("clicks")
            or kwargs.get("amount")
            or kwargs.get("delta_y")
            or kwargs.get("delta")
        )
        clicks = int(txt) if txt else int(raw_scroll if raw_scroll is not None else -3)
        ctrl.scroll(clicks)
        return {"success": True, "ok": True, "scroll": clicks}
    if act == "wait":
        ms = float(txt) if txt else float(kwargs.get("ms") or kwargs.get("duration") or 500.0)
        await asyncio.sleep(ms / 1000.0)
        return {"success": True, "ok": True, "waited_ms": ms}
    if act == "cursor_position":
        return {"success": True, "ok": True, "position": ctrl.get_cursor_position()}
    if act == "clipboard_write":
        return copy_to_clipboard(txt)
    if act == "clipboard_read":
        return read_from_clipboard()
    if act == "clipboard_paste":
        if txt:
            copy_to_clipboard(txt)
            time.sleep(0.04)
        ctrl.hotkey("ctrl", "v")
        return {"success": True, "ok": True, "pasted": txt}
    if act == "window_focus":
        res = focus_desktop_window(title=txt)
        return {"success": res.get("ok", True), "ok": res.get("ok", True), "focused": txt}
    if act == "window_state":
        res = set_desktop_window_state(state=txt or "restore", title=kwargs.get("title") or "")
        return {"success": res.get("ok", True), "ok": res.get("ok", True), "window_state": txt}

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

    screen_mgr = ScreenManager.get_instance()
    shot = await asyncio.to_thread(screen_mgr.capture_screenshot)
    out: Dict[str, Any] = {
        "success": True,
        "ok": True,
        "completed_steps": len(results),
        "actions_executed": len(results),
        "step_reports": results,
        "results": results,
        "screenshot": shot,
    }
    if isinstance(shot, dict) and "content" in shot:
        out["content"] = shot["content"]
        if "display" in shot:
            out["display"] = shot["display"]
    return out
