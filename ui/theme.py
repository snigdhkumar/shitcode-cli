"""ANSI Color & Style Constants (Gemini / Modern CLI style)."""

import os
import sys

# ANSI Color & Style Constants
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
ORANGE = "\033[38;5;208m"
AMBER = "\033[38;5;214m"
GREEN = "\033[38;5;35m"
RED = "\033[38;5;196m"
CYAN = "\033[38;5;45m"
YELLOW = "\033[38;5;220m"
GRAY = "\033[38;5;244m"


def init_terminal():
    """Initialize Windows virtual terminal processing and UTF-8 encoding."""
    if sys.platform == "win32":
        os.system("")
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
