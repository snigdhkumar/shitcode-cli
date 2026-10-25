"""Native shell command execution engine for ShitCode.
Supports Windows (PowerShell/CMD) and Linux (Bash/sh) with directory state memory.
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from core.reporter import with_error_reporting
from tools.terminal.process import LOGS_DIR, register_background_process

logger = logging.getLogger("mcp_new.terminal.shell")

_IS_WINDOWS = platform.system() == "Windows"
_CURRENT_WORKDIR: str = os.getcwd()
_WORKDIR_LOCK = threading.Lock()


def _get_shell_cmd(command: str) -> list[str]:
    """Return appropriate shell command list based on the operating system.
    On Windows: defaults to native PowerShell, or cmd.exe if explicitly requested.
    """
    if _IS_WINDOWS:
        cmd_lower = command.strip().lower()

        # Explicit CMD execution if command calls cmd or batch directives
        if cmd_lower.startswith(("cmd /c ", "cmd.exe /c ")):
            prefix_len = 7 if cmd_lower.startswith("cmd /c ") else 11
            return ["cmd.exe", "/c", command[prefix_len:].strip()]
        if cmd_lower.startswith(("cmd ", "cmd.exe ", "call ", "echo.", "cls")):
            return ["cmd.exe", "/c", command]

        # Explicit Bash execution only if the caller explicitly requests it
        if cmd_lower.startswith(("bash ", "bash.exe ", "sh ")):
            git_bash = Path(r"C:\Program Files\Git\bin\bash.exe")
            if git_bash.exists():
                return [str(git_bash), "-c", command]
            return ["bash", "-c", command]

        # Default shell on Windows is native PowerShell with ExecutionPolicy Bypass
        return [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
        ]
    else:
        shell = "/bin/bash" if os.path.exists("/bin/bash") else "/bin/sh"
        return [shell, "-c", command]


def _get_clean_env() -> dict:
    """Return environment dictionary with Git Bash path conversion disabled on Windows."""
    env = os.environ.copy()
    if _IS_WINDOWS:
        # Prevent Git Bash from converting flags like /IM or /F into C:/Program Files/Git/... paths
        env["MSYS_NO_PATHCONV"] = "1"
        env["MSYS2_ARG_CONV_EXCL"] = "*"
    return env


@with_error_reporting("terminal")
def terminal(
    command: str,
    background: bool = False,
    timeout: int = 120,
    workdir: Optional[str] = None,
) -> str:
    """Execute shell command on the host environment and return stdout, stderr, and exit code.

    Args:
        command: The shell command line to execute.
        background: Set to True to run long-lived processes in the background.
        timeout: Execution timeout in seconds (default 120).
        workdir: Working directory for this command execution.
    """
    global _CURRENT_WORKDIR

    with _WORKDIR_LOCK:
        effective_workdir = workdir or _CURRENT_WORKDIR
        if not os.path.isdir(effective_workdir):
            effective_workdir = os.getcwd()

    # Track directory changes (cd) explicitly
    trimmed = command.strip()
    if trimmed.startswith("cd ") or trimmed == "cd":
        parts = trimmed.split(maxsplit=1)
        if len(parts) == 1 or parts[1].strip() in ("~", ""):
            target_dir = os.path.expanduser("~")
        else:
            target_dir = parts[1].strip().strip("\"'")
            if not os.path.isabs(target_dir):
                target_dir = os.path.normpath(os.path.join(effective_workdir, target_dir))

        if os.path.isdir(target_dir):
            with _WORKDIR_LOCK:
                _CURRENT_WORKDIR = target_dir
            return f"Changed directory to: {_CURRENT_WORKDIR}"
        else:
            return f"Error: Directory not found: {target_dir}"

    shell_cmd = _get_shell_cmd(command)
    clean_env = _get_clean_env()

    # Background execution branch
    if background:
        session_id = f"proc_{int(time.time())}_{os.getpid()}"
        log_file = LOGS_DIR / f"{session_id}.log"
        try:
            out_handle = open(log_file, "w", encoding="utf-8")
            proc = subprocess.Popen(
                shell_cmd,
                cwd=effective_workdir,
                stdout=out_handle,
                stderr=subprocess.STDOUT,
                env=clean_env,
                shell=False,
            )
            register_background_process(session_id, proc, command, log_file)
            return (
                f"Started background process with ID '{session_id}' (PID {proc.pid}).\n"
                f"Working directory: {effective_workdir}\n"
                f"Log file: {log_file}\n"
                f"Use process_manage(action='poll', session_id='{session_id}') to check status."
            )
        except Exception as e:
            return f"Error starting background process: {e}"

    # Foreground synchronous execution
    try:
        proc = subprocess.run(
            shell_cmd,
            cwd=effective_workdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=clean_env,
            timeout=timeout,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
        )

        output = proc.stdout
        if proc.stderr:
            output += ("\n--- STDERR ---\n" if output else "") + proc.stderr

        if proc.returncode != 0:
            output += f"\n[Process exited with return code: {proc.returncode}]"

        return output.strip() or "(Command completed with no output)"

    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds."
    except Exception as e:
        return f"Execution error: {e}"
