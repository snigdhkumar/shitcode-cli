"""File viewing and structured directory inspection tools for ShitCode.
Implements 1-indexed line sliced reading and depth-controlled directory listing.
"""

from __future__ import annotations

import os
from pathlib import Path
from core.reporter import with_error_reporting


@with_error_reporting("read_file")
def read_file(path: str, offset: int = 1, limit: int = 200) -> str:
    """Read a slice of lines from a file with 1-indexed line numbers.

    Args:
        path: Path to the target file.
        offset: Line number to start reading from (1-indexed, default 1).
        limit: Maximum number of lines to return (default 200).
    """
    file_path = Path(path).resolve()
    if not file_path.exists():
        return f"Error: File not found: {path}"
    if not file_path.is_file():
        return f"Error: Path is a directory, not a file: {path}"

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Error reading file '{path}': {e}"

    lines = content.splitlines()
    total_lines = len(lines)

    if total_lines == 0:
        return "(File is empty)"

    start_idx = max(0, offset - 1)
    end_idx = min(total_lines, start_idx + limit)

    selected_lines = lines[start_idx:end_idx]

    output_lines = []
    for i, line in enumerate(selected_lines, start=start_idx + 1):
        output_lines.append(f"{i}: {line}")

    result = "\n".join(output_lines)
    header = f"File: {path} (Showing lines {start_idx + 1}-{end_idx} of {total_lines})\n"
    if end_idx < total_lines:
        footer = f"\n... [{total_lines - end_idx} more lines remaining]"
    else:
        footer = ""

    return header + result + footer


@with_error_reporting("list_dir")
def list_dir(path: str = ".", recursive: bool = False, max_depth: int = 2) -> str:
    """List directory contents with file sizes and type markers.

    Args:
        path: Target directory path (default current directory).
        recursive: Whether to list subdirectories recursively (default False).
        max_depth: Maximum recursion depth when recursive is True (default 2).
    """
    target = Path(path).resolve()
    if not target.exists():
        return f"Error: Directory not found: {path}"
    if not target.is_dir():
        return f"Error: Path is not a directory: {path}"

    entries = []
    ignored_patterns = {".git", "node_modules", "__pycache__", ".venv", "venv", ".idea", ".vscode"}

    def _scan(current: Path, depth: int):
        if depth > max_depth:
            return
        try:
            items = sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            for item in items:
                if item.name in ignored_patterns:
                    continue
                rel = item.relative_to(target)
                indent = "  " * (depth - 1)
                if item.is_dir():
                    entries.append(f"{indent}[DIR]  {rel.as_posix()}/")
                    if recursive:
                        _scan(item, depth + 1)
                else:
                    try:
                        sz = item.stat().st_size
                        if sz < 1024:
                            sz_str = f"{sz} B"
                        elif sz < 1024 * 1024:
                            sz_str = f"{sz / 1024:.1f} KB"
                        else:
                            sz_str = f"{sz / (1024 * 1024):.1f} MB"
                    except Exception:
                        sz_str = "? B"
                    entries.append(f"{indent}[FILE] {rel.as_posix()} ({sz_str})")
        except PermissionError:
            entries.append(f"{'  ' * (depth - 1)}[ACCESS DENIED] {current.name}/")

    _scan(target, depth=1)

    if not entries:
        return f"Directory '{path}' is empty."

    header = f"Contents of '{path}':\n"
    return header + "\n".join(entries[:300]) + (f"\n\n[Capped at 300 entries]" if len(entries) > 300 else "")
