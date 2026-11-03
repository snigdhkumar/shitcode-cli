"""Native OS Accessibility Engine for ShitCode.
Provides token-efficient UI element discovery (snapshots) and headless element actions.
"""

from typing import Any, Dict, Optional

from tools.desktop.accessibility.dispatch import dispatch_element_action
from tools.desktop.accessibility.ref_map import resolve_ref
from tools.desktop.accessibility.tree_walker import capture_tree_snapshot


async def desktop_snapshot(
    app_name: Optional[str] = None,
    window_id: Optional[str | int] = None,
    interactive_only: bool = True,
    max_elements: int = 60,
) -> Dict[str, Any]:
    """Inspect the native OS accessibility tree of a window.
    Returns compact controls with qualified refs (@snap:e1) for headless interaction.
    """
    return await capture_tree_snapshot(
        app_name=app_name,
        window_id=window_id,
        interactive_only=interactive_only,
        max_elements=max_elements,
    )


async def desktop_interact(
    ref: str,
    action: str = "click",
    value: str = "",
    **kwargs: Any,
) -> Dict[str, Any]:
    """Execute a semantic or coordinate fallback action on an element by its ref."""
    entry, err = resolve_ref(ref)
    if err:
        return err

    return dispatch_element_action(
        entry=entry,
        action=action,
        value=value or kwargs.get("text", ""),
    )


__all__ = [
    "desktop_snapshot",
    "desktop_interact",
    "capture_tree_snapshot",
    "dispatch_element_action",
    "resolve_ref",
]
