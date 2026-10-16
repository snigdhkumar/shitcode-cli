"""On-demand lazy installer for Playwright and Chromium in ShitCode CLI.
Keeps repository and shitcode.zip ultralight (~40 KB) by only installing when requested.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Tuple


def is_playwright_installed() -> bool:
    """Check if playwright Python package is importable."""
    try:
        import playwright
        return True
    except ImportError:
        return False


def get_playwright_browsers_dir() -> Path:
    """Return the default system cache directory where Playwright installs browsers."""
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "ms-playwright"
        return Path.home() / "AppData" / "Local" / "ms-playwright"
    else:
        return Path.home() / ".cache" / "ms-playwright"


def is_chromium_installed() -> bool:
    """Check if Chromium binary exists in the Playwright cache."""
    browsers_dir = get_playwright_browsers_dir()
    if not browsers_dir.exists():
        return False
    # Look for chromium-* folders containing chrome.exe or chrome/chromium
    for folder in browsers_dir.glob("chromium-*"):
        if sys.platform == "win32":
            if (folder / "chrome-win" / "chrome.exe").exists() or (folder / "chrome-win64" / "chrome.exe").exists():
                return True
        else:
            if (folder / "chrome-linux" / "chrome").exists():
                return True
    return False


def is_browser_ready() -> bool:
    """Return True if both playwright package and chromium executable are installed."""
    return is_playwright_installed() and is_chromium_installed()


def ensure_browser_installed(interactive: bool = True) -> Tuple[bool, str]:
    """Ensure playwright package and Chromium binary are installed on the local system.
    
    Downloads directly into the user's OS cache, keeping the git repository clean.
    """
    if is_browser_ready():
        return True, "Browser engine is ready."

    print("\n[*] Initializing browser engine (one-time local setup)...", flush=True)

    # 1. Install playwright package if missing
    if not is_playwright_installed():
        print("  -> Installing playwright Python package...", flush=True)
        try:
            cmd = [sys.executable, "-m", "pip", "install", "playwright"]
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            if proc.returncode != 0:
                err = proc.stderr.strip() or proc.stdout.strip()
                return False, f"Failed to install playwright package: {err}"
        except Exception as e:
            return False, f"Error launching pip install playwright: {e}"

    # 2. Download Chromium binary to OS cache if missing
    if not is_chromium_installed():
        print("  -> Downloading automated Chromium browser binary...", flush=True)
        try:
            cmd = [sys.executable, "-m", "playwright", "install", "chromium"]
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            if proc.returncode != 0:
                err = proc.stderr.strip() or proc.stdout.strip()
                return False, f"Failed to download Chromium binary: {err}"
        except Exception as e:
            return False, f"Error launching playwright install chromium: {e}"

    print("[✓] Browser engine ready (Chromium installed in OS cache).\n", flush=True)
    return True, "Chromium browser engine ready."
