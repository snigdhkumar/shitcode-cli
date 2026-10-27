"""Antigravity-style regex and literal grep search engine for ShitCode.
Provides line numbers, context snippets, glob inclusion filters, automatic binary file pruning,
file size guardrails, and execution time limits.
"""

from __future__ import annotations

import fnmatch
import os
import re
import time
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
    ".cache",
    "cache",
    "site-packages",
    "AppData",
    "Local",
    "Roaming",
    "target",
    "vendor",
}

BINARY_EXTENSIONS = {
    ".exe", ".dll", ".so", ".dylib", ".bin", ".pyc", ".png", ".jpg",
    ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".tar", ".gz", ".7z",
    ".mp4", ".mp3", ".wav", ".ttf", ".woff", ".woff2", ".iso", ".img",
    ".dmg", ".msi", ".pkg", ".apk", ".jar", ".war", ".class", ".o",
    ".obj", ".a", ".lib", ".whl", ".sqlite", ".sqlite3", ".db", ".mdb",
    ".bak", ".vmdk", ".vdi", ".qcow2", ".xz", ".bz2", ".rar", ".webm",
    ".mov", ".avi", ".mkv", ".flac", ".ogg", ".eot", ".otf"
}

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


@with_error_reporting("grep_search")
def grep_search(
    query: str = "",
    path: str = ".",
    is_regex: bool = False,
    case_insensitive: bool = False,
    includes: Optional[List[str]] = None,
    max_results: int = 100,
    pattern: Optional[str] = None,
    timeout: float = 20.0,
    max_files: int = 5000,
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
        timeout: Maximum seconds to search before returning partial results (default 20.0s).
        max_files: Maximum files to inspect before stopping (default 5000).
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

    start_time = time.perf_counter()
    matches = []
    files_searched = 0
    hit_cutoff = False
    cutoff_reason = ""

    for current_root, dirs, files in os.walk(root_path):
        # Prune ignored directories in-place to avoid deep traversal
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]

        # Timeout check before processing folder files
        if (time.perf_counter() - start_time) > timeout:
            hit_cutoff = True
            cutoff_reason = f"reached {int(timeout)}s execution time limit"
            break

        for file in files:
            if (time.perf_counter() - start_time) > timeout:
                hit_cutoff = True
                cutoff_reason = f"reached {int(timeout)}s execution time limit"
                break
            if files_searched >= max_files:
                hit_cutoff = True
                cutoff_reason = f"scanned {max_files} files limit"
                break

            file_path = Path(current_root) / file

            # Fast suffix check
            if file_path.suffix.lower() in BINARY_EXTENSIONS:
                continue

            rel_path = file_path.relative_to(root_path)

            # Filter by includes patterns if provided
            if includes:
                matched_include = False
                posix_rel = str(rel_path).replace("\\", "/")
                for inc in includes:
                    if fnmatch.fnmatch(file_path.name, inc) or fnmatch.fnmatch(posix_rel, inc):
                        matched_include = True
                        break
                if not matched_include:
                    continue

            # Skip oversized files to prevent memory exhaustion
            try:
                if file_path.stat().st_size > MAX_FILE_SIZE_BYTES:
                    continue
            except Exception:
                continue

            # Fast binary sniffing on first 512 bytes
            try:
                with open(file_path, "rb") as bf:
                    if b"\x00" in bf.read(512):
                        continue
            except Exception:
                continue

            files_searched += 1

            # Line-by-line stream reading
            try:
                posix_rel = str(rel_path).replace("\\", "/")
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    for line_no, line in enumerate(f, start=1):
                        if regex_pattern.search(line):
                            trimmed = line.strip()
                            if len(trimmed) > 200:
                                trimmed = trimmed[:200] + "..."
                            matches.append(f"{posix_rel}:{line_no}: {trimmed}")
                            if len(matches) >= max_results:
                                break
            except Exception:
                continue

            if len(matches) >= max_results:
                break

        if len(matches) >= max_results or hit_cutoff:
            break

    elapsed_s = round(time.perf_counter() - start_time, 2)

    if not matches:
        if hit_cutoff:
            return (
                f"No matches found for '{search_term}' before search was halted ({cutoff_reason}, "
                f"inspected {files_searched} files in {elapsed_s}s under '{path}').\n"
                f"Tip: Target a specific subfolder or use includes=['*.txt'] to narrow the search scope."
            )
        return f"No matches found for '{search_term}' across {files_searched} file(s) in {elapsed_s}s under '{path}'."

    header = f"Found {len(matches)} match(es) for '{search_term}' across {files_searched} file(s) ({elapsed_s}s):\n"
    footer = ""
    if len(matches) >= max_results:
        footer = f"\n\n[Showing first {max_results} results; more may exist]"
    elif hit_cutoff:
        footer = f"\n\n[Note: Search halted early ({cutoff_reason}). Narrow path or use includes to see remaining files.]"

    return header + "\n".join(matches) + footer
