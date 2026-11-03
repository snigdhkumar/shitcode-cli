"""Multi-Tier Action Dispatch Chain.
Executes semantic accessibility patterns with intelligent physical coordinate fallback.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict

from tools.desktop.accessibility.actions import (
    perform_focus,
    perform_invoke,
    perform_select,
    perform_toggle,
    perform_value,
)
from tools.desktop.input import InputController
from tools.desktop.system.clipboard import copy_to_clipboard
from tools.desktop.window.manager import focus_desktop_window

logger = logging.getLogger("shitcode.tools.desktop.accessibility.dispatch")


def physical_click_fallback(entry: Dict[str, Any]) -> bool:
    """Fallback: focus window and physically click element center."""
    try:
        hwnd = entry.get("hwnd", 0)
        bounds = entry.get("bounds", [0, 0, 0, 0])
        if bounds[2] <= 0 or bounds[3] <= 0:
            return False

        if hwnd:
            focus_desktop_window(window_id=hwnd)
            time.sleep(0.04)

        cx = bounds[0] + bounds[2] // 2
        cy = bounds[1] + bounds[3] // 2
        ctrl = InputController.get_instance()
        ctrl.click(cx, cy)
        return True
    except Exception as e:
        logger.debug(f"Physical click fallback error: {e}")
        return False


def dispatch_element_action(
    entry: Dict[str, Any],
    action: str,
    value: str = "",
) -> Dict[str, Any]:
    """Execute action through the multi-stage ladder."""
    elem = entry.get("element")
    act = (action or "click").strip().lower()
    ref = entry.get("ref", "")
    role = entry.get("role", "")
    name = entry.get("name", "")

    # 1. Click ladder
    if act == "click":
        if elem and perform_invoke(elem):
            return {"ok": True, "success": True, "ref": ref, "action": "click", "method": "semantic_invoke", "message": f"Clicked '{name}' ({role}) via InvokePattern."}
        if elem and perform_toggle(elem):
            return {"ok": True, "success": True, "ref": ref, "action": "click", "method": "semantic_toggle", "message": f"Clicked '{name}' ({role}) via TogglePattern."}
        if physical_click_fallback(entry):
            return {"ok": True, "success": True, "ref": ref, "action": "click", "method": "physical_fallback", "message": f"Clicked '{name}' ({role}) via coordinate fallback."}
        return {"ok": False, "success": False, "ref": ref, "error": f"Failed to deliver click to '{name}' ({role})."}

    # 2. Type ladder
    elif act == "type":
        if elem and perform_value(elem, value):
            return {"ok": True, "success": True, "ref": ref, "action": "type", "method": "semantic_value", "message": f"Typed '{value}' into '{name}' ({role}) via ValuePattern."}
        # Physical type fallback
        if physical_click_fallback(entry):
            time.sleep(0.05)
            ctrl = InputController.get_instance()
            copy_to_clipboard(value)
            ctrl.hotkey("ctrl", "v")
            return {"ok": True, "success": True, "ref": ref, "action": "type", "method": "physical_paste", "message": f"Pasted '{value}' into '{name}' ({role})."}
        return {"ok": False, "success": False, "ref": ref, "error": f"Failed to type into '{name}' ({role})."}

    # 3. Toggle ladder
    elif act in ("toggle", "check", "uncheck"):
        if elem and perform_toggle(elem):
            return {"ok": True, "success": True, "ref": ref, "action": "toggle", "method": "semantic_toggle", "message": f"Toggled '{name}' ({role})."}
        if physical_click_fallback(entry):
            return {"ok": True, "success": True, "ref": ref, "action": "toggle", "method": "physical_click", "message": f"Toggled '{name}' ({role}) via click."}
        return {"ok": False, "success": False, "ref": ref, "error": f"Failed to toggle '{name}' ({role})."}

    # 4. Select ladder
    elif act == "select":
        if elem and perform_select(elem):
            return {"ok": True, "success": True, "ref": ref, "action": "select", "method": "semantic_select", "message": f"Selected '{name}' ({role})."}
        if physical_click_fallback(entry):
            return {"ok": True, "success": True, "ref": ref, "action": "select", "method": "physical_click", "message": f"Selected '{name}' ({role}) via click."}
        return {"ok": False, "success": False, "ref": ref, "error": f"Failed to select '{name}' ({role})."}

    # 5. Focus ladder
    elif act == "focus":
        if elem and perform_focus(elem):
            return {"ok": True, "success": True, "ref": ref, "action": "focus", "method": "semantic_focus", "message": f"Focused '{name}' ({role})."}
        if physical_click_fallback(entry):
            return {"ok": True, "success": True, "ref": ref, "action": "focus", "method": "physical_click", "message": f"Focused '{name}' ({role}) via click."}
        return {"ok": False, "success": False, "ref": ref, "error": f"Failed to focus '{name}' ({role})."}

    return {"ok": False, "success": False, "ref": ref, "error": f"Unsupported accessibility action '{action}'."}
