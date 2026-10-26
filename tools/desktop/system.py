"""System Performance & Hardware Resource Diagnostics for Windows and Linux.
Provides structured CPU, RAM, disk, and process telemetry via psutil.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

import psutil

logger = logging.getLogger("shitcode.tools.desktop.system")


def get_system_metrics() -> Dict[str, Any]:
    """Retrieve structured operating system health, load, memory, and top active processes."""
    try:
        vm = psutil.virtual_memory()
        cpu_pct = psutil.cpu_percent(interval=0.05)
        cpu_count = psutil.cpu_count(logical=True)

        disk_info: Dict[str, Any] = {}
        try:
            target_path = "C:\\" if os.name == "nt" else "/"
            du = psutil.disk_usage(target_path)
            disk_info = {
                "drive": target_path,
                "total_gb": round(du.total / (1024**3), 1),
                "free_gb": round(du.free / (1024**3), 1),
                "percent_used": du.percent,
            }
        except Exception as disk_err:
            disk_info = {"notice": str(disk_err)}

        top_procs: List[Dict[str, Any]] = []
        try:
            for p in sorted(
                psutil.process_iter(['pid', 'name', 'memory_info', 'cpu_percent']),
                key=lambda x: (x.info.get('memory_info').rss if x.info.get('memory_info') else 0),
                reverse=True,
            )[:6]:
                rss = p.info.get('memory_info').rss if p.info.get('memory_info') else 0
                top_procs.append({
                    "pid": p.info['pid'],
                    "name": p.info['name'],
                    "mem_mb": round(rss / (1024**2), 1),
                })
        except Exception:
            pass

        return {
            "success": True,
            "os": os.name,
            "cpu": {
                "percent": cpu_pct,
                "cores": cpu_count,
            },
            "ram": {
                "total_gb": round(vm.total / (1024**3), 1),
                "available_gb": round(vm.available / (1024**3), 1),
                "percent_used": vm.percent,
            },
            "disk": disk_info,
            "top_memory_processes": top_procs,
            "message": f"System status: CPU {cpu_pct}%, RAM {vm.percent}% used ({round(vm.available / (1024**3), 1)} GB free).",
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to retrieve system diagnostics: {e}"}
