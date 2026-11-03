"""Native Cross-Platform Desktop OS Accessibility Engine for Windows & Linux.
Provides token-efficient UI element discovery (snapshots) and headless element actions
without cursor hijacking or full-screen visual screenshot overhead.
"""

from __future__ import annotations

import logging
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("shitcode.tools.desktop.accessibility")

_IS_WIN = sys.platform == "win32"
_IS_LINUX = sys.platform.startswith("linux")

# In-memory snapshot cache for fast ref resolution: ref -> {element, bounds, hwnd, name, role}
_SNAPSHOT_CACHE: Dict[str, Dict[str, Any]] = {}
_LAST_SNAPSHOT_TIME: float = 0.0

# Windows ControlType mapping to readable roles
WIN_CONTROL_TYPE_NAMES: Dict[int, str] = {
    50000: "button",
    50001: "calendar",
    50002: "checkbox",
    50003: "combobox",
    50004: "edit",
    50005: "hyperlink",
    50006: "image",
    50007: "list",
    50008: "listitem",
    50009: "menu",
    50010: "menubar",
    50011: "menuitem",
    50012: "progressbar",
    50013: "radiobutton",
    50014: "scrollbar",
    50015: "slider",
    50016: "spinner",
    50017: "statusbar",
    50018: "tab",
    50019: "tabitem",
    50020: "text",
    50021: "toolbar",
    50022: "tooltip",
    50023: "tree",
    50024: "treeitem",
    50025: "custom",
    50026: "group",
    50028: "document",
    50030: "window",
    50032: "pane",
    50033: "header",
    50034: "headeritem",
    50035: "table",
    50036: "titlebar",
    50037: "separator",
}

INTERACTIVE_ROLES = {
    "button", "checkbox", "combobox", "edit", "hyperlink", "listitem",
    "menuitem", "radiobutton", "slider", "tabitem", "treeitem", "tab"
}


LINUX_ROLE_NAMES: Dict[str, str] = {
    "push button": "button",
    "toggle button": "button",
    "check box": "checkbox",
    "radio button": "radiobutton",
    "combo box": "combobox",
    "entry": "edit",
    "text": "text",
    "page tab": "tabitem",
    "page tab list": "tab",
    "menu": "menu",
    "menu item": "menuitem",
    "check menu item": "menuitem",
    "radio menu item": "menuitem",
    "link": "hyperlink",
    "list item": "listitem",
    "slider": "slider",
    "spin button": "spinner",
    "tree item": "treeitem",
}


def _get_win_uia():
    """Lazily initialize Windows CUIAutomation COM client."""
    if not _IS_WIN:
        return None
    try:
        import comtypes.client
        comtypes.client.GetModule("UIAutomationCore.dll")
        from comtypes.gen.UIAutomationClient import CUIAutomation, IUIAutomation
        return comtypes.client.CreateObject(CUIAutomation, interface=IUIAutomation)
    except Exception as e:
        logger.debug(f"Failed to initialize Windows UIAutomation: {e}")
        return None


def _find_window_hwnd(app_name: Optional[str] = None, window_id: Optional[str] = None) -> Optional[int]:
    """Resolve target window HWND on Windows."""
    if not _IS_WIN:
        return None
    try:
        import win32gui

        if window_id:
            try:
                hwnd = int(window_id, 0)
                if win32gui.IsWindow(hwnd):
                    return hwnd
            except ValueError:
                pass

        if app_name:
            app_lower = app_name.lower().strip()
            found_hwnds: List[Tuple[int, str]] = []

            def _enum_cb(hwnd: int, extra: list) -> bool:
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd).strip()
                    if title and app_lower in title.lower():
                        extra.append((hwnd, title))
                return True

            win32gui.EnumWindows(_enum_cb, found_hwnds)
            if found_hwnds:
                # Return the first matching visible window
                return found_hwnds[0][0]

        # Default: Foreground window
        fg = win32gui.GetForegroundWindow()
        if fg and win32gui.IsWindow(fg):
            return fg
    except Exception as e:
        logger.debug(f"Window handle resolution error: {e}")
    return None


async def desktop_snapshot(
    app_name: Optional[str] = None,
    window_id: Optional[str] = None,
    interactive_only: bool = True,
    max_elements: int = 60
) -> Dict[str, Any]:
    """Inspect the native OS accessibility tree of a window.
    Returns a compact list of controls with refs (@e1, @e2) for headless interaction.
    """
    global _SNAPSHOT_CACHE, _LAST_SNAPSHOT_TIME
    _SNAPSHOT_CACHE.clear()
    _LAST_SNAPSHOT_TIME = time.time()

    if _IS_WIN:
        return await _win_desktop_snapshot(app_name, window_id, interactive_only, max_elements)
    elif _IS_LINUX:
        return await _linux_desktop_snapshot(app_name, window_id, interactive_only, max_elements)
    else:
        return {
            "ok": False,
            "error": "OS accessibility engine is only supported on Windows and Linux."
        }


async def _win_desktop_snapshot(
    app_name: Optional[str],
    window_id: Optional[str],
    interactive_only: bool,
    max_elements: int
) -> Dict[str, Any]:
    """Windows implementation using IUIAutomation."""
    try:
        import win32gui
        uia = _get_win_uia()
        if not uia:
            return {
                "ok": False,
                "error": "Windows UIAutomationCore COM interface is unavailable."
            }

        hwnd = _find_window_hwnd(app_name, window_id)
        if not hwnd:
            return {
                "ok": False,
                "error": f"No matching window found for app_name='{app_name or ''}' or window_id='{window_id or ''}'."
            }

        window_title = win32gui.GetWindowText(hwnd).strip() or "Untitled Window"
        root_elem = uia.ElementFromHandle(hwnd)
        if not root_elem:
            return {
                "ok": False,
                "error": f"Unable to attach UIAutomation to window '{window_title}' (HWND: {hwnd})."
            }

        walker = uia.ControlViewWalker
        elements_list: List[Dict[str, Any]] = []
        elem_index = 1

        # Recursive depth-limited tree walk
        def _walk_tree(element, depth: int):
            nonlocal elem_index
            if depth > 6 or len(elements_list) >= max_elements:
                return

            try:
                child = walker.GetFirstChildElement(element)
            except Exception:
                child = None

            while child:
                if len(elements_list) >= max_elements:
                    break

                try:
                    name = str(child.CurrentName or "").strip()
                    control_type = child.CurrentControlType
                    role = WIN_CONTROL_TYPE_NAMES.get(control_type, "control")
                    is_offscreen = bool(child.CurrentIsOffscreen)
                    is_enabled = bool(child.CurrentIsEnabled)
                    rect = child.CurrentBoundingRectangle
                    bounds = [rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top]

                    is_actionable = role in INTERACTIVE_ROLES
                    include = True

                    # Filters
                    if is_offscreen or bounds[2] <= 0 or bounds[3] <= 0:
                        include = False
                    elif interactive_only and not is_actionable:
                        include = False

                    if include and (name or is_actionable):
                        ref = f"@e{elem_index}"
                        elem_index += 1
                        item = {
                            "ref": ref,
                            "role": role,
                            "name": name,
                            "bounds": bounds,
                            "enabled": is_enabled
                        }
                        elements_list.append(item)
                        _SNAPSHOT_CACHE[ref] = {
                            "element": child,
                            "bounds": bounds,
                            "hwnd": hwnd,
                            "name": name,
                            "role": role
                        }
                except Exception:
                    pass

                # Recurse children
                _walk_tree(child, depth + 1)

                try:
                    child = walker.GetNextSiblingElement(child)
                except Exception:
                    break

        _walk_tree(root_elem, 1)

        return {
            "ok": True,
            "window": {
                "id": str(hwnd),
                "title": window_title,
                "elements_found": len(elements_list)
            },
            "elements": elements_list,
            "note": "Use desktop_interact with a ref (e.g. '@e1') to click or type. If the app is visual/canvas, use computer_actions."
        }
    except Exception as e:
        logger.error(f"Error in Windows desktop snapshot: {e}", exc_info=True)
        return {
            "ok": False,
            "error": f"Windows desktop snapshot error: {str(e)}"
        }


async def _linux_desktop_snapshot(
    app_name: Optional[str],
    window_id: Optional[str],
    interactive_only: bool,
    max_elements: int
) -> Dict[str, Any]:
    """Linux implementation via AT-SPI2 (pyatspi) or X11 xwininfo/wmctrl."""
    from tools.desktop.controller import has_gui_display
    if not has_gui_display():
        return {
            "ok": False,
            "error": "No graphical display detected (neither DISPLAY nor WAYLAND_DISPLAY is set). You are running in a headless Linux environment (e.g. Google Cloud Shell or SSH). Desktop GUI accessibility is not available. Use terminal or browser_* tools instead.",
            "is_headless": True
        }

    from tools.desktop.windows import list_desktop_windows
    wins = list_desktop_windows()
    target_win = None

    if window_id:
        for w in wins:
            if str(w.get("id")) == str(window_id):
                target_win = w
                break

    if not target_win and app_name:
        app_lower = app_name.lower().strip()
        for w in wins:
            if app_lower in w.get("title", "").lower():
                target_win = w
                break

    if not target_win and wins:
        target_win = wins[0]

    window_title = target_win.get("title", "Active Window") if target_win else "Desktop"
    target_x11_id = target_win.get("id") if target_win else None
    target_bounds = target_win.get("bounds", [0, 0, 1920, 1080]) if target_win else [0, 0, 1920, 1080]

    elements_list: List[Dict[str, Any]] = []
    elem_index = 1

    # Stage 1: Attempt native AT-SPI2 via pyatspi
    try:
        import pyatspi
        desktop = pyatspi.Registry.getDesktop(0)
        target_obj = None

        for app in desktop:
            if not app:
                continue
            for win in app:
                if not win:
                    continue
                w_name = win.name or ""
                if app_name and app_name.lower() in w_name.lower():
                    target_obj = win
                    window_title = w_name
                    break
                elif not target_obj:
                    target_obj = win
            if target_obj and app_name:
                break

        if target_obj:
            def _walk_atspi(node, depth: int):
                nonlocal elem_index
                if depth > 5 or len(elements_list) >= max_elements or not node:
                    return

                for i in range(node.getChildCount()):
                    if len(elements_list) >= max_elements:
                        break
                    try:
                        child = node.getChildAtIndex(i)
                        if not child:
                            continue

                        raw_role = child.getRoleName() or ""
                        role = LINUX_ROLE_NAMES.get(raw_role.lower(), "control")
                        name = (child.name or "").strip()
                        state = child.getState()
                        is_enabled = state.contains(pyatspi.STATE_ENABLED) if state else True
                        is_showing = state.contains(pyatspi.STATE_SHOWING) if state else True

                        bounds = [0, 0, 0, 0]
                        try:
                            comp = child.queryComponent()
                            if comp:
                                ext = comp.getExtents(pyatspi.DESKTOP_COORDS)
                                bounds = [ext.x, ext.y, ext.width, ext.height]
                        except Exception:
                            pass

                        is_actionable = role in INTERACTIVE_ROLES
                        include = is_showing and bounds[2] > 0 and bounds[3] > 0
                        if interactive_only and not is_actionable:
                            include = False

                        if include and (name or is_actionable):
                            ref = f"@e{elem_index}"
                            elem_index += 1
                            item = {
                                "ref": ref,
                                "role": role,
                                "name": name,
                                "bounds": bounds,
                                "enabled": is_enabled
                            }
                            elements_list.append(item)
                            _SNAPSHOT_CACHE[ref] = {
                                "atspi_obj": child,
                                "bounds": bounds,
                                "name": name,
                                "role": role
                            }

                        _walk_atspi(child, depth + 1)
                    except Exception:
                        pass

            _walk_atspi(target_obj, 1)
    except Exception as atspi_err:
        logger.debug(f"pyatspi unavailable: {atspi_err}")

    # Stage 2: Fallback to X11 xwininfo subwindow traversal if AT-SPI produced 0 elements
    if not elements_list and target_x11_id:
        try:
            import re
            import subprocess
            cmd = ["xwininfo", "-children", "-id", str(target_x11_id)]
            out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
            # Match lines: 0x123456 (has no name): ()  100x30+10+50  +110+150
            pattern = re.compile(r'\s+(0x[0-9a-fA-F]+)\s+(?:"([^"]*)"|\(has no name\)):.*?(\d+)x(\d+)\+(-?\d+)\+(-?\d+)')
            for match in pattern.finditer(out):
                if len(elements_list) >= max_elements:
                    break
                sub_id, sub_name, w_str, h_str, x_str, y_str = match.groups()
                w_val, h_val = int(w_str), int(h_str)
                x_val, y_val = int(x_str), int(y_str)

                # Convert relative to window coordinates
                abs_x = target_bounds[0] + x_val
                abs_y = target_bounds[1] + y_val
                bounds = [abs_x, abs_y, w_val, h_val]

                if w_val > 15 and h_val > 15:
                    ref = f"@e{elem_index}"
                    elem_index += 1
                    name = sub_name or f"Control {sub_id}"
                    item = {
                        "ref": ref,
                        "role": "control",
                        "name": name,
                        "bounds": bounds,
                        "enabled": True
                    }
                    elements_list.append(item)
                    _SNAPSHOT_CACHE[ref] = {
                        "x11_id": sub_id,
                        "bounds": bounds,
                        "name": name,
                        "role": "control"
                    }
        except Exception as xwin_err:
            logger.debug(f"xwininfo fallback unavailable: {xwin_err}")

    return {
        "ok": True,
        "window": {
            "id": str(target_x11_id or "0"),
            "title": window_title,
            "bounds": target_bounds,
            "elements_found": len(elements_list)
        },
        "elements": elements_list,
        "note": "Use desktop_interact with a ref (e.g. '@e1') to click or type. If the app is visual/canvas, use computer_actions."
    }


async def desktop_interact(
    ref: str,
    action: str = "click",
    text: Optional[str] = None,
    app_name: Optional[str] = None
) -> Dict[str, Any]:
    """Perform a headless OS accessibility action on a UI element using its ref from desktop_snapshot."""
    ref_norm = ref.strip()
    if not ref_norm.startswith("@"):
        ref_norm = f"@{ref_norm}"

    cached = _SNAPSHOT_CACHE.get(ref_norm)
    if not cached:
        return {
            "ok": False,
            "error": f"Ref '{ref_norm}' not found or snapshot expired. Run desktop_snapshot again to get fresh element refs.",
            "disposition": {"delivery": "not_delivered", "retry": "safe"}
        }

    element = cached.get("element")
    bounds = cached.get("bounds", [0, 0, 0, 0])
    role = cached.get("role", "control")
    name = cached.get("name", "")

    action_lower = action.lower().strip()

    if _IS_WIN:
        return await _win_interact(element, bounds, role, name, action_lower, text)
    elif _IS_LINUX:
        return await _linux_interact(cached, action_lower, text)
    else:
        return {
            "ok": False,
            "error": "Desktop accessibility interactions are not supported on this platform."
        }


async def _win_interact(
    element: Any,
    bounds: List[int],
    role: str,
    name: str,
    action: str,
    text: Optional[str]
) -> Dict[str, Any]:
    """Execute action on Windows element via COM patterns with physical click fallback."""
    from tools.desktop.controller import get_pyautogui

    try:
        from comtypes.gen.UIAutomationClient import (
            UIA_InvokePatternId,
            UIA_TogglePatternId,
            UIA_ValuePatternId,
            IUIAutomationInvokePattern,
            IUIAutomationTogglePattern,
            IUIAutomationValuePattern
        )
    except Exception as e:
        return {"ok": False, "error": f"Failed importing UIAutomation pattern interfaces: {e}"}

    delivered_method = "headless"

    try:
        if action == "click":
            # 1. Try InvokePattern (buttons, links, menu items)
            try:
                pat = element.GetCurrentPattern(UIA_InvokePatternId)
                if pat:
                    inv = pat.QueryInterface(IUIAutomationInvokePattern)
                    inv.Invoke()
                    return {"ok": True, "action": "click", "method": "InvokePattern (headless)", "element": name or role}
            except Exception:
                pass

            # 2. Try TogglePattern (checkboxes, switches)
            try:
                pat = element.GetCurrentPattern(UIA_TogglePatternId)
                if pat:
                    tog = pat.QueryInterface(IUIAutomationTogglePattern)
                    tog.Toggle()
                    return {"ok": True, "action": "click", "method": "TogglePattern (headless)", "element": name or role}
            except Exception:
                pass

            # 3. Fallback: Deterministic physical click at element bounds center
            pag = get_pyautogui()
            if pag and bounds and len(bounds) == 4 and bounds[2] > 0 and bounds[3] > 0:
                cx = bounds[0] + bounds[2] // 2
                cy = bounds[1] + bounds[3] // 2
                pag.click(cx, cy)
                return {"ok": True, "action": "click", "method": f"physical click at ({cx}, {cy})", "element": name or role}

            return {"ok": False, "error": f"Element '{name or role}' does not support invoke or click."}

        elif action == "type":
            if not text:
                return {"ok": False, "error": "Action 'type' requires 'text' parameter."}

            # 1. Try ValuePattern (headless text input)
            try:
                pat = element.GetCurrentPattern(UIA_ValuePatternId)
                if pat:
                    val = pat.QueryInterface(IUIAutomationValuePattern)
                    val.SetValue(str(text))
                    return {"ok": True, "action": "type", "method": "ValuePattern (headless)", "text": text}
            except Exception:
                pass

            # 2. Fallback: Focus and type
            try:
                element.SetFocus()
            except Exception:
                pass

            pag = get_pyautogui()
            if pag:
                pag.typewrite(str(text), interval=0.01)
                return {"ok": True, "action": "type", "method": "focus + physical typing", "text": text}

            return {"ok": False, "error": f"Element '{name or role}' does not support setting text."}

        elif action == "toggle":
            try:
                pat = element.GetCurrentPattern(UIA_TogglePatternId)
                if pat:
                    tog = pat.QueryInterface(IUIAutomationTogglePattern)
                    tog.Toggle()
                    return {"ok": True, "action": "toggle", "method": "TogglePattern (headless)", "element": name or role}
            except Exception as e:
                return {"ok": False, "error": f"Failed to toggle element: {e}"}

        elif action == "clear":
            try:
                pat = element.GetCurrentPattern(UIA_ValuePatternId)
                if pat:
                    val = pat.QueryInterface(IUIAutomationValuePattern)
                    val.SetValue("")
                    return {"ok": True, "action": "clear", "method": "ValuePattern (headless)"}
            except Exception:
                pass
            return {"ok": False, "error": f"Element '{name or role}' does not support clearing value."}

        elif action == "focus":
            try:
                element.SetFocus()
                return {"ok": True, "action": "focus", "element": name or role}
            except Exception as e:
                return {"ok": False, "error": f"Failed to focus element: {e}"}

        else:
            return {"ok": False, "error": f"Unsupported accessibility action '{action}'."}

    except Exception as e:
        logger.error(f"Error executing accessibility interaction: {e}", exc_info=True)
        return {"ok": False, "error": f"Accessibility action error: {str(e)}"}


async def _linux_interact(cached: Dict[str, Any], action: str, text: Optional[str]) -> Dict[str, Any]:
    """Execute action on Linux via AT-SPI2 action interface, xdotool, or PyAutoGUI."""
    from tools.desktop.controller import get_pyautogui, has_gui_display
    if not has_gui_display():
        return {
            "ok": False,
            "error": "No graphical display detected (neither DISPLAY nor WAYLAND_DISPLAY is set). You are in a headless Linux session.",
            "is_headless": True
        }

    atspi_obj = cached.get("atspi_obj")
    bounds = cached.get("bounds", [0, 0, 0, 0])
    name = cached.get("name", "element")
    x11_id = cached.get("x11_id")

    # 1. Attempt headless AT-SPI2 action if available
    if atspi_obj:
        try:
            if action == "click":
                act = atspi_obj.queryAction()
                if act and act.nActions > 0:
                    act.doAction(0)
                    return {"ok": True, "action": "click", "method": "AT-SPI2 doAction (headless)", "element": name}
            elif action == "type" and text:
                edt = atspi_obj.queryEditableText()
                if edt:
                    edt.setTextContents(str(text))
                    return {"ok": True, "action": "type", "method": "AT-SPI2 EditableText (headless)", "text": text}
        except Exception as e:
            logger.debug(f"Headless AT-SPI action fallback to physical: {e}")

    # 2. Attempt xdotool on X11 if available
    if bounds and len(bounds) == 4 and bounds[2] > 0 and bounds[3] > 0:
        cx = bounds[0] + bounds[2] // 2
        cy = bounds[1] + bounds[3] // 2

        try:
            import subprocess
            if action == "click":
                res = subprocess.run(["xdotool", "mousemove", str(cx), str(cy), "click", "1"], capture_output=True, timeout=3)
                if res.returncode == 0:
                    return {"ok": True, "action": "click", "method": f"xdotool click at ({cx}, {cy})", "element": name}
            elif action == "type" and text:
                res1 = subprocess.run(["xdotool", "mousemove", str(cx), str(cy), "click", "1"], capture_output=True, timeout=3)
                res2 = subprocess.run(["xdotool", "type", "--delay", "10", str(text)], capture_output=True, timeout=5)
                if res1.returncode == 0 and res2.returncode == 0:
                    return {"ok": True, "action": "type", "method": f"xdotool typing at ({cx}, {cy})", "text": text}
        except Exception:
            pass

        # 3. Fallback to PyAutoGUI
        try:
            pag = get_pyautogui()
            if pag:
                if action == "click":
                    pag.click(cx, cy)
                    return {"ok": True, "action": "click", "method": f"physical click at ({cx}, {cy})", "element": name}
                elif action == "type" and text:
                    pag.click(cx, cy)
                    pag.typewrite(str(text), interval=0.01)
                    return {"ok": True, "action": "type", "method": f"click + physical typing at ({cx}, {cy})", "text": text}
        except Exception as pag_err:
            return {"ok": False, "error": f"Physical input execution failed: {pag_err}"}

    return {"ok": False, "error": f"Element '{name}' has invalid bounds for interaction."}

