"""Tool Aggregator and Registry for ShitCode.
Registers all 34 high-performance autonomous coding, browser, multimodal, and computer control tools onto MCPServer.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable, List

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

logger = logging.getLogger("shitcode.tools")

ALL_TOOLS: List[Callable[..., Any]] = []


def _register(fn: Any):
    if callable(fn) and fn not in ALL_TOOLS:
        ALL_TOOLS.append(fn)


# 1. Terminal & Process Control
try:
    from tools.terminal import terminal, process_manage
    _register(terminal)
    _register(process_manage)
except Exception as e:
    logger.warning(f"Failed to load terminal tools: {e}")

# 2. Filesystem & Precision Editing
try:
    from tools.filesystem import read_file, write_file, patch_file, patch, multi_patch_file, list_dir
    _register(read_file)
    _register(write_file)
    _register(patch_file)
    _register(patch)
    _register(multi_patch_file)
    _register(list_dir)
except Exception as e:
    logger.warning(f"Failed to load filesystem tools: {e}")

# 3. Search & Repo Inspection
try:
    from tools.search import grep_search, find_files, search_files, git_status
    _register(grep_search)
    _register(find_files)
    _register(search_files)
    _register(git_status)
except Exception as e:
    logger.warning(f"Failed to load search tools: {e}")

# 4. Code Execution & Scraping
try:
    from tools.execution import execute_code
    from tools.scraping import web_extract
    _register(execute_code)
    _register(web_extract)
except Exception as e:
    logger.warning(f"Failed to load execution/scraping tools: {e}")

# 5. Self-Improving Skills
try:
    from tools.skills import skills_list, skill_view, skill_manage
    _register(skills_list)
    _register(skill_view)
    _register(skill_manage)
except Exception as e:
    logger.warning(f"Failed to load skills tools: {e}")

# 6. Browser Automation (Playwright)
try:
    from tools.browser import (
        browser_open,
        browser_click,
        browser_type,
        browser_extract,
        browser_screenshot,
        browser_actions,
        browser_close,
    )
    _register(browser_open)
    _register(browser_click)
    _register(browser_type)
    _register(browser_extract)
    _register(browser_screenshot)
    _register(browser_actions)
    _register(browser_close)
except Exception as e:
    logger.warning(f"Failed to load browser tools: {e}")

# 7. Multimodal Vision & Video Engine
try:
    from tools.media import image_inspect, video_inspect
    _register(image_inspect)
    _register(video_inspect)
except Exception as e:
    logger.warning(f"Failed to load media tools: {e}")

# 8. Desktop & Computer Control Automation
try:
    from tools.desktop import (
        computer,
        computer_actions,
        windows_list,
        window_focus,
        window_state,
        clipboard_write,
        clipboard_read,
        system_info,
    )
    _register(computer)
    _register(computer_actions)
    _register(windows_list)
    _register(window_focus)
    _register(window_state)
    _register(clipboard_write)
    _register(clipboard_read)
    _register(system_info)
except Exception as e:
    logger.warning(f"Failed to load desktop tools: {e}")


def register_all_tools(server: MCPServer) -> List[str]:
    """Register all modular coding agent tools onto the given MCPServer instance.

    Returns:
        List of registered tool names.
    """
    registered_names: List[str] = []
    for tool_fn in ALL_TOOLS:
        try:
            server.add_tool(tool_fn)
            registered_names.append(tool_fn.__name__)
        except Exception as e:
            logger.error(f"Failed to register tool '{tool_fn.__name__}': {e}")
    logger.info(f"Registered {len(registered_names)} tools on MCPServer.")
    return registered_names
