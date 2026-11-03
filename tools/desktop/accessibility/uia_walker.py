"""Windows UIAutomation Tree Walker with Web Wrapper Pruning.
Walks IUIAutomation ControlView and skips transparent Chromium/Electron wrapper nodes.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from tools.desktop.accessibility.models import (
    INTERACTIVE_ROLES,
    WIN_CONTROL_TYPE_NAMES,
    format_element_node,
)
from tools.desktop.accessibility.ref_map import register_ref

logger = logging.getLogger("shitcode.tools.desktop.accessibility.uia_walker")

WRAPPER_CONTROL_TYPES: Set[int] = {50026, 50025, 50033}  # Group, Custom, Pane


def is_chromium_root(elem: Any) -> bool:
    """Detect if root window has Chromium/Electron provenance."""
    try:
        cls_name = getattr(elem, "CurrentClassName", "")
        return cls_name == "Chrome_WidgetWin_1"
    except Exception:
        return False


def is_web_wrapper(elem: Any) -> bool:
    """Whether element is a transparent web container that consumes no logical depth."""
    try:
        ctype = getattr(elem, "CurrentControlType", 0)
        if ctype not in WRAPPER_CONTROL_TYPES:
            return False
        name = (getattr(elem, "CurrentName", "") or "").strip()
        auto_id = (getattr(elem, "CurrentAutomationId", "") or "").strip()
        return not name and not auto_id
    except Exception:
        return False


def extract_node_facts(elem: Any, elem_idx: int, hwnd: int) -> Optional[Dict[str, Any]]:
    """Read element attributes and register into snapshot cache."""
    try:
        name = (getattr(elem, "CurrentName", "") or "").strip()
        ctype = getattr(elem, "CurrentControlType", 0)
        role = WIN_CONTROL_TYPE_NAMES.get(ctype, "custom")

        # Skip invisible or zero-rect elements
        rect = getattr(elem, "CurrentBoundingRectangle", None)
        if not rect:
            return None
        w = rect.right - rect.left
        h = rect.bottom - rect.top
        if w <= 0 or h <= 0:
            return None

        # Determine available actions
        actions = ["focus"]
        if role in INTERACTIVE_ROLES:
            actions.append("click")
        if role in ("edit", "combobox"):
            actions.append("type")
        if role in ("checkbox", "radiobutton"):
            actions.append("toggle")

        bounds = [rect.left, rect.top, w, h]
        ref = register_ref(elem_idx, elem, hwnd, role, name, bounds, actions)
        return format_element_node(ref, role, name, "", bounds, actions)
    except Exception:
        return None


def walk_uia_tree(
    walker: Any,
    root_elem: Any,
    hwnd: int,
    interactive_only: bool = True,
    max_elements: int = 60,
    max_depth: int = 8,
) -> List[Dict[str, Any]]:
    """Walk UIA tree with Chromium settle and transparent container depth bypass."""
    elements: List[Dict[str, Any]] = []
    elem_idx = 1
    is_chrom = is_chromium_root(root_elem)
    if is_chrom:
        time.sleep(0.04)  # Brief settle buffer to activate sleepy Chromium accessibility tree

    def _traverse(node: Any, current_depth: int):
        nonlocal elem_idx
        if len(elements) >= max_elements or current_depth > max_depth:
            return

        child = None
        try:
            child = walker.GetFirstChildElement(node)
        except Exception:
            return

        while child is not None and len(elements) < max_elements:
            wrapper = is_chrom and is_web_wrapper(child)
            next_depth = current_depth if wrapper else current_depth + 1

            facts = extract_node_facts(child, elem_idx, hwnd)
            if facts:
                is_interactive = facts["role"] in INTERACTIVE_ROLES
                if not interactive_only or is_interactive:
                    elements.append(facts)
                    elem_idx += 1

            if next_depth <= max_depth:
                _traverse(child, next_depth)

            try:
                child = walker.GetNextSiblingElement(child)
            except Exception:
                break

    _traverse(root_elem, 0)
    return elements
