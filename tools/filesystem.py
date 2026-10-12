"""Filesystem and precision code editing tools for MCP_NEW.
Implements line-numbered file viewing, safe writes, unified diff patching,
atomic multi-patching (from Antigravity), and structured directory listing.
"""

from __future__ import annotations

import difflib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

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


@with_error_reporting("write_file")
def write_file(path: str, content: str) -> str:
    """Create or overwrite a file with automatic directory creation and UTF-8 encoding.

    Args:
        path: Path to the file to create or overwrite.
        content: The text content to write into the file.
    """
    file_path = Path(path).resolve()
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        line_count = len(content.splitlines())
        byte_count = len(content.encode("utf-8"))
        return f"Successfully wrote {line_count} lines ({byte_count} bytes) to '{path}'."
    except Exception as e:
        return f"Error writing file '{path}': {e}"


@with_error_reporting("patch_file")
def patch_file(
    path: str,
    old_string: Optional[str] = None,
    new_string: Optional[str] = None,
    old_str: Optional[str] = None,
    new_str: Optional[str] = None,
    old_text: Optional[str] = None,
    new_text: Optional[str] = None,
) -> str:
    """Perform exact search-and-replace modification on an existing file with unified diff verification.

    Args:
        path: Path to the file to edit.
        old_string: The exact existing text chunk to find and replace (or old_str/old_text).
        new_string: The new replacement text (or new_str/new_text).
    """
    target_old = old_string if old_string is not None else (old_str if old_str is not None else old_text)
    target_new = new_string if new_string is not None else (new_str if new_str is not None else new_text)

    if target_old is None or target_new is None:
        return "Error: Both 'old_string' (or 'old_str') and 'new_string' (or 'new_str') are required."

    file_path = Path(path).resolve()
    if not file_path.exists():
        return f"Error: File not found: {path}"
    if not file_path.is_file():
        return f"Error: Path is not a file: {path}"

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Error reading file '{path}': {e}"

    if target_old not in content:
        return (
            f"Error: Target text not found in '{path}'.\n"
            "Ensure the old_string matches the file content exactly, including whitespace and indentation."
        )

    count = content.count(target_old)
    if count > 1:
        return (
            f"Error: Target text appears {count} times in '{path}'.\n"
            "Please include more surrounding context lines in old_string to make the match unique."
        )

    # Perform replacement
    new_content = content.replace(target_old, target_new, 1)

    try:
        file_path.write_text(new_content, encoding="utf-8")
    except Exception as e:
        return f"Error writing patched content to '{path}': {e}"

    # Generate unified diff
    orig_lines = content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    diff = list(
        difflib.unified_diff(
            orig_lines,
            new_lines,
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
    )
    diff_text = "".join(diff)
    return f"Successfully patched '{path}'.\n\n```diff\n{diff_text}\n```"


# Alias for client backwards-compatibility
@with_error_reporting("patch")
def patch(
    path: str,
    old_string: Optional[str] = None,
    new_string: Optional[str] = None,
    old_str: Optional[str] = None,
    new_str: Optional[str] = None,
    old_text: Optional[str] = None,
    new_text: Optional[str] = None,
) -> str:
    """Alias for patch_file."""
    return patch_file(
        path=path,
        old_string=old_string,
        new_string=new_string,
        old_str=old_str,
        new_str=new_str,
        old_text=old_text,
        new_text=new_text,
    )


@with_error_reporting("multi_patch_file")
def multi_patch_file(
    path: str,
    replacements: Optional[List[Dict[str, str]]] = None,
    patches: Optional[List[Dict[str, str]]] = None,
) -> str:
    """Perform multiple non-contiguous search-and-replace edits atomically on a file (Antigravity-style).
    All replacement chunks are validated before applying any changes to prevent partial corruption.

    Args:
        path: Path to the target file.
        replacements: List of dicts, each with 'old_string' and 'new_string'.
        patches: Alias for replacements.
    """
    file_path = Path(path).resolve()
    if not file_path.exists():
        return f"Error: File not found: {path}"
    if not file_path.is_file():
        return f"Error: Path is not a file: {path}"

    target_replacements = replacements if replacements is not None else patches
    if not target_replacements or not isinstance(target_replacements, list):
        return "Error: 'replacements' (or 'patches') must be a non-empty list of {'old_string': '...', 'new_string': '...'}."

    try:
        original_content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Error reading file '{path}': {e}"

    # Pre-validation pass: verify all old_string targets exist and are uniquely identifiable
    current_content = original_content
    for idx, r in enumerate(target_replacements):
        old_s = r.get("old_string") or r.get("old_str") or r.get("old_text") or ""
        new_s = r.get("new_string") if "new_string" in r else (r.get("new_str") if "new_str" in r else r.get("new_text", ""))
        if not old_s:
            return f"Error in replacement #{idx + 1}: 'old_string' cannot be empty."

        if old_s not in current_content:
            return (
                f"Error in replacement #{idx + 1}: Target text not found in current content.\n"
                f"Snippet: {repr(old_s[:80])}"
            )
        if current_content.count(old_s) > 1:
            return (
                f"Error in replacement #{idx + 1}: Target text appears {current_content.count(old_s)} times.\n"
                f"Please include more surrounding context to disambiguate."
            )
        # Apply virtually
        current_content = current_content.replace(old_s, new_s, 1)

    # Write final atomically
    try:
        file_path.write_text(current_content, encoding="utf-8")
    except Exception as e:
        return f"Error saving multi-patched content to '{path}': {e}"

    # Generate unified diff
    orig_lines = original_content.splitlines(keepends=True)
    new_lines = current_content.splitlines(keepends=True)
    diff = list(
        difflib.unified_diff(
            orig_lines,
            new_lines,
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
    )
    diff_text = "".join(diff)
    return f"Successfully applied {len(replacements)} atomic patches to '{path}'.\n\n```diff\n{diff_text}\n```"


@with_error_reporting("list_dir")
def list_dir(path: str = ".", recursive: bool = False, max_depth: int = 2) -> str:
    """List directory contents with file sizes and type markers.

    Args:
        path: Directory path to list (default current directory).
        recursive: Whether to list subdirectories recursively (default False).
        max_depth: Maximum recursion depth when recursive=True (default 2).
    """
    root_path = Path(path).resolve()
    if not root_path.exists():
        return f"Error: Directory not found: {path}"
    if not root_path.is_dir():
        return f"Error: Path is a file, not a directory: {path}"

    lines = [f"Directory listing for: {root_path}"]

    def _format_size(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"

    def _walk(current: Path, depth: int, prefix: str = ""):
        if depth > max_depth:
            return
        try:
            entries = sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            lines.append(f"{prefix}└── [Permission Denied]")
            return

        for idx, entry in enumerate(entries):
            # Skip hidden and cache entries
            if entry.name.startswith((".", "__pycache__")):
                continue
            is_last = idx == len(entries) - 1
            connector = "└── " if is_last else "├── "
            sub_prefix = "    " if is_last else "│   "

            if entry.is_dir():
                lines.append(f"{prefix}{connector}[DIR] {entry.name}/")
                if recursive and depth < max_depth:
                    _walk(entry, depth + 1, prefix + sub_prefix)
            else:
                try:
                    size_str = _format_size(entry.stat().st_size)
                except Exception:
                    size_str = "unknown size"
                lines.append(f"{prefix}{connector}{entry.name} ({size_str})")

    _walk(root_path, depth=1)
    return "\n".join(lines)
