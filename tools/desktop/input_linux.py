"""Linux input forwarder for backward compatibility."""
from tools.desktop.input.linux_input import (
    LINUX_KEY_MAP,
    get_linux_display_server,
    has_gui_display,
    map_key_linux,
)

__all__ = [
    "LINUX_KEY_MAP",
    "get_linux_display_server",
    "has_gui_display",
    "map_key_linux",
]
