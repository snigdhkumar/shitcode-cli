"""Background process lifecycle and monitoring management for ShitCode.
Allows inspecting, polling, tailing logs, and terminating long-running background tasks.
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from core.reporter import with_error_reporting

logger = logging.getLogger("mcp_new.terminal.process")

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
LOGS_DIR = ROOT_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Background processes registry: {session_id: dict}
BG_PROCESSES: Dict[str, Dict[str, Any]] = {}
BG_LOCK = threading.Lock()


def register_background_process(session_id: str, proc: subprocess.Popen, command: str, log_file: Path) -> None:
    """Register an active background process into the session registry."""
    with BG_LOCK:
        BG_PROCESSES[session_id] = {
            "proc": proc,
            "command": command,
            "start_time": time.time(),
            "log_file": str(log_file),
        }


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
    with BG_LOCK:
        if action == "list":
            if not BG_PROCESSES:
                return "No background processes currently registered."
            lines = ["Active & recent background processes:"]
            for sid, info in BG_PROCESSES.items():
                p = info["proc"]
                status = "Running" if p.poll() is None else f"Exited ({p.poll()})"
                elapsed = int(time.time() - info["start_time"])
                lines.append(f"• ID: {sid} | PID: {p.pid} | Status: {status} | Elapsed: {elapsed}s | Cmd: {info['command'][:60]}")
            return "\n".join(lines)

        if not session_id:
            return "Error: 'session_id' is required for action: " + action

        info = BG_PROCESSES.get(session_id)
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
