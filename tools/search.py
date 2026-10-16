"""Search and repository inspection tools for ShitCode.
Implements Antigravity-style regex/literal grep search with file inclusion filters,
glob filename discovery, and git status / working diff inspection.
"""

from __future__ import annotations

import fnmatch
import os
import re
import subprocess
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
                    # Truncate overly long lines
                    clean_line = line.strip()
                    if len(clean_line) > 200:
                        clean_line = clean_line[:200] + "..."
                    matches.append(f"{rel_path}:{line_no}: {clean_line}")
                    if len(matches) >= max_results:
                        break
            if len(matches) >= max_results:
                break
        if len(matches) >= max_results:
            break

    if not matches:
        return f"No matches found for '{search_term}' in {files_searched} files searched."

    header = f"Found {len(matches)} match(es) for '{search_term}' across {files_searched} file(s):\n"
    footer = f"\n\n[Showing first {max_results} results; more may exist]" if len(matches) >= max_results else ""
    return header + "\n".join(matches) + footer


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


@with_error_reporting("git_status")
def git_status(path: str = ".", diff: bool = True) -> str:
    """Inspect current git repository state: branch, staged/unstaged files, and summary diffs.

    Args:
        path: Path within the git repository (default current directory).
        diff: Whether to include short diff statistics (default True).
    """
    root_path = Path(path).resolve()
    if not (root_path / ".git").exists() and not Path(os.path.join(root_path, "..", ".git")).exists():
        # Check if git rev-parse works
        check = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(root_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if check.returncode != 0:
            return f"Notice: Directory '{path}' is not inside a git repository."

    res = subprocess.run(
        ["git", "status", "--short", "--branch"],
        cwd=str(root_path),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if res.returncode != 0:
        return f"Git error: {res.stderr.strip()}"

    status_out = res.stdout.strip()
    if not status_out:
        return "Git working directory is clean (nothing to commit)."

    output = f"Git Status:\n{status_out}"

    if diff:
        diff_res = subprocess.run(
            ["git", "diff", "--stat"],
            cwd=str(root_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if diff_res.stdout.strip():
            output += f"\n\nUnstaged Changes Summary:\n{diff_res.stdout.strip()}"

        staged_res = subprocess.run(
            ["git", "diff", "--cached", "--stat"],
            cwd=str(root_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if staged_res.stdout.strip():
            output += f"\n\nStaged Changes Summary:\n{staged_res.stdout.strip()}"

    return output
