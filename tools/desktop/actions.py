"""Anthropic-Standard Computer Use Protocol & Compound Batch Actions Engine for ShitCode.
Allows external AI models (ChatGPT, Claude) to interact with the local host desktop.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

from core.reporter import with_error_reporting
from tools.desktop.clipboard import copy_to_clipboard, paste_text_via_clipboard, read_from_clipboard
from tools.desktop.controller import InputController
from tools.desktop.screen import ScreenManager
from tools.desktop.system import get_system_metrics
from tools.desktop.windows import focus_desktop_window, list_desktop_windows, set_desktop_window_state

logger = logging.getLogger("shitcode.tools.desktop.actions")


def _safe_print(text: str = ""):
    """Print text safely handling Windows non-UTF8 charmap encodings."""
    try:
        print(text)
    except UnicodeEncodeError:
        try:
            safe_text = (
                text.replace("╭", "+")
                .replace("╮", "+")
                .replace("╰", "+")
                .replace("╯", "+")
                .replace("─", "-")
                .replace("│", "|")
                .replace("[✓]", "[ok]")
                .replace("✓", "ok")
                .replace("[✗]", "[err]")
                .replace("✗", "err")
            )
            print(safe_text)
        except Exception:
            pass


def _attach_screenshot_note(shot: Any, prefix: str) -> Any:
    """Safely attach context notes to a screenshot result without failing if screenshot errored."""
    if isinstance(shot, dict) and shot.get("success") and shot.get("content"):
        try:
            shot["content"][0]["text"] = f"{prefix} Updated desktop state below:"
        except Exception:
            pass
    return shot


@with_error_reporting("desktop_inspect")
async def desktop_inspect(max_dimension: int = 1280, quality: int = 75) -> Any:
    """Visually inspect the current state of the local computer desktop.
    Returns downsampled native MCP image content blocks for AI vision inspection.
    """
    screen_mgr = ScreenManager.get_instance()
    res = await asyncio.to_thread(screen_mgr.capture_screenshot, max_dimension=max_dimension, quality=quality)
    return res


@with_error_reporting("computer")
async def computer(
    action: str,
    coordinate: Optional[List[int | float]] = None,
    text: Optional[str] = None,
) -> Any:
    """Execute an atomic desktop action matching the Anthropic Computer Use specification.

    Supported actions:
    - screenshot: Takes a screenshot of the desktop.
    - mouse_move: Moves mouse cursor to coordinate [x, y].
    - left_click: Clicks at coordinate [x, y] (or current position).
    - right_click: Right-clicks at coordinate [x, y].
    - double_click: Double-clicks at coordinate [x, y].
    - triple_click: Triple-clicks at coordinate [x, y].
    - middle_click: Middle-clicks at coordinate [x, y].
    - mouse_down / mouse_up: Holds or releases mouse button.
    - left_click_drag: Drags mouse from start to end coordinates.
    - type: Types text string specified in 'text'.
    - key / hotkey: Presses key or combination specified in 'text' (e.g. 'Return', 'Escape', 'ctrl+c').
    - press_enter: Presses Return/Enter.
    - scroll: Scrolls up or down by ticks specified in 'text'.
    - wait: Waits for milliseconds specified in 'text'.
    - cursor_position: Returns current mouse cursor position.
    """
    ctrl = InputController.get_instance()
    screen_mgr = ScreenManager.get_instance()
    act = action.strip().lower()

    x: Optional[int | float] = None
    y: Optional[int | float] = None
    if coordinate and len(coordinate) >= 2:
        x, y = coordinate[0], coordinate[1]

    if act == "screenshot":
        return await asyncio.to_thread(screen_mgr.capture_screenshot)

    elif act == "mouse_move":
        if x is None or y is None:
            return "Error: 'coordinate' [x, y] is required for action 'mouse_move'."
        real_x, real_y = ctrl.mouse_move(x, y)
        return f"Moved mouse to ({real_x}, {real_y}) [scaled from AI ({x}, {y})]."

    elif act in ("left_click", "click"):
        real_x, real_y = ctrl.click(x=x, y=y, button="left")
        shot = await asyncio.to_thread(screen_mgr.capture_screenshot)
        return _attach_screenshot_note(shot, f"Left-clicked at ({real_x}, {real_y}).")

    elif act == "right_click":
        real_x, real_y = ctrl.right_click(x=x, y=y)
        shot = await asyncio.to_thread(screen_mgr.capture_screenshot)
        return _attach_screenshot_note(shot, f"Right-clicked at ({real_x}, {real_y}).")

    elif act == "double_click":
        real_x, real_y = ctrl.double_click(x=x, y=y)
        shot = await asyncio.to_thread(screen_mgr.capture_screenshot)
        return _attach_screenshot_note(shot, f"Double-clicked at ({real_x}, {real_y}).")

    elif act == "triple_click":
        real_x, real_y = ctrl.triple_click(x=x, y=y)
        shot = await asyncio.to_thread(screen_mgr.capture_screenshot)
        return _attach_screenshot_note(shot, f"Triple-clicked at ({real_x}, {real_y}).")

    elif act == "middle_click":
        real_x, real_y = ctrl.middle_click(x=x, y=y)
        return f"Middle-clicked at ({real_x}, {real_y})."

    elif act == "mouse_down":
        real_x, real_y = ctrl.mouse_down(x=x, y=y)
        return f"Mouse button held down at ({real_x}, {real_y})."

    elif act == "mouse_up":
        real_x, real_y = ctrl.mouse_up(x=x, y=y)
        return f"Mouse button released at ({real_x}, {real_y})."

    elif act == "type":
        if not text:
            return "Error: 'text' parameter is required for action 'type'."
        ctrl.type_text(text)
        shot = await asyncio.to_thread(screen_mgr.capture_screenshot)
        return _attach_screenshot_note(shot, f"Typed \"{text}\".")

    elif act in ("key", "hotkey"):
        if not text:
            return "Error: 'text' parameter is required for action 'key' / 'hotkey'."
        keys = text.replace("+", " ").split()
        if len(keys) > 1:
            ctrl.key_combination(keys)
        else:
            ctrl.press_key(keys[0])
        shot = await asyncio.to_thread(screen_mgr.capture_screenshot)
        return _attach_screenshot_note(shot, f"Pressed key '{text}'.")

    elif act == "press_enter":
        ctrl.press_key("Return")
        shot = await asyncio.to_thread(screen_mgr.capture_screenshot)
        return _attach_screenshot_note(shot, "Pressed Enter.")

    elif act in ("left_click_drag", "drag"):
        if coordinate and len(coordinate) >= 4:
            x1, y1, x2, y2 = coordinate[0], coordinate[1], coordinate[2], coordinate[3]
            ctrl.drag(x1, y1, x2, y2)
        elif x is not None and y is not None:
            ctrl.drag_to(x, y)
        else:
            return "Error: 'coordinate' with target [x, y] required for drag action."
        shot = await asyncio.to_thread(screen_mgr.capture_screenshot)
        return _attach_screenshot_note(shot, "Completed mouse drag.")

    elif act == "scroll":
        clicks = 3
        direction = "down"
        if text:
            try:
                val = int(text)
                clicks = abs(val)
                direction = "up" if val > 0 else "down"
            except ValueError:
                direction = "up" if "up" in text.lower() else "down"
        ctrl.scroll(clicks=clicks, direction=direction)
        shot = await asyncio.to_thread(screen_mgr.capture_screenshot)
        return _attach_screenshot_note(shot, f"Scrolled {direction} ({clicks} clicks).")

    elif act == "wait":
        ms = 500
        if text:
            try:
                ms = max(50, int(text))
            except ValueError:
                pass
        await asyncio.sleep(ms / 1000.0)
        return f"Waited {ms}ms."

    elif act == "cursor_position":
        cx, cy = ctrl.get_cursor_position()
        return f"Current cursor position: ({cx}, {cy})."

    elif act in ("window_focus", "focus_window"):
        if not text:
            return "Error: 'text' parameter specifying window title or name is required for 'window_focus'."
        res_focus = await asyncio.to_thread(focus_desktop_window, title=text)
        shot = await asyncio.to_thread(screen_mgr.capture_screenshot)
        return _attach_screenshot_note(shot, res_focus.get("message", res_focus.get("error", "Window focus executed.")))

    elif act in ("clipboard_paste", "paste"):
        if not text:
            return "Error: 'text' parameter is required for action 'clipboard_paste'."
        res_paste = await asyncio.to_thread(paste_text_via_clipboard, text=text)
        shot = await asyncio.to_thread(screen_mgr.capture_screenshot)
        return _attach_screenshot_note(shot, res_paste.get("message", "Pasted text via clipboard."))

    elif act in ("clipboard_write", "copy"):
        if not text:
            return "Error: 'text' parameter is required for action 'clipboard_write'."
        res_copy = await asyncio.to_thread(copy_to_clipboard, text=text)
        return res_copy.get("message", "Copied to clipboard.")

    elif act == "clipboard_read":
        res_read = await asyncio.to_thread(read_from_clipboard)
        return res_read.get("content", "")

    return f"Unknown action: '{action}'. Available: screenshot, mouse_move, left_click, right_click, middle_click, double_click, triple_click, mouse_down, mouse_up, left_click_drag, type, key, hotkey, press_enter, scroll, wait, cursor_position, window_focus, clipboard_paste, clipboard_write, clipboard_read."


@with_error_reporting("computer_actions")
async def computer_actions(actions: list) -> Any:
    """Execute a batch of sequential desktop actions in a single turn with live CLI feedback.
    
    Supported action types in the list:
    - {"action": "click", "coordinate": [x, y]}
    - {"action": "double_click", "coordinate": [x, y]}
    - {"action": "right_click", "coordinate": [x, y]}
    - {"action": "type", "text": "Hello"}
    - {"action": "key", "key": "Return"} (or text: "ctrl+s")
    - {"action": "drag", "start": [x1, y1], "end": [x2, y2]}
    - {"action": "scroll", "clicks": 3, "direction": "down"}
    - {"action": "wait", "ms": 500}
    - {"action": "screenshot"}
    """
    if not actions or not isinstance(actions, list):
        return {"success": False, "error": "Parameter 'actions' must be a non-empty list of action objects."}

    ctrl = InputController.get_instance()
    screen_mgr = ScreenManager.get_instance()
    total = len(actions)
    step_reports: List[Dict[str, Any]] = []
    start_total = time.time()

    from ui.theme import BOLD, CYAN, DIM, GREEN, RED, RESET, YELLOW
    _safe_print(f"\n{CYAN}╭─ Desktop Actions ({total} steps) ──────────────────────────────╮{RESET}")

    failed_step_idx = None
    failure_error = None
    last_screenshot: Optional[Dict[str, Any]] = None

    for idx, item in enumerate(actions):
        if not isinstance(item, dict):
            err_msg = f"Step {idx+1} is not a valid action dictionary: {item}"
            _safe_print(f"{CYAN}│{RESET} {RED}[✗] {idx+1}. Invalid action format{RESET}")
            failed_step_idx = idx + 1
            failure_error = err_msg
            break

        action_type = item.get("action", "").lower().strip()
        t0 = time.time()

        try:
            if action_type in ("click", "left_click"):
                coord = item.get("coordinate") or item.get("target")
                x, y = (coord[0], coord[1]) if (coord and len(coord) >= 2) else (None, None)
                rx, ry = ctrl.click(x=x, y=y, button="left")
                dur_ms = int((time.time() - t0) * 1000)
                desc = f"click ({rx}, {ry})"
                _safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                step_reports.append({"step": idx + 1, "action": "click", "status": "ok", "x": rx, "y": ry, "elapsed_ms": dur_ms})

            elif action_type == "double_click":
                coord = item.get("coordinate") or item.get("target")
                x, y = (coord[0], coord[1]) if (coord and len(coord) >= 2) else (None, None)
                rx, ry = ctrl.double_click(x=x, y=y)
                dur_ms = int((time.time() - t0) * 1000)
                desc = f"double_click ({rx}, {ry})"
                _safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                step_reports.append({"step": idx + 1, "action": "double_click", "status": "ok", "x": rx, "y": ry, "elapsed_ms": dur_ms})

            elif action_type == "triple_click":
                coord = item.get("coordinate") or item.get("target")
                x, y = (coord[0], coord[1]) if (coord and len(coord) >= 2) else (None, None)
                rx, ry = ctrl.triple_click(x=x, y=y)
                dur_ms = int((time.time() - t0) * 1000)
                desc = f"triple_click ({rx}, {ry})"
                _safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                step_reports.append({"step": idx + 1, "action": "triple_click", "status": "ok", "x": rx, "y": ry, "elapsed_ms": dur_ms})

            elif action_type == "right_click":
                coord = item.get("coordinate") or item.get("target")
                x, y = (coord[0], coord[1]) if (coord and len(coord) >= 2) else (None, None)
                rx, ry = ctrl.right_click(x=x, y=y)
                dur_ms = int((time.time() - t0) * 1000)
                desc = f"right_click ({rx}, {ry})"
                _safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                step_reports.append({"step": idx + 1, "action": "right_click", "status": "ok", "x": rx, "y": ry, "elapsed_ms": dur_ms})

            elif action_type == "middle_click":
                coord = item.get("coordinate") or item.get("target")
                x, y = (coord[0], coord[1]) if (coord and len(coord) >= 2) else (None, None)
                rx, ry = ctrl.middle_click(x=x, y=y)
                dur_ms = int((time.time() - t0) * 1000)
                desc = f"middle_click ({rx}, {ry})"
                _safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                step_reports.append({"step": idx + 1, "action": "middle_click", "status": "ok", "x": rx, "y": ry, "elapsed_ms": dur_ms})

            elif action_type in ("mouse_move", "move"):
                coord = item.get("coordinate") or item.get("target")
                if not coord or len(coord) < 2:
                    raise ValueError("Action 'mouse_move' requires 'coordinate': [x, y]")
                rx, ry = ctrl.mouse_move(coord[0], coord[1])
                dur_ms = int((time.time() - t0) * 1000)
                desc = f"mouse_move ({rx}, {ry})"
                _safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                step_reports.append({"step": idx + 1, "action": "mouse_move", "status": "ok", "x": rx, "y": ry, "elapsed_ms": dur_ms})

            elif action_type == "mouse_down":
                coord = item.get("coordinate") or item.get("target")
                x, y = (coord[0], coord[1]) if (coord and len(coord) >= 2) else (None, None)
                button = str(item.get("button", "left"))
                rx, ry = ctrl.mouse_down(x=x, y=y, button=button)
                dur_ms = int((time.time() - t0) * 1000)
                desc = f"mouse_down {button} ({rx}, {ry})"
                _safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                step_reports.append({"step": idx + 1, "action": "mouse_down", "status": "ok", "x": rx, "y": ry, "button": button, "elapsed_ms": dur_ms})

            elif action_type == "mouse_up":
                coord = item.get("coordinate") or item.get("target")
                x, y = (coord[0], coord[1]) if (coord and len(coord) >= 2) else (None, None)
                button = str(item.get("button", "left"))
                rx, ry = ctrl.mouse_up(x=x, y=y, button=button)
                dur_ms = int((time.time() - t0) * 1000)
                desc = f"mouse_up {button} ({rx}, {ry})"
                _safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                step_reports.append({"step": idx + 1, "action": "mouse_up", "status": "ok", "x": rx, "y": ry, "button": button, "elapsed_ms": dur_ms})

            elif action_type in ("left_click_drag", "drag"):
                coord = item.get("coordinate") or item.get("target")
                start = item.get("start")
                end = item.get("end")
                duration = float(item.get("duration", 0.5))

                if coord and len(coord) >= 4:
                    ctrl.drag(coord[0], coord[1], coord[2], coord[3], duration=duration)
                    desc = f"drag [{coord[0]},{coord[1]}] -> [{coord[2]},{coord[3]}]"
                elif start and end:
                    ctrl.drag(start[0], start[1], end[0], end[1], duration=duration)
                    desc = f"drag {start} -> {end}"
                elif coord and len(coord) >= 2:
                    rx, ry = ctrl.drag_to(coord[0], coord[1], duration=duration)
                    desc = f"drag_to ({rx}, {ry})"
                else:
                    raise ValueError("Action 'left_click_drag' requires destination 'coordinate': [x, y] or [start_x, start_y, end_x, end_y]")

                dur_ms = int((time.time() - t0) * 1000)
                _safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                step_reports.append({"step": idx + 1, "action": "left_click_drag", "status": "ok", "elapsed_ms": dur_ms})

            elif action_type in ("type", "fill"):
                val = str(item.get("text") or item.get("value") or "")
                ctrl.type_text(val)
                dur_ms = int((time.time() - t0) * 1000)
                val_preview = val if len(val) <= 15 else val[:12] + "..."
                desc = f"type \"{val_preview}\""
                _safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                step_reports.append({"step": idx + 1, "action": "type", "status": "ok", "text": val, "elapsed_ms": dur_ms})

            elif action_type in ("key", "hotkey"):
                key_str = str(item.get("key") or item.get("text") or "Return")
                keys = key_str.replace("+", " ").split()
                if len(keys) > 1:
                    ctrl.key_combination(keys)
                else:
                    ctrl.press_key(keys[0])
                dur_ms = int((time.time() - t0) * 1000)
                desc = f"key \"{key_str}\""
                _safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                step_reports.append({"step": idx + 1, "action": "key", "status": "ok", "key": key_str, "elapsed_ms": dur_ms})

            elif action_type == "press_enter":
                ctrl.press_key("Return")
                dur_ms = int((time.time() - t0) * 1000)
                desc = "press_enter"
                _safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                step_reports.append({"step": idx + 1, "action": "press_enter", "status": "ok", "elapsed_ms": dur_ms})

            elif action_type == "scroll":
                clicks = 3
                direction = "down"
                raw_val = item.get("scroll") or item.get("clicks") or item.get("text")
                if raw_val is not None:
                    try:
                        val = int(raw_val)
                        clicks = abs(val)
                        direction = "up" if val > 0 else "down"
                    except (ValueError, TypeError):
                        direction = "up" if "up" in str(raw_val).lower() else "down"
                else:
                    direction = str(item.get("direction", "down")).lower()
                    clicks = int(item.get("clicks", 3))

                ctrl.scroll(clicks=clicks, direction=direction)
                dur_ms = int((time.time() - t0) * 1000)
                desc = f"scroll {direction} ({clicks} clicks)"
                _safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                step_reports.append({"step": idx + 1, "action": "scroll", "status": "ok", "elapsed_ms": dur_ms})

            elif action_type in ("wait", "sleep"):
                ms = int(item.get("ms") or item.get("text") or 500)
                time.sleep(ms / 1000.0)
                desc = f"wait {ms}ms"
                _safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({ms}ms){RESET}")
                step_reports.append({"step": idx + 1, "action": "wait", "status": "ok", "ms": ms})

            elif action_type == "screenshot":
                shot = screen_mgr.capture_screenshot()
                last_screenshot = shot
                dur_ms = int((time.time() - t0) * 1000)
                desc = f"screenshot ({shot.get('filename')})"
                _safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                step_reports.append({"step": idx + 1, "action": "screenshot", "status": "ok", "path": shot.get("path"), "elapsed_ms": dur_ms})

            elif action_type == "cursor_position":
                cx, cy = ctrl.get_cursor_position()
                dur_ms = int((time.time() - t0) * 1000)
                desc = f"cursor_position ({cx}, {cy})"
                _safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                step_reports.append({"step": idx + 1, "action": "cursor_position", "status": "ok", "x": cx, "y": cy, "elapsed_ms": dur_ms})

            elif action_type in ("window_focus", "focus_window", "focus"):
                target_title = item.get("title") or item.get("target") or item.get("name")
                target_id = item.get("window_id") or item.get("id")
                res_focus = await asyncio.to_thread(focus_desktop_window, title=target_title, window_id=target_id)
                dur_ms = int((time.time() - t0) * 1000)
                desc = f"window_focus ('{target_title or target_id}')"
                if res_focus.get("success"):
                    _safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                    step_reports.append({"step": idx + 1, "action": "window_focus", "status": "ok", "title": target_title, "elapsed_ms": dur_ms})
                else:
                    raise RuntimeError(res_focus.get("error", "Window focus failed"))

            elif action_type in ("window_state", "set_window_state"):
                target_title = item.get("title") or item.get("target")
                target_id = item.get("window_id") or item.get("id")
                state_act = item.get("state") or item.get("value") or "restore"
                res_state = await asyncio.to_thread(set_desktop_window_state, action=state_act, title=target_title, window_id=target_id)
                dur_ms = int((time.time() - t0) * 1000)
                desc = f"window_state {state_act} ('{target_title or target_id}')"
                if res_state.get("success"):
                    _safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                    step_reports.append({"step": idx + 1, "action": "window_state", "status": "ok", "state": state_act, "elapsed_ms": dur_ms})
                else:
                    raise RuntimeError(res_state.get("error", "Window state change failed"))

            elif action_type in ("clipboard_paste", "paste"):
                paste_text = item.get("text") or item.get("value") or ""
                res_paste = await asyncio.to_thread(paste_text_via_clipboard, text=paste_text)
                dur_ms = int((time.time() - t0) * 1000)
                preview = paste_text[:25] + ("..." if len(paste_text) > 25 else "")
                desc = f"clipboard_paste ({len(paste_text)} chars: \"{preview}\")"
                _safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                step_reports.append({"step": idx + 1, "action": "clipboard_paste", "status": "ok", "length": len(paste_text), "elapsed_ms": dur_ms})

            elif action_type in ("clipboard_write", "copy", "set_clipboard"):
                copy_text = item.get("text") or item.get("value") or ""
                res_copy = await asyncio.to_thread(copy_to_clipboard, text=copy_text)
                dur_ms = int((time.time() - t0) * 1000)
                desc = f"clipboard_write ({len(copy_text)} chars)"
                _safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                step_reports.append({"step": idx + 1, "action": "clipboard_write", "status": "ok", "length": len(copy_text), "elapsed_ms": dur_ms})

            elif action_type in ("clipboard_read", "get_clipboard"):
                res_read = await asyncio.to_thread(read_from_clipboard)
                dur_ms = int((time.time() - t0) * 1000)
                desc = f"clipboard_read ({res_read.get('length', 0)} chars)"
                _safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                step_reports.append({"step": idx + 1, "action": "clipboard_read", "status": "ok", "content": res_read.get("content", ""), "elapsed_ms": dur_ms})

            else:
                raise ValueError(f"Unknown desktop action: '{action_type}'")

        except Exception as step_err:
            dur_ms = int((time.time() - t0) * 1000)
            desc = f"{action_type} -> FAILED: {step_err}"
            _safe_print(f"{CYAN}│{RESET} {RED}[✗]{RESET} {idx+1}. {desc:<50} {RED}({dur_ms}ms){RESET}")

            # Mark remaining steps as skipped
            for skip_idx in range(idx + 1, total):
                skip_item = actions[skip_idx]
                skip_act = skip_item.get("action", "step") if isinstance(skip_item, dict) else "step"
                _safe_print(f"{CYAN}│{RESET} {DIM}[-] {skip_idx+1}. {skip_act} (Skipped){RESET}")

            failed_step_idx = idx + 1
            failure_error = str(step_err)
            break

    _safe_print(f"{CYAN}╰──────────────────────────────────────────────────────────╯{RESET}")
    total_elapsed_ms = int((time.time() - start_total) * 1000)

    # If no explicit screenshot was captured in the batch, capture one automatically at the end to show final state
    if not last_screenshot:
        try:
            last_screenshot = screen_mgr.capture_screenshot()
        except Exception:
            pass

    if failed_step_idx:
        _safe_print(f"{RED}[!] Desktop batch execution failed at Step {failed_step_idx}: {failure_error}{RESET}\n")
        res_fail: Dict[str, Any] = {
            "success": False,
            "failed_step": failed_step_idx,
            "error": f"Step {failed_step_idx} failed: {failure_error}",
            "completed_steps": len(step_reports),
            "total_steps": total,
            "step_reports": step_reports,
            "elapsed_ms": total_elapsed_ms,
        }
        if last_screenshot and "content" in last_screenshot:
            res_fail["content"] = last_screenshot["content"]
        return res_fail

    _safe_print(f"{GREEN}[+] Completed in {total_elapsed_ms}ms (All {total} desktop actions succeeded){RESET}\n")
    res_ok: Dict[str, Any] = {
        "success": True,
        "message": f"All {total} desktop actions executed successfully in {total_elapsed_ms}ms.",
        "total_steps": total,
        "completed_steps": total,
        "elapsed_ms": total_elapsed_ms,
        "step_reports": step_reports,
    }
    if last_screenshot and "content" in last_screenshot:
        res_ok["content"] = last_screenshot["content"]
    return res_ok


@with_error_reporting("windows_list")
async def windows_list() -> str:
    """List all open desktop application windows with title, PID, and bounding box coordinates."""
    res = await asyncio.to_thread(list_desktop_windows)
    return json.dumps(res, indent=2, ensure_ascii=False)


@with_error_reporting("window_focus")
async def window_focus(
    title: Optional[str] = None,
    window_id: Optional[int | str] = None,
) -> str:
    """Activate and bring the target desktop application window to the foreground."""
    res = await asyncio.to_thread(focus_desktop_window, title=title, window_id=window_id)
    return json.dumps(res, indent=2, ensure_ascii=False)


@with_error_reporting("window_state")
async def window_state(
    action: str,
    title: Optional[str] = None,
    window_id: Optional[int | str] = None,
) -> str:
    """Change window state (maximize, minimize, restore, close)."""
    res = await asyncio.to_thread(set_desktop_window_state, action=action, title=title, window_id=window_id)
    return json.dumps(res, indent=2, ensure_ascii=False)


@with_error_reporting("clipboard_write")
async def clipboard_write(text: str) -> str:
    """Copy text string to the operating system clipboard."""
    res = await asyncio.to_thread(copy_to_clipboard, text=text)
    return json.dumps(res, indent=2, ensure_ascii=False)


@with_error_reporting("clipboard_read")
async def clipboard_read() -> str:
    """Read the current text contents from the operating system clipboard."""
    res = await asyncio.to_thread(read_from_clipboard)
    return json.dumps(res, indent=2, ensure_ascii=False)


@with_error_reporting("system_info")
async def system_info() -> str:
    """Retrieve structured operating system health, CPU, memory, disk, and process telemetry."""
    res = await asyncio.to_thread(get_system_metrics)
    return json.dumps(res, indent=2, ensure_ascii=False)

