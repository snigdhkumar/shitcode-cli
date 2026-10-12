"""Configuration management for ShitCode Local Client."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("shitcode.config")

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT_DIR / "config.json"


def get_fallback_workspace() -> str:
    """Return a clean user workspace path outside of the client source directory."""
    projects_dir = Path.home() / "Projects"
    if projects_dir.exists():
        return str(projects_dir)
    return str(Path.home())


DEFAULT_CONFIG: Dict[str, Any] = {
    "client_token": "",
    "device_token": "",
    "workspace_dir": "",
    "ask_permission": False,
    "terminal": {
        "timeout": 120,
        "default_shell": "auto",  # auto, powershell, cmd, bash
    },
    "scraping": {
        "char_limit": 50000,
    },
}


def is_internal_client_path(path: str | Path) -> bool:
    """Check if a given path is the ShitCode client source folder itself."""
    try:
        resolved = Path(path).resolve()
        client_root = ROOT_DIR.resolve()
        # Direct match or subfolder of client
        if resolved == client_root or client_root in resolved.parents:
            return True
        # Check for signature files of client directory
        if (resolved / "shitcode_client.py").exists() and (resolved / "tools").is_dir():
            return True
    except Exception:
        pass
    return False


def load_config() -> Dict[str, Any]:
    """Load configuration from config.json, falling back to defaults."""
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            merged = DEFAULT_CONFIG.copy()
            merged.update(data)
            # Sync client_token and device_token
            c_tok = merged.get("client_token") or merged.get("device_token") or ""
            merged["client_token"] = c_tok
            merged["device_token"] = c_tok
            return merged
    except Exception as e:
        logger.warning(f"Failed to read {CONFIG_FILE}: {e}, using defaults.")
        return DEFAULT_CONFIG.copy()


def save_config(cfg: Dict[str, Any]) -> None:
    """Save configuration dictionary to config.json."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
            f.write("\n")
    except Exception as e:
        logger.error(f"Failed to save {CONFIG_FILE}: {e}")


def reset_device_token() -> None:
    """Clear saved client token from config.json."""
    cfg = load_config()
    cfg["client_token"] = ""
    cfg["device_token"] = ""
    save_config(cfg)


reset_client_token = reset_device_token


def set_device_token(new_token: str) -> None:
    """Persist client token into config.json."""
    cfg = load_config()
    tok_clean = str(new_token).strip()
    cfg["client_token"] = tok_clean
    cfg["device_token"] = tok_clean
    save_config(cfg)


set_client_token = set_device_token


def set_workspace_dir(new_path: str) -> None:
    """Persist new workspace directory into config.json."""
    cfg = load_config()
    cfg["workspace_dir"] = str(Path(new_path).resolve())
    save_config(cfg)


def set_ask_permission(enabled: bool) -> None:
    """Persist ask_permission setting into config.json."""
    cfg = load_config()
    cfg["ask_permission"] = bool(enabled)
    save_config(cfg)
