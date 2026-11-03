"""Linux AT-SPI2 D-Bus Tree Walker.
Walks accessible desktop hierarchy via pyatspi or accessible D-Bus interfaces.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from tools.desktop.accessibility.models import (
    INTERACTIVE_ROLES,
    LINUX_ROLE_NAMES,
    format_element_node,
)
from tools.desktop.accessibility.ref_map import register_ref

logger = logging.getLogger("shitcode.tools.desktop.accessibility.atspi_walker")


def walk_atspi_tree(
    root_accessible: Any,
    interactive_only: bool = True,
    max_elements: int = 60,
    max_depth: int = 8,
) -> List[Dict[str, Any]]:
    """Recursively walk AT-SPI accessibility tree on Linux."""
    elements: List[Dict[str, Any]] = []
    elem_idx = 1

    def _traverse(node: Any, depth: int):
        nonlocal elem_idx
        if len(elements) >= max_elements or depth > max_depth:
            return

        try:
            child_count = node.childCount
        except Exception:
            return

        for i in range(child_count):
            if len(elements) >= max_elements:
                break
            try:
                child = node.getChildAtIndex(i)
                if not child:
                    continue

                role_raw = child.getRoleName()
                role = LINUX_ROLE_NAMES.get(role_raw, role_raw.lower())
                name = (child.name or "").strip()

                bounds = [0, 0, 0, 0]
                try:
                    comp = child.queryComponent()
                    # 0 = DESKTOP coordinate type in pyatspi
                    bbox = comp.getExtents(0)
                    bounds = [bbox.x, bbox.y, bbox.width, bbox.height]
                except Exception:
                    pass

                actions = ["focus"]
                if role in INTERACTIVE_ROLES:
                    actions.append("click")
                if role in ("edit", "entry"):
                    actions.append("type")
                if role in ("checkbox", "radiobutton"):
                    actions.append("toggle")

                is_interactive = role in INTERACTIVE_ROLES
                if not interactive_only or is_interactive:
                    ref = register_ref(elem_idx, child, 0, role, name, bounds, actions)
                    elements.append(format_element_node(ref, role, name, "", bounds, actions))
                    elem_idx += 1

                _traverse(child, depth + 1)
            except Exception:
                continue

    _traverse(root_accessible, 0)
    return elements
