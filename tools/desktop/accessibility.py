"""Accessibility forwarder for backward compatibility."""
from tools.desktop.accessibility import (
    capture_tree_snapshot,
    desktop_interact,
    desktop_snapshot,
    dispatch_element_action,
    resolve_ref,
)

__all__ = [
    "desktop_snapshot",
    "desktop_interact",
    "capture_tree_snapshot",
    "dispatch_element_action",
    "resolve_ref",
]
