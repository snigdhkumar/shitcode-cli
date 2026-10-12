"""Tool Aggregator and Registry for ShitCode.
Registers all 17 high-performance coding agent tools onto MCPServer.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable, List

from tools.terminal import terminal, process_manage
from tools.filesystem import read_file, write_file, patch_file, patch, multi_patch_file, list_dir
from tools.search import grep_search, find_files, search_files, git_status
from tools.execution import execute_code
from tools.scraping import web_extract
from tools.skills import skills_list, skill_view, skill_manage

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

logger = logging.getLogger("mcp_new.tools")

ALL_TOOLS: List[Callable[..., Any]] = [
    # Terminal & Process Control
    terminal,
    process_manage,
    # Filesystem & Precision Editing
    read_file,
    write_file,
    patch_file,
    patch,
    multi_patch_file,
    list_dir,
    # Search & Repo Inspection
    grep_search,
    find_files,
    search_files,
    git_status,
    # Code Execution & Scraping
    execute_code,
    web_extract,
    # Self-Improving Skills
    skills_list,
    skill_view,
    skill_manage,
]


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
            raise
    logger.info(f"Registered {len(registered_names)} tools on MCPServer.")
    return registered_names
