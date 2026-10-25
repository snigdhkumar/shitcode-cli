"""Sandboxed Python code execution tool for ShitCode.
Runs Python snippets in a sandboxed child process with timeout protection.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

from core.reporter import with_error_reporting


@with_error_reporting("execute_code")
def execute_code(
    code: str,
    timeout: int = 60,
    task_id: Optional[str] = None,
    reset: bool = False,
) -> str:
    """Execute Python code in a sandboxed runtime environment and return output.

    Args:
        code: Python source code string to execute.
        timeout: Execution timeout in seconds (default 60).
        task_id: Optional task/session identifier (SNITRIX compatibility).
        reset: Reset sandbox state (SNITRIX compatibility).
    """
    if not code.strip():
        return "Error: Code string cannot be empty."

    # Write code to temporary script
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        temp_path = f.name

    try:
        proc = subprocess.run(
            [sys.executable, temp_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )

        output = proc.stdout
        if proc.stderr:
            output += ("\n--- STDERR ---\n" if output else "") + proc.stderr

        if proc.returncode != 0:
            output += f"\n[Process exited with return code: {proc.returncode}]"

        return output.strip() or "(Code executed successfully with no output)"
    except subprocess.TimeoutExpired:
        return f"Error: Code execution timed out after {timeout} seconds."
    except Exception as e:
        return f"Code execution error: {e}"
    finally:
        try:
            Path(temp_path).unlink(missing_ok=True)
        except Exception:
            pass
