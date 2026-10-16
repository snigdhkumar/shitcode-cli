"""On-demand lazy installer for Playwright and Chromium in ShitCode CLI.
Installs Playwright browser binaries self-contained inside shitcode-cli/.browsers/
to keep the host system AppData/system directories 100% clean and portable.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

CLI_ROOT = Path(__file__).resolve().parent.parent
BROWSERS_DIR = CLI_ROOT / ".browsers"

# Always ensure Playwright stores browsers in the self-contained CLI folder
if "PLAYWRIGHT_BROWSERS_PATH" not in os.environ:
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(BROWSERS_DIR)


def is_playwright_installed() -> bool:
    """Check if playwright Python package is importable."""
    try:
        import playwright
        return True
    except ImportError:
        return False


def get_playwright_browsers_dir() -> Path:
    """Return the self-contained browser directory inside shitcode-cli/.browsers/."""
    custom_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if custom_path:
        return Path(custom_path)
    return BROWSERS_DIR


def get_expected_chromium_revisions() -> Dict[str, str]:
    """Inspect Playwright's internal browsers.json to get exact required revisions."""
    if not is_playwright_installed():
        return {}
    try:
        import playwright
        pkg_dir = Path(playwright.__file__).parent
        for candidate in [
            pkg_dir / "driver" / "package" / "browsers.json",
            pkg_dir / "driver" / "browsers.json",
        ]:
            if candidate.exists():
                data = json.loads(candidate.read_text(encoding="utf-8"))
                revs: Dict[str, str] = {}
                for b in data.get("browsers", []):
                    name = b.get("name")
                    rev = b.get("revision")
                    if name in ("chromium", "chromium-headless-shell") and rev:
                        revs[name] = str(rev)
                return revs
    except Exception:
        pass
    return {}


def is_chromium_installed() -> bool:
    """Check if Chromium binaries matching current Playwright version exist in CLI .browsers."""
    browsers_dir = get_playwright_browsers_dir()
    if not browsers_dir.exists():
        return False

    expected = get_expected_chromium_revisions()
    if expected:
        chromium_rev = expected.get("chromium")
        if chromium_rev:
            folder = browsers_dir / f"chromium-{chromium_rev}"
            if not folder.exists():
                return False
            if not (folder / "INSTALLATION_COMPLETE").exists():
                has_exe = any(folder.rglob("chrome.exe")) if sys.platform == "win32" else any(folder.rglob("chrome"))
                if not has_exe:
                    return False
            return True

    # Fallback heuristic if browsers.json was unreadable
    for folder in browsers_dir.glob("chromium-*"):
        if (folder / "INSTALLATION_COMPLETE").exists():
            return True
        if sys.platform == "win32":
            if any(folder.rglob("chrome.exe")):
                return True
        else:
            if any(folder.rglob("chrome")):
                return True
    return False


def is_browser_ready() -> bool:
    """Return True if both playwright package and exact chromium executables are installed."""
    return is_playwright_installed() and is_chromium_installed()


def ensure_browser_installed(interactive: bool = True, force: bool = False) -> Tuple[bool, str]:
    """Ensure playwright package and Chromium binaries are installed inside shitcode-cli/.browsers/.
    
    Streams live progress bars directly to the user's terminal window.
    """
    browsers_dir = get_playwright_browsers_dir()
    browsers_dir.mkdir(parents=True, exist_ok=True)
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers_dir)

    if not force and is_browser_ready():
        return True, "Browser engine is ready."

    print(f"\n{'='*64}", flush=True)
    print("  [*] ShitCode Browser Engine: Initializing Self-Contained Setup", flush=True)
    print(f"  [*] Destination: {browsers_dir}", flush=True)
    print(f"{'='*64}\n", flush=True)

    # 1. Install playwright package if missing
    if not is_playwright_installed():
        print("  -> Installing playwright Python package...", flush=True)
        try:
            cmd = [sys.executable, "-m", "pip", "install", "playwright"]
            proc = subprocess.Popen(cmd)
            ret = proc.wait()
            if ret != 0:
                return False, "Failed to install playwright package via pip."
        except Exception as e:
            return False, f"Error launching pip install playwright: {e}"

    # 2. Download Chromium & Headless Shell binaries with live terminal streaming
    if force or not is_chromium_installed():
        print("  -> Downloading automated Chromium binaries into shitcode-cli/.browsers/...", flush=True)
        print("     (Live download progress is streaming below)\n", flush=True)
        try:
            env = os.environ.copy()
            env["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers_dir)
            cmd = [sys.executable, "-m", "playwright", "install", "chromium", "chromium-headless-shell"]
            proc = subprocess.Popen(cmd, env=env)
            ret = proc.wait()
            if ret != 0:
                # Fallback to general chromium install
                cmd_fallback = [sys.executable, "-m", "playwright", "install", "chromium"]
                proc = subprocess.Popen(cmd_fallback, env=env)
                ret = proc.wait()
                if ret != 0:
                    return False, f"Failed to download Chromium into {browsers_dir}."
        except Exception as e:
            return False, f"Error launching playwright install: {e}"

    print(f"\n[OK] Browser engine ready in {browsers_dir}.\n", flush=True)
    return True, f"Chromium browser engine ready in {browsers_dir}."
