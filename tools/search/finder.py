"""Glob filename discovery and unified search router for ShitCode.
"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Optional

from core.reporter import with_error_reporting
from tools.search.grep import IGNORED_DIRS, grep_search


@with_error_reporting("find_files")
def find_files(pattern: str, path: str = ".", max_results: int = 100) -> str:
    """Find files matching a glob pattern across the directory tree.

    Args:
        pattern: Glob pattern to match against filenames (e.g. '*.py', '*config*.json', 'test_*.ts').
        path: Root directory to search within (default current directory).
        max_results: Maximum file paths to return (default 100).
    """
    root_path = Path(path).resolve()
    if not root_path.exists():
        return f"Error: Path not found: {path}"

    matched_paths = []

    for current_root, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]

        for file in files:
            if fnmatch.fnmatch(file, pattern):
                rel_path = (Path(current_root) / file).relative_to(root_path)
                matched_paths.append(str(rel_path).replace("\\", "/"))
                if len(matched_paths) >= max_results:
                    break
        if len(matched_paths) >= max_results:
            break

    if not matched_paths:
        return f"No files matching '{pattern}' found under '{path}'."

    header = f"Found {len(matched_paths)} file(s) matching '{pattern}':\n"
    footer = f"\n[Capped at {max_results} files]" if len(matched_paths) >= max_results else ""
    return header + "\n".join(f"• {p}" for p in matched_paths) + footer


# Backward-compatible search_files from SNITRIX
@with_error_reporting("search_files")
def search_files(
    pattern: Optional[str] = None,
    query: Optional[str] = None,
    target: str = "content",
    path: str = ".",
) -> str:
    """Search for text patterns or filenames across the workspace (SNITRIX compatibility).

    Args:
        pattern: Pattern to search for (or query).
        query: Alias for pattern.
        target: 'content' (search file content), 'path' (search filenames/paths), or 'fuzzy'.
        path: Root directory to search within.
    """
    search_term = pattern if pattern is not None else query
    if not search_term:
        return "Error: 'pattern' (or 'query') parameter is required for search_files."
    if target in ("path", "filename", "file"):
        return find_files(pattern=search_term, path=path)
    return grep_search(query=search_term, path=path)
