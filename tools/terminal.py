"""Terminal and background process execution tools for MCP_NEW.
Supports native Windows (PowerShell/CMD) and Linux (Bash/sh) execution.
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from core.reporter import with_error_reporting

logger = logging.getLogger("mcp_new.terminal")

ROOT_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = ROOT_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

_IS_WINDOWS = platform.system() == "Windows"
_CURRENT_WORKDIR: str = os.getcwd()
_WORKDIR_LOCK = threading.Lock()

# Background processes registry: {session_id: dict}
_BG_PROCESSES: Dict[str, Dict[str, Any]] = {}
_BG_LOCK = threading.Lock()


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
        # Crucial: Prevent Git Bash from converting flags like /IM or /F into C:/Program Files/Git/... paths
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

    cmd_stripped = command.strip()

    # Handle directory change (cd) tracking
    if cmd_stripped.startswith("cd ") and not background:
        target_dir = cmd_stripped[3:].strip().strip('"').strip("'")
        expanded = os.path.expanduser(target_dir)
        new_dir = os.path.abspath(os.path.join(effective_workdir, expanded))
        if os.path.isdir(new_dir):
            with _WORKDIR_LOCK:
                _CURRENT_WORKDIR = new_dir
            return f"Directory changed to: {new_dir}"
        else:
            return f"Error: Directory not found: {new_dir}"

    args = _get_shell_cmd(command)

    if background:
        # Launch background process detached
        session_id = f"bg_{int(time.time())}_{os.getpid()}_{len(_BG_PROCESSES) + 1}"
        log_path = LOGS_DIR / f"{session_id}.log"
        log_file = open(log_path, "w", encoding="utf-8", errors="replace")

        creation_flags = 0
        if _IS_WINDOWS:
            creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

        clean_env = _get_clean_env()

        proc = subprocess.Popen(
            args,
            cwd=effective_workdir,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            creationflags=creation_flags,
            env=clean_env,
            text=True,
        )

        with _BG_LOCK:
            _BG_PROCESSES[session_id] = {
                "proc": proc,
                "command": command,
                "workdir": effective_workdir,
                "log_file": str(log_path),
                "log_handle": log_file,
                "start_time": time.time(),
                "session_id": session_id,
            }

        return (
            f"Process started in background.\n"
            f"Session ID: {session_id}\n"
            f"PID: {proc.pid}\n"
            f"Logs: {log_path}\n"
            f"Use process_manage(action='poll' or 'log', session_id='{session_id}') to monitor."
        )

    # Foreground execution
    try:
        clean_env = _get_clean_env()
        proc = subprocess.run(
            args,
            cwd=effective_workdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=clean_env,
            timeout=timeout,
        )
        output = proc.stdout
        if proc.stderr:
            output += ("\n--- STDERR ---\n" if output else "") + proc.stderr
        
        status_line = f"\n[Exit code: {proc.returncode}]" if proc.returncode != 0 else ""
        return (output + status_line).strip() or "(Command executed with no output)"
    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds."
    except Exception as e:
        return f"Execution error: {e}"


@with_error_reporting("process_manage")
def process_manage(
    action: str,
    session_id: Optional[str] = None,
    signal: Optional[str] = None,
    timeout: Optional[int] = None,
) -> str:
    """Inspect, monitor, wait for, or terminate background processes.

    Args:
        action: Operation to perform: 'list', 'poll', 'log', 'wait', or 'kill'.
        session_id: Identifier of the background process or session.
        signal: Signal/action for kill ('TERM', 'KILL').
        timeout: Optional wait timeout in seconds.
    """
    with _BG_LOCK:
        if action == "list":
            if not _BG_PROCESSES:
                return "No background processes currently registered."
            lines = ["Active & recent background processes:"]
            for sid, info in _BG_PROCESSES.items():
                p = info["proc"]
                status = "Running" if p.poll() is None else f"Exited ({p.poll()})"
                elapsed = int(time.time() - info["start_time"])
                lines.append(f"• ID: {sid} | PID: {p.pid} | Status: {status} | Elapsed: {elapsed}s | Cmd: {info['command'][:60]}")
            return "\n".join(lines)

        if not session_id:
            return "Error: 'session_id' is required for action: " + action

        info = _BG_PROCESSES.get(session_id)
        if not info:
            return f"Error: Unknown session_id '{session_id}'."

        proc: subprocess.Popen = info["proc"]

        if action == "poll":
            code = proc.poll()
            if code is None:
                elapsed = int(time.time() - info["start_time"])
                return f"Process {session_id} (PID {proc.pid}) is RUNNING (elapsed: {elapsed}s)."
            return f"Process {session_id} (PID {proc.pid}) FINISHED with exit code {code}."

        if action == "log":
            log_path = Path(info["log_file"])
            if not log_path.exists():
                return "No log file found."
            try:
                content = log_path.read_text(encoding="utf-8", errors="replace")
                lines = content.splitlines()
                # Return last 100 lines
                tail = lines[-100:]
                return "\n".join(tail) or "(Log file is empty)"
            except Exception as e:
                return f"Error reading log: {e}"

        if action == "kill":
            if proc.poll() is not None:
                return f"Process {session_id} has already exited with code {proc.poll()}."
            try:
                proc.terminate()
                time.sleep(0.5)
                if proc.poll() is None:
                    proc.kill()
                return f"Process {session_id} (PID {proc.pid}) terminated."
            except Exception as e:
                return f"Error terminating process: {e}"

        if action == "wait":
            wait_time = timeout or 30
            try:
                code = proc.wait(timeout=wait_time)
                return f"Process {session_id} completed with exit code {code}."
            except subprocess.TimeoutExpired:
                return f"Process {session_id} is still running after {wait_time}s wait."

        return f"Unknown action: '{action}'. Available: list, poll, log, kill, wait."
