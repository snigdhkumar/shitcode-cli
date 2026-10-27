"""Glob filename discovery and unified search router for ShitCode.
"""

from __future__ import annotations

import fnmatch
import os
import time
from pathlib import Path
from typing import Optional

from core.reporter import with_error_reporting
from tools.search.grep import IGNORED_DIRS, grep_search


@with_error_reporting("find_files")
def find_files(
    pattern: str,
    path: str = ".",
    max_results: int = 100,
    timeout: float = 20.0,
    max_scanned: int = 10000,
) -> str:
    """Find files matching a glob pattern across the directory tree.

    Args:
        pattern: Glob pattern to match against filenames (e.g. '*.py', '*config*.json', 'test_*.ts').
        path: Root directory to search within (default current directory).
        max_results: Maximum file paths to return (default 100).
        timeout: Maximum seconds to search before returning partial results (default 20.0s).
        max_scanned: Maximum files to inspect before stopping (default 10000).
    """
    root_path = Path(path).resolve()
    if not root_path.exists():
        return f"Error: Path not found: {path}"

    start_time = time.perf_counter()
    matched_paths = []
    files_scanned = 0
    hit_cutoff = False
    cutoff_reason = ""

    for current_root, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]

        if (time.perf_counter() - start_time) > timeout:
            hit_cutoff = True
            cutoff_reason = f"reached {int(timeout)}s execution time limit"
            break

        for file in files:
            if (time.perf_counter() - start_time) > timeout:
                hit_cutoff = True
                cutoff_reason = f"reached {int(timeout)}s execution time limit"
                break
            if files_scanned >= max_scanned:
                hit_cutoff = True
                cutoff_reason = f"scanned {max_scanned} files limit"
                break

            files_scanned += 1
            if fnmatch.fnmatch(file, pattern):
                rel_path = (Path(current_root) / file).relative_to(root_path)
                matched_paths.append(str(rel_path).replace("\\", "/"))
                if len(matched_paths) >= max_results:
                    break
        if len(matched_paths) >= max_results or hit_cutoff:
            break

    elapsed_s = round(time.perf_counter() - start_time, 2)

    if not matched_paths:
        if hit_cutoff:
            return (
                f"No files matching '{pattern}' found before search halted ({cutoff_reason}, "
                f"inspected {files_scanned} files in {elapsed_s}s under '{path}').\n"
                f"Tip: Target a specific subfolder to narrow the search scope."
            )
        return f"No files matching '{pattern}' found across {files_scanned} file(s) in {elapsed_s}s under '{path}'."

    header = f"Found {len(matched_paths)} file(s) matching '{pattern}' ({elapsed_s}s):\n"
    footer = ""
    if len(matched_paths) >= max_results:
        footer = f"\n\n[Capped at {max_results} files; more may exist]"
    elif hit_cutoff:
        footer = f"\n\n[Note: Search halted early ({cutoff_reason}). Narrow path to see remaining files.]"

    return header + "\n".join(f"• {p}" for p in matched_paths) + footer


# Backward-compatible search_files from SNITRIX
@with_error_reporting("search_files")
def search_files(
    pattern: Optional[str] = None,
    query: Optional[str] = None,
    target: str = "content",
    path: str = ".",
    timeout: float = 20.0,
    **kwargs,
) -> str:
    """Search for text patterns or filenames across the workspace (SNITRIX compatibility).

    Args:
        pattern: Pattern to search for (or query).
        query: Alias for pattern.
        target: 'content' (search file content), 'path' (search filenames/paths), or 'fuzzy'.
        path: Root directory to search within.
        timeout: Maximum seconds to search before returning partial results (default 20.0s).
    """
    search_term = pattern if pattern is not None else query
    if not search_term:
        return "Error: 'pattern' (or 'query') parameter is required for search_files."
    if target in ("path", "filename", "file"):
        return find_files(pattern=search_term, path=path, timeout=timeout)
    return grep_search(query=search_term, path=path, timeout=timeout)
