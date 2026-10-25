"""Interactive console command dispatching and handler routines."""

from __future__ import annotations

import asyncio
import inspect
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from core.config import is_internal_client_path, load_config
from core.terminal_io import clear_screen
from core.updater import execute_update_routine
from ui.theme import AMBER, BOLD, CYAN, DIM, GREEN, ORANGE, RED, RESET, YELLOW
from ui.views import print_banner


def _get_tools_map(tools_map: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Retrieve active tools mapping or dynamically fetch from shitcode module."""
    if tools_map is not None:
        return tools_map
    for mod_name in ("shitcode", "shitcode_client"):
        try:
            mod = sys.modules.get(mod_name) or __import__(mod_name)
            mapping = getattr(mod, "TOOLS_MAP", None)
            if mapping is not None:
                return mapping
        except Exception:
            pass
    try:
        from core.models import TOOLS_MAP
        return TOOLS_MAP
    except Exception:
        return {}


def _run_update_routine(skip_prompt: bool = True) -> bool:
    """Execute update routine honoring mock patches on shitcode."""
    for mod_name in ("shitcode", "shitcode_client"):
        try:
            mod = sys.modules.get(mod_name) or __import__(mod_name)
            fn = getattr(mod, "execute_update_routine", None)
            if fn is not None:
                return fn(skip_prompt=skip_prompt)
        except Exception:
            pass
    return execute_update_routine(skip_prompt=skip_prompt)


def handle_interactive_help():
    """Print available interactive terminal commands."""
    print(f"""
{ORANGE}╭─ Interactive Terminal Commands ────────────────────────────────────────╮{RESET}
{ORANGE}│{RESET}  {BOLD}update [-y]{RESET}      {DIM}Update ShitCode CLI to the latest version via Git    {RESET}{ORANGE}│{RESET}
{ORANGE}│{RESET}  {BOLD}workspace <path>{RESET} {DIM}Switch project folder live without restarting        {RESET}{ORANGE}│{RESET}
{ORANGE}│{RESET}  {BOLD}perm{RESET}             {DIM}Toggle between Auto-Approve & Interactive Approval    {RESET}{ORANGE}│{RESET}
{ORANGE}│{RESET}  {BOLD}expand / Ctrl+O{RESET}  {DIM}Toggle Enlarged/Compact AI request details            {RESET}{ORANGE}│{RESET}
{ORANGE}│{RESET}  {BOLD}browser <cmd>{RESET}    {DIM}Browser automation (open, close, status, install)    {RESET}{ORANGE}│{RESET}
{ORANGE}│{RESET}  {BOLD}status{RESET}           {DIM}View live connection uptime, session ID, & ping      {RESET}{ORANGE}│{RESET}
{ORANGE}│{RESET}  {BOLD}tools{RESET}            {DIM}List all available tools & dynamic descriptions       {RESET}{ORANGE}│{RESET}
{ORANGE}│{RESET}  {BOLD}clear{RESET}            {DIM}Clear console screen and re-render status banner      {RESET}{ORANGE}│{RESET}
{ORANGE}│{RESET}  {BOLD}token{RESET}            {DIM}View masked active device token                       {RESET}{ORANGE}│{RESET}
{ORANGE}│{RESET}  {BOLD}reset / reset token{RESET} {DIM}Reset active device token & configure a new device {RESET}{ORANGE}│{RESET}
{ORANGE}│{RESET}  {BOLD}help / ?{RESET}         {DIM}Show this cheat sheet                                 {RESET}{ORANGE}│{RESET}
{ORANGE}│{RESET}  {BOLD}quit / exit{RESET}      {DIM}Safely disconnect and exit client                     {RESET}{ORANGE}│{RESET}
{ORANGE}╰────────────────────────────────────────────────────────────────────────╯{RESET}
  {DIM}Type any command above, or press ESC (or 'clear') to return to banner.{RESET}
  {DIM}Tip: You can also update the token directly in config.json inside the client folder.{RESET}
""")


def handle_interactive_status(state: Any, tools_map: Optional[Dict[str, Any]] = None):
    """Display connection status, uptime, session info."""
    active_tools = _get_tools_map(tools_map)
    uptime_sec = int(time.time() - getattr(state, "start_time", time.time()))
    mins, secs = divmod(uptime_sec, 60)
    hrs, mins = divmod(mins, 60)
    uptime_str = f"{hrs}h {mins}m {secs}s" if hrs else f"{mins}m {secs}s"
    auth_email = getattr(state, "user_email", "user") or "user"
    device_name = getattr(state, "device_name", "Local PC")
    session_id = getattr(state, "session_id", "unknown")
    workspace_dir = getattr(state, "workspace_dir", ".")
    ask_perm = getattr(state, "ask_permission", False)
    req_view = "Enlarged (Ctrl+O)" if getattr(state, "expanded_request_view", False) else "Compact (Ctrl+O to enlarge)"

    print(f"""
{CYAN}╭─ Client Status ────────────────────────────────────────────────────────╮{RESET}
{CYAN}│{RESET}  ● Status:     {GREEN}ONLINE{RESET} {DIM}(Authenticated as "{auth_email}" '{device_name}'){RESET}
{CYAN}│{RESET}  Session ID:   {session_id:<55}{CYAN}│{RESET}
{CYAN}│{RESET}  Workspace:    {workspace_dir:<55}{CYAN}│{RESET}
{CYAN}│{RESET}  Security:     {"Interactive Approval" if ask_perm else "Auto-Approve":<55}{CYAN}│{RESET}
{CYAN}│{RESET}  Request View: {req_view:<55}{CYAN}│{RESET}
{CYAN}│{RESET}  Uptime:       {uptime_str:<55}{CYAN}│{RESET}
{CYAN}│{RESET}  Active Tools: {len(active_tools):<55}{CYAN}│{RESET}
{CYAN}╰────────────────────────────────────────────────────────────────────────╯{RESET}
  {DIM}Type any command, or press ESC (or 'clear') to return to banner.{RESET}
""")


def handle_interactive_tools(tools_map: Optional[Dict[str, Any]] = None):
    """Dynamically display all registered tools."""
    active_tools = _get_tools_map(tools_map)
    print(f"\n{BOLD}{ORANGE}● Active Coding Agent Tools ({len(active_tools)} registered):{RESET}")
    for name, fn in sorted(active_tools.items()):
        doc = inspect.getdoc(fn) or "No description"
        first_line = doc.splitlines()[0]
        mod = getattr(fn, "__module__", "tool").split(".")[-1]
        print(f"  {CYAN}{name:<18}{RESET} {DIM}[{mod}]{RESET} {first_line[:65]}")
    print(f"  {DIM}Type any command, or press ESC (or 'clear') to return to banner.{RESET}\n")


def handle_interactive_browser(arg: str):
    """Handle interactive browser commands (open, close, status, install)."""
    subparts = arg.strip().split(maxsplit=1)
    subcmd = subparts[0].lower() if subparts else "status"
    subarg = subparts[1].strip() if len(subparts) > 1 else ""

    try:
        from core.browser_installer import is_browser_ready, is_playwright_installed, is_chromium_installed, ensure_browser_installed
        from tools.browser import BrowserManager
    except ImportError as e:
        print(f"\n{RED}[!] Browser module error: {e}{RESET}\n")
        return

    mgr = BrowserManager.get_instance()

    if subcmd in ("status", "info"):
        from core.browser_installer import get_playwright_browsers_dir
        from tools.browser import PROFILE_DIR
        ready = is_browser_ready()
        pw_ok = is_playwright_installed()
        cr_ok = is_chromium_installed()
        active = mgr.is_active()
        browsers_dir = get_playwright_browsers_dir()
        profile_exists = PROFILE_DIR.exists() and any(PROFILE_DIR.iterdir()) if PROFILE_DIR.exists() else False

        ready_str = f"{GREEN}Installed & Ready{RESET}" if ready else f"{YELLOW}Not Installed (Run 'browser install'){RESET}"
        active_str = f"{GREEN}Active Tab ({mgr._page.url}){RESET}" if (active and mgr._page) else f"{DIM}Inactive{RESET}"
        mode_str = f"{CYAN}Headless (VPS/Background){RESET}" if mgr._is_headless else f"{CYAN}Headed (Visible Window){RESET}"
        profile_str = f"{GREEN}Saved logins/cookies present{RESET}" if profile_exists else f"{DIM}Fresh profile{RESET}"

        pw_str = f"{GREEN}[✓]{RESET} playwright" if pw_ok else f"{RED}[x]{RESET} playwright {RED}(missing){RESET}"
        cr_str = f"{GREEN}[✓]{RESET} self-contained binary" if cr_ok else f"{RED}[x]{RESET} chromium {RED}(missing){RESET}"

        print(f"\n{BOLD}ShitCode Browser Automation Status:{RESET}")
        print(f"  * Engine:     {ready_str}")
        print(f"  * Package:    {pw_str}")
        print(f"  * Chromium:   {cr_str}")
        print(f"  * Location:   {browsers_dir}")
        print(f"  * Profile:    {profile_str} ({PROFILE_DIR.name})")
        print(f"  * Session:    {active_str} {DIM}({mode_str}){RESET}\n")

    elif subcmd in ("clean", "reset-profile", "clear-profile"):
        import shutil
        from tools.browser import PROFILE_DIR
        if mgr.is_active():
            print(f"\n{YELLOW}[*] Closing active browser before cleaning...{RESET}")
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(mgr.close())
                else:
                    asyncio.run(mgr.close())
            except Exception:
                pass
        if PROFILE_DIR.exists():
            shutil.rmtree(PROFILE_DIR, ignore_errors=True)
            print(f"\n{GREEN}[✓] Browser user profile wiped clean ({PROFILE_DIR.name}). Cookies and logins reset.{RESET}\n")
        else:
            print(f"\n{DIM}[i] Profile directory already clean.{RESET}\n")

    elif subcmd in ("install", "setup", "download"):
        print(f"\n{BOLD}{CYAN}[*] Checking browser dependencies...{RESET}")
        success, msg = ensure_browser_installed(interactive=True)
        if success:
            print(f"{GREEN}[✓] Browser engine is ready! Run 'browser open <url>' or let AI control it.{RESET}\n")
        else:
            print(f"{RED}[!] Browser installation error: {msg}{RESET}\n")

    elif subcmd in ("open", "launch", "goto"):
        url = subarg or "https://google.com"
        print(f"\n{CYAN}[*] Launching browser to '{url}' (headed with headless fallback)...{RESET}")
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                async def _do_open():
                    res = await mgr.open(url)
                    if res.get("success"):
                        msg = res.get("message") or res.get("warning") or f"Browser opened to {url}"
                        print(f"{GREEN}[✓] {msg}{RESET}\n")
                    else:
                        print(f"{RED}[!] {res.get('error')}{RESET}\n")
                asyncio.create_task(_do_open())
            else:
                res = asyncio.run(mgr.open(url))
                if res.get("success"):
                    msg = res.get("message") or res.get("warning") or f"Browser opened to {url}"
                    print(f"{GREEN}[✓] {msg}{RESET}\n")
                else:
                    print(f"{RED}[!] {res.get('error')}{RESET}\n")
        except Exception as e:
            print(f"{RED}[!] Failed to open browser: {e}{RESET}\n")

    elif subcmd in ("close", "exit", "stop"):
        if not mgr.is_active():
            print(f"\n{DIM}[i] No active browser session to close.{RESET}\n")
            return
        print(f"\n{CYAN}[*] Closing browser session...{RESET}")
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                async def _do_close():
                    res = await mgr.close()
                    print(f"{GREEN}[✓] {res.get('message', 'Closed.')}{RESET}\n")
                asyncio.create_task(_do_close())
            else:
                res = asyncio.run(mgr.close())
                print(f"{GREEN}[✓] {res.get('message', 'Closed.')}{RESET}\n")
        except Exception as e:
            print(f"{RED}[!] Error closing browser: {e}{RESET}\n")

    else:
        print(f"""
{BOLD}Usage: browser <command>{RESET}
  browser open [url]   Launch browser window and open URL
  browser close        Close active browser session
  browser status       Check if Playwright & Chromium are installed
  browser install      Download & install automated Chromium browser
""")


def process_command(cmd_raw: str, state: Any, tools_map: Optional[Dict[str, Any]] = None):
    """Execute an interactive CLI command (synchronous & non-blocking)."""
    if not cmd_raw:
        return

    parts = cmd_raw.split(maxsplit=1)
    action = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if action in ("help", "?", "/help"):
        handle_interactive_help()

    elif action in ("update", "/update", "upgrade"):
        skip_confirm = "-y" in arg.lower() or "--yes" in arg.lower()
        if skip_confirm:
            _run_update_routine(skip_prompt=True)
        else:
            state.active_prompt = "confirm_update"
            print(f"\n{BOLD}{YELLOW}[?] Are you sure you want to update to the latest CLI version? [y/N]: {RESET}", end="", flush=True)

    elif action in ("browser", "/browser"):
        handle_interactive_browser(arg)

    elif action in ("status", "/status"):
        handle_interactive_status(state, tools_map=tools_map)

    elif action in ("tools", "/tools"):
        handle_interactive_tools(tools_map=tools_map)

    elif action in ("expand", "/expand", "verbose", "view", "toggle", "ctrl+o"):
        state.expanded_request_view = not getattr(state, "expanded_request_view", False)
        clear_screen()
        print_banner(state, tools_map=tools_map)
        from core.tunnel import render_request_history
        render_request_history(state)

    elif action in ("clear", "cls", "/clear", "esc", "escape"):
        clear_screen()
        print_banner(state, tools_map=tools_map)

    elif action in ("perm", "permission", "/perm"):
        new_perm = not getattr(state, "ask_permission", False)
        new_mode_str = "Interactive Approval (Ask)" if new_perm else "Auto-Approve"
        state.active_prompt = "confirm_perm"
        print(f"\n{BOLD}{YELLOW}[?] Confirm changing Security Mode to '{new_mode_str}'? [Y/n]: {RESET}", end="", flush=True)

    elif action in ("workspace", "cd", "/workspace"):
        target_path_str = arg.strip("\"' ")
        if not target_path_str:
            state.active_prompt = "input_workspace"
            current_ws = getattr(state, "workspace_dir", ".")
            print(f"\n{AMBER}● Current Workspace:{RESET} {current_ws}\n"
                  f"{BOLD}{ORANGE}[?] Enter new project workspace directory (or press ESC to cancel):{RESET} ", end="", flush=True)
            return

        new_path = Path(target_path_str).expanduser().resolve()
        if is_internal_client_path(new_path):
            print(f"\n{RED}[!] Warning:{RESET} Cannot set workspace to internal ShitCode client directory.\n")
            return

        state.pending_workspace_target = str(new_path)
        state.active_prompt = "confirm_workspace"
        print(f"\n{BOLD}{YELLOW}[?] Confirm switching workspace to '{new_path}'? [Y/n]: {RESET}", end="", flush=True)

    elif action in ("token", "/token") and arg.lower() not in ("reset", "clear"):
        cfg = load_config()
        tok = cfg.get("device_token", "")
        masked = f"{tok[:10]}...{tok[-6:]}" if len(tok) > 16 else "(no token)"
        print(f"\n{CYAN}● Stored Device Token:{RESET} {masked}")
        print(f"  {DIM}Tip: You can edit 'config.json' directly or run 'reset token' to configure a new one.{RESET}\n")

    elif action in ("reset", "/reset", "reset-token", "/reset-token") or (action == "token" and arg.lower() in ("reset", "clear")):
        state.active_prompt = "confirm_reset_token"
        print(f"\n{BOLD}{YELLOW}[?] Are you sure you want to reset your saved device token? This will disconnect the active session. [y/N]: {RESET}", end="", flush=True)

    elif action in ("quit", "exit", "/quit", "/exit", "q"):
        print(f"\n{DIM}[*] Disconnecting client...{RESET}")
        state.is_running = False
        ws = getattr(state, "ws", None)
        if ws:
            asyncio.create_task(ws.close())

    else:
        print(f"{DIM}[?] Unknown command '{action}'. Type 'help' for available commands.{RESET}")
