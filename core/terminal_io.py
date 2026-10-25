"""Cross-platform console I/O, raw terminal input, and clipboard handling."""

from __future__ import annotations

import os
import sys
import time
from typing import Any


def clear_screen():
    """Clear terminal screen cross-platform (ANSI escape sequence with system fallback)."""
    if sys.platform == "win32":
        os.system("cls")
    else:
        # Standard ANSI escape to clear entire screen and reset cursor to home (1,1)
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()
        try:
            os.system("clear")
        except Exception:
            pass


def get_clipboard_text() -> str:
    """Retrieve text from system clipboard using Win32 API, Linux xclip/wl-paste/xsel, macOS pbpaste, or Tkinter."""
    if sys.platform == "win32":
        try:
            import ctypes
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            user32.OpenClipboard.argtypes = [ctypes.c_void_p]
            user32.OpenClipboard.restype = ctypes.c_bool
            user32.GetClipboardData.argtypes = [ctypes.c_uint]
            user32.GetClipboardData.restype = ctypes.c_void_p
            user32.CloseClipboard.argtypes = []
            user32.CloseClipboard.restype = ctypes.c_bool
            kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
            kernel32.GlobalLock.restype = ctypes.c_void_p
            kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
            kernel32.GlobalUnlock.restype = ctypes.c_bool

            if user32.OpenClipboard(None):
                try:
                    h_data = user32.GetClipboardData(13)  # CF_UNICODETEXT
                    if h_data:
                        p_data = kernel32.GlobalLock(h_data)
                        if p_data:
                            try:
                                text = ctypes.c_wchar_p(p_data).value
                                return text or ""
                            finally:
                                kernel32.GlobalUnlock(h_data)
                finally:
                    user32.CloseClipboard()
        except Exception:
            pass
    elif sys.platform.startswith("linux"):
        import shutil
        import subprocess
        # 1. Wayland
        if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-paste"):
            try:
                res = subprocess.run(["wl-paste", "--no-newline"], capture_output=True, text=True, timeout=0.5)
                if res.returncode == 0 and res.stdout:
                    return res.stdout
            except Exception:
                pass
        # 2. X11 xclip
        if shutil.which("xclip"):
            try:
                res = subprocess.run(["xclip", "-selection", "clipboard", "-o"], capture_output=True, text=True, timeout=0.5)
                if res.returncode == 0 and res.stdout:
                    return res.stdout
            except Exception:
                pass
        # 3. X11 xsel
        if shutil.which("xsel"):
            try:
                res = subprocess.run(["xsel", "--clipboard", "--output"], capture_output=True, text=True, timeout=0.5)
                if res.returncode == 0 and res.stdout:
                    return res.stdout
            except Exception:
                pass
    elif sys.platform.darwin:
        import subprocess
        try:
            res = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=0.5)
            if res.returncode == 0 and res.stdout:
                return res.stdout
        except Exception:
            pass

    # Universal GUI Tkinter fallback (only if display server is available on non-Windows)
    if sys.platform != "win32" and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return ""

    try:
        import tkinter
        r = tkinter.Tk()
        r.withdraw()
        text = r.clipboard_get()
        r.destroy()
        return text or ""
    except Exception:
        return ""


def read_console_line(state: Any) -> tuple[str, bool]:
    """Read a line of text or detect an immediate ESC keypress from console.
    Returns: (text, is_escape)
    - If user pressed physical ESC key (ASCII 27): returns ("", True)
    - If user pressed Enter: returns (text, False)
    """
    if sys.platform == "win32" and sys.stdin.isatty():
        import msvcrt
        buf: list[str] = []
        while state.is_running:
            if msvcrt.kbhit():
                ch = msvcrt.getwch()
                if ch == "\x1b":  # Physical ESC key pressed
                    sys.stdout.write("\n")
                    sys.stdout.flush()
                    return ("", True)
                elif ch in ("\r", "\n"):  # Enter pressed
                    sys.stdout.write("\n")
                    sys.stdout.flush()
                    return ("".join(buf), False)
                elif ch in ("\x08", "\x7f"):  # Backspace
                    if buf:
                        buf.pop()
                        sys.stdout.write("\b \b")
                        sys.stdout.flush()
                elif ch == "\x16":  # Ctrl+V paste
                    clip_text = get_clipboard_text()
                    if clip_text:
                        clean_paste = clip_text.replace("\r\n", " ").replace("\n", " ")
                        buf.extend(list(clean_paste))
                        sys.stdout.write(clean_paste)
                        sys.stdout.flush()
                elif ch == "\x0f":  # Ctrl+O (toggle enlarged AI request view)
                    sys.stdout.write("\n")
                    sys.stdout.flush()
                    return ("__CTRL_O__", False)
                elif ch == "\x03":  # Ctrl+C
                    raise KeyboardInterrupt
                elif ch in ("\x00", "\xe0"):  # Extended key prefix (arrows, function keys)
                    msvcrt.getwch()  # Consume second scan code
                elif ch.isprintable():
                    buf.append(ch)
                    sys.stdout.write(ch)
                    sys.stdout.flush()
            else:
                time.sleep(0.04)
        return ("", False)
    elif sys.platform != "win32" and sys.stdin.isatty():
        import termios
        import tty
        import select
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        buf = []
        try:
            tty.setcbreak(fd)
            while state.is_running:
                r, _, _ = select.select([sys.stdin], [], [], 0.05)
                if r:
                    ch = sys.stdin.read(1)
                    if ch == "\x1b":
                        r2, _, _ = select.select([sys.stdin], [], [], 0.03)
                        if r2:
                            # Discard full extended ANSI escape sequence (arrows, function keys, delete, etc.)
                            while True:
                                seq_char = sys.stdin.read(1)
                                if seq_char.isalpha() or seq_char == "~" or not seq_char:
                                    break
                                r_extra, _, _ = select.select([sys.stdin], [], [], 0.01)
                                if not r_extra:
                                    break
                        else:
                            sys.stdout.write("\n")
                            sys.stdout.flush()
                            return ("", True)
                    elif ch in ("\r", "\n"):
                        sys.stdout.write("\n")
                        sys.stdout.flush()
                        return ("".join(buf), False)
                    elif ch in ("\x7f", "\x08"):  # Backspace
                        if buf:
                            buf.pop()
                            sys.stdout.write("\b \b")
                            sys.stdout.flush()
                    elif ch == "\x16":  # Ctrl+V paste
                        clip_text = get_clipboard_text()
                        if clip_text:
                            clean_paste = clip_text.replace("\r\n", " ").replace("\n", " ")
                            buf.extend(list(clean_paste))
                            sys.stdout.write(clean_paste)
                            sys.stdout.flush()
                    elif ch == "\x0f":  # Ctrl+O (toggle enlarged AI request view)
                        sys.stdout.write("\n")
                        sys.stdout.flush()
                        return ("__CTRL_O__", False)
                    elif ch == "\x03":  # Ctrl+C
                        raise KeyboardInterrupt
                    elif ch.isprintable():
                        buf.append(ch)
                        sys.stdout.write(ch)
                        sys.stdout.flush()
            return ("", False)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    else:
        # Fallback for non-tty (pipes, automated unittests, background subshells)
        try:
            line = sys.stdin.readline()
            if not line:
                return ("", False)
            raw = line.strip()
            if raw == "\x1b" or raw.lower() in ("esc", "escape"):
                return ("", True)
            if raw in ("\x0f", "__CTRL_O__", "ctrl+o", "expand"):
                return ("__CTRL_O__", False)
            return (raw, False)
        except Exception:
            return ("", False)
