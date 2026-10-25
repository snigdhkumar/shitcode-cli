"""Filesystem and Precision Code Editing Package for ShitCode.
Exports file reading, writing, diff patching, atomic multi-patching, and directory listing tools.
"""

from __future__ import annotations

from tools.filesystem.view import read_file, list_dir
from tools.filesystem.edit import write_file, patch_file, patch, multi_patch_file

__all__ = [
    "read_file",
    "write_file",
    "patch_file",
    "patch",
    "multi_patch_file",
    "list_dir",
]
