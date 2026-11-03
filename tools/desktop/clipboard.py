"""Clipboard forwarder for backward compatibility."""
from tools.desktop.system.clipboard import (
    clipboard_read,
    clipboard_write,
    copy_to_clipboard,
    paste_text_via_clipboard,
    read_from_clipboard,
)

__all__ = [
    "clipboard_read",
    "clipboard_write",
    "copy_to_clipboard",
    "read_from_clipboard",
    "paste_text_via_clipboard",
]
