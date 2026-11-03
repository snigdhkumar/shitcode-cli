"""Native Accessibility Pattern Implementations.
Invokes UIAutomation patterns directly on element COM handles.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger("shitcode.tools.desktop.accessibility.actions")

UIA_INVOKE_PATTERN_ID = 10000
UIA_VALUE_PATTERN_ID = 10002
UIA_SELECTION_ITEM_PATTERN_ID = 10010
UIA_TOGGLE_PATTERN_ID = 10015
UIA_EXPAND_COLLAPSE_PATTERN_ID = 10005


def perform_invoke(elem: Any) -> bool:
    """Trigger InvokePattern on element."""
    try:
        pat = elem.GetCurrentPattern(UIA_INVOKE_PATTERN_ID)
        if pat:
            import comtypes.gen.UIAutomationClient as uia_client
            inv = pat.QueryInterface(uia_client.IUIAutomationInvokePattern)
            inv.Invoke()
            return True
    except Exception as e:
        logger.debug(f"InvokePattern failed: {e}")
    return False


def perform_value(elem: Any, value: str) -> bool:
    """Set text value via ValuePattern."""
    try:
        pat = elem.GetCurrentPattern(UIA_VALUE_PATTERN_ID)
        if pat:
            import comtypes.gen.UIAutomationClient as uia_client
            val_pat = pat.QueryInterface(uia_client.IUIAutomationValuePattern)
            val_pat.SetValue(value)
            return True
    except Exception as e:
        logger.debug(f"ValuePattern failed: {e}")
    return False


def perform_toggle(elem: Any) -> bool:
    """Toggle element state via TogglePattern."""
    try:
        pat = elem.GetCurrentPattern(UIA_TOGGLE_PATTERN_ID)
        if pat:
            import comtypes.gen.UIAutomationClient as uia_client
            tog = pat.QueryInterface(uia_client.IUIAutomationTogglePattern)
            tog.Toggle()
            return True
    except Exception as e:
        logger.debug(f"TogglePattern failed: {e}")
    return False


def perform_select(elem: Any) -> bool:
    """Select element via SelectionItemPattern."""
    try:
        pat = elem.GetCurrentPattern(UIA_SELECTION_ITEM_PATTERN_ID)
        if pat:
            import comtypes.gen.UIAutomationClient as uia_client
            sel = pat.QueryInterface(uia_client.IUIAutomationSelectionItemPattern)
            sel.Select()
            return True
    except Exception as e:
        logger.debug(f"SelectionItemPattern failed: {e}")
    return False


def perform_focus(elem: Any) -> bool:
    """Set keyboard focus to element."""
    try:
        elem.SetFocus()
        return True
    except Exception as e:
        logger.debug(f"SetFocus failed: {e}")
    return False
