"""Desktop System & Clipboard Services.
"""

from tools.desktop.system.clipboard import (
    clipboard_read,
    clipboard_write,
    copy_to_clipboard,
    paste_text_via_clipboard,
    read_from_clipboard,
)
from tools.desktop.system.telemetry import (
    get_system_metrics,
    system_info,
)

__all__ = [
    "clipboard_read",
    "clipboard_write",
    "copy_to_clipboard",
    "read_from_clipboard",
    "get_system_metrics",
    "system_info",
]
