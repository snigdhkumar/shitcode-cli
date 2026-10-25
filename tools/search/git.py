"""Git repository state inspection and diff summarization tools for ShitCode.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from core.reporter import with_error_reporting


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
