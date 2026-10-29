"""State models and tool registry definitions for ShitCode CLI."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import time
from typing import Any, Callable, Dict, Optional

# Tools categorized as modifying the system (requiring confirmation in --ask-permission mode)
MODIFYING_TOOLS = {
    "terminal",
    "execute_code",
    "write_file",
    "patch_file",
    "patch",
    "multi_patch_file",
    "skill_manage",
    "process_manage",
    "browser_open",
    "browser_click",
    "browser_type",
    "browser_actions",
    "browser_close",
    "computer",
    "computer_actions",
    "window_focus",
    "window_state",
    "clipboard_write",
}

# Dynamically load registered tools
TOOLS_MAP: Dict[str, Callable[..., Any]] = {}
try:
    from tools import ALL_TOOLS
    for fn in ALL_TOOLS:
        if callable(fn):
            TOOLS_MAP[fn.__name__] = fn
except Exception as _load_err:
    import logging
    logging.getLogger("shitcode.core.models").warning(f"Error loading tools: {_load_err}")


@dataclass
class ClientState:
    device_name: str = "Local PC"
    user_email: str = "user"
    session_id: str = "initializing"
    workspace_dir: str = "."
    ask_permission: bool = False
    is_running: bool = True
    start_time: float = field(default_factory=time.time)
    ws: Optional[Any] = None
    is_prompting_permission: bool = False
    pending_perm_future: Optional[asyncio.Future[str]] = None
    pending_line_future: Optional[asyncio.Future[str]] = None
    recently_changed_fields: set[str] = field(default_factory=set)
    active_prompt: Optional[str] = None
    pending_workspace_target: Optional[str] = None
    reconnect_with_new_token: Optional[str] = None
    newer_version_available: Optional[str] = None
    expanded_request_view: bool = False
    last_ai_request: Optional[Dict[str, Any]] = None
    request_history: list[Dict[str, Any]] = field(default_factory=list)
