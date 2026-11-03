"""Semantic Vocabulary & Node Models for Accessibility Engine.
Defines canonical roles, state flags, and structured element schemas.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set

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

INTERACTIVE_ROLES: Set[str] = {
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


def format_element_node(
    ref: str,
    role: str,
    name: str,
    value: str,
    bounds: List[int],
    actions: List[str],
) -> Dict[str, Any]:
    """Build standard structured node dictionary."""
    node = {
        "ref": ref,
        "role": role,
        "name": name,
        "bounds": bounds,
        "actions": actions,
    }
    if value:
        node["value"] = value
    return node
