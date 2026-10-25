"""Antigravity-style regex and literal grep search engine for ShitCode.
Provides line numbers, context snippets, glob inclusion filters, and automatic binary file pruning.
"""

from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path
from typing import List, Optional

from core.reporter import with_error_reporting

IGNORED_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".idea",
    ".vscode",
    "dist",
    "build",
    ".pytest_cache",
    ".next",
    ".nuxt",
}


@with_error_reporting("grep_search")
def grep_search(
    query: str = "",
    path: str = ".",
    is_regex: bool = False,
    case_insensitive: bool = False,
    includes: Optional[List[str]] = None,
    max_results: int = 100,
    pattern: Optional[str] = None,
) -> str:
    """Search for text patterns across files in a directory tree with line numbers and context snippets.

    Args:
        query: Search string or regular expression (or pattern).
        path: Root directory to search within (default current directory).
        is_regex: Treat query as regular expression (default False).
        case_insensitive: Perform case-insensitive search (default False).
        includes: List of glob patterns to filter files (e.g. ['*.py', '*.ts', '!**/tests/*']).
        max_results: Maximum matching lines to return (default 100).
        pattern: Alias for query.
    """
    search_term = query or pattern or ""
    if not search_term:
        return "Error: Search query/pattern cannot be empty."

    root_path = Path(path).resolve()
    if not root_path.exists():
        return f"Error: Path not found: {path}"

    flags = re.IGNORECASE if case_insensitive else 0
    try:
        regex_pattern = re.compile(search_term if is_regex else re.escape(search_term), flags)
    except re.error as e:
        return f"Invalid regex pattern: {e}"

    matches = []
    files_searched = 0

    for current_root, dirs, files in os.walk(root_path):
        # Prune ignored directories in-place
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]

        for file in files:
            file_path = Path(current_root) / file
            rel_path = file_path.relative_to(root_path)

            # Filter by includes patterns if provided
            if includes:
                matched_include = False
                for inc in includes:
                    if fnmatch.fnmatch(file_path.name, inc) or fnmatch.fnmatch(str(rel_path).replace("\\", "/"), inc):
                        matched_include = True
                        break
                if not matched_include:
                    continue

            # Skip common binary file extensions
            if file_path.suffix.lower() in {
                ".exe", ".dll", ".so", ".dylib", ".bin", ".pyc", ".png", ".jpg",
                ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".tar", ".gz", ".7z",
                ".mp4", ".mp3", ".wav", ".ttf", ".woff", ".woff2"
            }:
                continue

            files_searched += 1
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            for line_no, line in enumerate(content.splitlines(), start=1):
                if regex_pattern.search(line):
                    posix_rel = str(rel_path).replace("\\", "/")
                    trimmed = line.strip()
                    if len(trimmed) > 200:
                        trimmed = trimmed[:200] + "..."
                    matches.append(f"{posix_rel}:{line_no}: {trimmed}")
                    if len(matches) >= max_results:
                        break
            if len(matches) >= max_results:
                break
        if len(matches) >= max_results:
            break

    if not matches:
        return f"No matches found for '{search_term}' across {files_searched} file(s) in '{path}'."

    header = f"Found {len(matches)} match(es) for '{search_term}' across {files_searched} file(s):\n"
    footer = f"\n\n[Showing first {max_results} results; more may exist]" if len(matches) >= max_results else ""
    return header + "\n".join(matches) + footer
