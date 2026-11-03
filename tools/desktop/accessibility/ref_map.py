"""RefMap & Qualified Snapshot Session Cache.
Tracks element handles, snapshot IDs, and validates stale ref mutations.
"""

from __future__ import annotations

import secrets
import time
from typing import Any, Dict, Optional, Tuple

_SNAPSHOT_CACHE: Dict[str, Dict[str, Any]] = {}
_CURRENT_SNAPSHOT_ID: str = ""
_LAST_SNAPSHOT_TIME: float = 0.0


def allocate_snapshot_id() -> str:
    """Generate a compact 8-char snapshot session hash (e.g. s8f3k2p9)."""
    global _CURRENT_SNAPSHOT_ID, _LAST_SNAPSHOT_TIME, _SNAPSHOT_CACHE
    _CURRENT_SNAPSHOT_ID = f"s{secrets.token_hex(3)}"
    _LAST_SNAPSHOT_TIME = time.time()
    _SNAPSHOT_CACHE.clear()
    return _CURRENT_SNAPSHOT_ID


def get_current_snapshot_id() -> str:
    """Get the active snapshot session ID."""
    global _CURRENT_SNAPSHOT_ID
    if not _CURRENT_SNAPSHOT_ID:
        allocate_snapshot_id()
    return _CURRENT_SNAPSHOT_ID


def register_ref(
    ref_idx: int,
    elem_handle: Any,
    hwnd: int,
    role: str,
    name: str,
    bounds: list,
    actions: list,
) -> str:
    """Register element into snapshot cache under both qualified (@snap:eN) and short (@eN) keys."""
    snap_id = get_current_snapshot_id()
    qualified_ref = f"@{snap_id}:e{ref_idx}"
    short_ref = f"@e{ref_idx}"

    entry = {
        "ref": qualified_ref,
        "element": elem_handle,
        "hwnd": hwnd,
        "role": role,
        "name": name,
        "bounds": bounds,
        "actions": actions,
        "snapshot_id": snap_id,
        "created_at": time.time(),
    }
    _SNAPSHOT_CACHE[qualified_ref] = entry
    _SNAPSHOT_CACHE[short_ref] = entry
    return qualified_ref


def resolve_ref(ref_str: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Resolve ref string to cached element entry with stale ref detection."""
    clean_ref = ref_str.strip()
    if clean_ref not in _SNAPSHOT_CACHE:
        return None, {
            "ok": False,
            "success": False,
            "error_code": "STALE_REF",
            "error": f"Element ref '{ref_str}' was not found in the active snapshot cache or has expired. Please run desktop_snapshot to get fresh element refs.",
        }

    entry = _SNAPSHOT_CACHE[clean_ref]
    return entry, None
