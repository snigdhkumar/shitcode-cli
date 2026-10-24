"""On-demand lazy installer for FFmpeg in ShitCode CLI.
Ensures a static universal FFmpeg binary is available on Windows and Linux
without requiring manual user installation or external package managers.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

CLI_ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = CLI_ROOT / ".bin"
FFMPEG_DIR = BIN_DIR / "ffmpeg"


def get_existing_ffmpeg_path() -> Optional[str]:
    """Check if FFmpeg executable exists on system PATH, local CLI bin, or imageio-ffmpeg."""
    # 1. System PATH
    sys_path = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if sys_path:
        return sys_path

    # 2. Local self-contained CLI bin directory
    bin_exe = FFMPEG_DIR / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
    if bin_exe.is_file() and os.access(str(bin_exe), os.X_OK):
        return str(bin_exe)

    # 3. imageio-ffmpeg Python wheel package
    try:
        import imageio_ffmpeg
        pkg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        if pkg_exe and Path(pkg_exe).is_file():
            return str(pkg_exe)
    except Exception:
        pass

    return None


def is_ffmpeg_ready() -> bool:
    """Return True if a working FFmpeg binary is found."""
    exe = get_existing_ffmpeg_path()
    if not exe:
        return False
    try:
        proc = subprocess.run([exe, "-version"], capture_output=True, text=True, timeout=5)
        return proc.returncode == 0
    except Exception:
        return False


def ensure_ffmpeg_installed() -> Tuple[bool, str, bool]:
    """Ensure FFmpeg is installed and runnable on the local machine.
    
    Returns:
        (success: bool, path_or_error: str, was_freshly_installed: bool)
    """
    existing = get_existing_ffmpeg_path()
    if existing:
        return True, existing, False

    print(f"\n{'='*64}", flush=True)
    print("  [*] ShitCode Video Engine: Initializing Universal FFmpeg Setup", flush=True)
    print("  [*] Downloading on-demand static FFmpeg binaries (Windows/Linux)...", flush=True)
    print(f"{'='*64}\n", flush=True)

    # 1. Install imageio-ffmpeg package (contains precompiled static binaries for all OS)
    print("  -> Provisioning universal static FFmpeg binary...", flush=True)
    try:
        cmd = [sys.executable, "-m", "pip", "install", "-q", "imageio-ffmpeg"]
        proc = subprocess.Popen(cmd)
        ret = proc.wait()
        if ret == 0:
            import imageio_ffmpeg
            exe = imageio_ffmpeg.get_ffmpeg_exe()
            if exe and Path(exe).is_file():
                # Make a convenient link/copy in shitcode-cli/.bin/ffmpeg/
                try:
                    FFMPEG_DIR.mkdir(parents=True, exist_ok=True)
                    dest = FFMPEG_DIR / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
                    if not dest.exists():
                        shutil.copy2(exe, dest)
                        if sys.platform != "win32":
                            dest.chmod(0o755)
                        exe = str(dest)
                except Exception:
                    pass

                print(f"[OK] FFmpeg video engine ready: {exe}\n", flush=True)
                return True, exe, True
    except Exception as e:
        print(f"  [!] Pip installation notice: {e}", flush=True)

    # Re-check if it became available
    re_check = get_existing_ffmpeg_path()
    if re_check:
        print(f"[OK] FFmpeg video engine ready: {re_check}\n", flush=True)
        return True, re_check, True

    return False, "Failed to provision FFmpeg binary automatically. Please install FFmpeg on your system PATH.", False
