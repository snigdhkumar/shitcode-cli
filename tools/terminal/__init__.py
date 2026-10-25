"""Terminal and Process Management Package for ShitCode.
Exports native shell command execution and background process monitoring tools.
"""

from __future__ import annotations

from tools.terminal.shell import terminal
from tools.terminal.process import process_manage

__all__ = ["terminal", "process_manage"]
