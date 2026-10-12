"""Diagnostic error logger and incident reporter for MCP_NEW.
Captures tool execution failures and writes structured JSON reports into reports/.
"""

from __future__ import annotations

import functools
import inspect
import json
import logging
import os
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Union

logger = logging.getLogger("mcp_new.reporter")

ROOT_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_LOG = REPORTS_DIR / "error_history.log"


def _sanitize_args(args: tuple, kwargs: dict) -> Dict[str, Any]:
    """Sanitize arguments for error reports, masking common secret names."""
    sanitized: Dict[str, Any] = {}
    for i, a in enumerate(args):
        sanitized[f"arg_{i}"] = str(a)[:1000]

    for k, v in kwargs.items():
        if any(secret_term in k.lower() for secret_term in ("token", "secret", "password", "key", "auth")):
            sanitized[k] = "***REDACTED***"
        else:
            sanitized[k] = str(v)[:1000]
    return sanitized


def log_error_report(tool_name: str, exc: Union[Exception, str], args: tuple = (), kwargs: dict | None = None) -> str:
    """Record an error into reports/err_<timestamp>_<tool>.json and history log.
    Returns the incident ID.
    """
    kwargs = kwargs or {}
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%d_%H%M%S_%f")[:19]
    incident_id = f"err_{ts}_{tool_name}"
    report_file = REPORTS_DIR / f"{incident_id}.json"

    if isinstance(exc, Exception):
        exc_type = type(exc).__name__
        exc_msg = str(exc)
        tb = traceback.format_exc()
        if tb.strip() == "NoneType: None":
            tb = f"Captured exception without traceback: {exc_type}: {exc_msg}"
    else:
        exc_type = "ToolExecutionError"
        exc_msg = str(exc)
        tb = f"Error message reported by tool: {exc_msg}"

    report_payload = {
        "incident_id": incident_id,
        "timestamp_iso": now.isoformat(),
        "tool_name": tool_name,
        "arguments": _sanitize_args(args, kwargs),
        "exception_type": exc_type,
        "exception_message": exc_msg,
        "traceback": tb,
        "working_directory": os.getcwd(),
        "user": os.environ.get("USERNAME") or os.environ.get("USER") or "unknown",
    }

    try:
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report_payload, f, indent=2, ensure_ascii=False)
            f.write("\n")
    except Exception as io_err:
        logger.error(f"Failed to write error report {report_file}: {io_err}")

    try:
        with open(HISTORY_LOG, "a", encoding="utf-8") as log_f:
            log_f.write(f"[{now.isoformat()}] ID={incident_id} TOOL={tool_name} ERROR={exc_type}: {exc_msg}\n")
    except Exception:
        pass

    logger.error(f"Tool '{tool_name}' failed with {exc_type}: {exc_msg} (Report: {report_file.name})")
    return incident_id


def with_error_reporting(tool_name: str) -> Callable:
    """Decorator wrapping tool functions with automatic error interception and reporting."""
    def decorator(fn: Callable) -> Callable:
        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args, **kwargs) -> Any:
                try:
                    return await fn(*args, **kwargs)
                except Exception as exc:
                    inc_id = log_error_report(tool_name, exc, args, kwargs)
                    return json.dumps({
                        "status": "failed",
                        "error": str(exc),
                        "incident_id": inc_id,
                        "report": f"reports/{inc_id}.json",
                    }, indent=2)
            return async_wrapper
        else:
            @functools.wraps(fn)
            def sync_wrapper(*args, **kwargs) -> Any:
                try:
                    return fn(*args, **kwargs)
                except Exception as exc:
                    inc_id = log_error_report(tool_name, exc, args, kwargs)
                    return json.dumps({
                        "status": "failed",
                        "error": str(exc),
                        "incident_id": inc_id,
                        "report": f"reports/{inc_id}.json",
                    }, indent=2)
            return sync_wrapper
    return decorator
