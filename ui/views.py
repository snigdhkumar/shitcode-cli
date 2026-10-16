"""Terminal views, status banners, ASCII art, and dialog cards for ShitCode CLI."""

from __future__ import annotations

import os
import platform
from typing import Any, Dict
from urllib.parse import urlparse

from ui.theme import AMBER, BOLD, CYAN, DIM, GREEN, ORANGE, RED, RESET, YELLOW


def get_tool_categories(tools_map: Dict[str, Any] | None = None) -> str:
    """Dynamically determine loaded tool module categories without hardcoding."""
    if tools_map is None:
        for mod_name in ("shitcode", "shitcode_client"):
            try:
                mod = sys.modules.get(mod_name) or __import__(mod_name)
                tools_map = getattr(mod, "TOOLS_MAP", None)
                if tools_map is not None:
                    break
            except Exception:
                pass
        if tools_map is None:
            try:
                from core.models import TOOLS_MAP
                tools_map = TOOLS_MAP
            except Exception:
                tools_map = {}
    if not tools_map:
        return "none"
    cats = sorted({fn.__module__.split(".")[-1] for fn in tools_map.values()})
    return ", ".join(cats)


def get_system_badge() -> str:
    """Dynamically generate system info badge from runtime platform inspection."""
    return f"{platform.system()} {platform.release()} ({platform.machine()})".strip()


def print_startup_intro():
    """Display block ASCII logo on client startup."""
    try:
        ascii_art = f"""{ORANGE} ███████╗██╗  ██╗██╗████████╗    ██████╗ ██████╗ ██████╗ ███████╗
 ██╔════╝██║  ██║██║╚══██╔══╝   ██╔════╝██╔═══██╗██╔══██╗██╔════╝
 ███████╗███████║██║   ██║      ██║     ██║   ██║██║  ██║█████╗  
 ╚════██║██╔══██║██║   ██║      ██║     ██║   ██║██║  ██║██╔══╝  
 ███████║██║  ██║██║   ██║      ╚██████╗╚██████╔╝██████╔╝███████╗
 ╚══════╝╚═╝  ╚═╝╚═╝   ╚═╝       ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝{RESET}
"""
        print(ascii_art)
    except Exception:
        pass


def print_banner(state: Any, client_version: Optional[str] = None, tools_map: Dict[str, Any] | None = None):
    """Render a modern Gemini-style status banner with dynamic change highlighting."""
    if client_version is None:
        client_version = getattr(state, "client_version", None)
    if client_version is None:
        try:
            from core.updater import load_client_version
            client_version = load_client_version()
        except Exception:
            client_version = "1.2.0"
    sys_badge = get_system_badge()
    if tools_map is None:
        for mod_name in ("shitcode", "shitcode_client"):
            try:
                mod = sys.modules.get(mod_name) or __import__(mod_name)
                tools_map = getattr(mod, "TOOLS_MAP", None)
                if tools_map is not None:
                    break
            except Exception:
                pass
        if tools_map is None:
            try:
                from core.models import TOOLS_MAP
                tools_map = TOOLS_MAP
            except Exception:
                tools_map = {}
    tools = tools_map

    # Dynamic status line highlighting
    is_sec_changed = "security" in state.recently_changed_fields
    if is_sec_changed:
        sec_str = "Interactive Approval (Ask) [MODIFIED]" if state.ask_permission else "Auto-Approve [MODIFIED]"
        perm_badge = f"{RED}{BOLD}{sec_str}{RESET}"
        sec_label = f"{RED}● {BOLD}Security:{RESET}"
    else:
        perm_badge = f"{YELLOW}Interactive Approval (Ask){RESET}" if state.ask_permission else f"{GREEN}Auto-Approve{RESET}"
        sec_label = f"{YELLOW}●{RESET} {BOLD}Security:{RESET}"

    is_ws_changed = "workspace" in state.recently_changed_fields
    if is_ws_changed:
        ws_display = f"{RED}{BOLD}{state.workspace_dir} [MODIFIED]{RESET}"
        ws_label = f"{RED}● {BOLD}Workspace:{RESET}"
    else:
        ws_display = f"{state.workspace_dir}"
        ws_label = f"{AMBER}●{RESET} {BOLD}Workspace:{RESET}"

    tool_cats = get_tool_categories(tools)
    auth_email = state.user_email or "user"

    # Extract gateway hostname dynamically
    gw_url = os.getenv("SHITCODE_BACKEND_URL", "wss://api.shitcode.in/ws/client")
    gw_host = urlparse(gw_url).netloc or "api.shitcode.in"

    update_notice = ""
    if getattr(state, "newer_version_available", None):
        update_notice = f"\n  {GREEN}[!] New version available: v{state.newer_version_available} (Current: v{client_version}){RESET}\n  {GREEN}    Note: Run 'update' or 'shitcode update' to upgrade.{RESET}\n"

    banner = f"""
{ORANGE}╭────────────────────────────────────────────────────────────────────────╮{RESET}
{ORANGE}│{RESET}  {BOLD}{ORANGE}ShitCode Local Client{RESET} {DIM}v{client_version}{RESET}                              {DIM}({sys_badge}){RESET}   {ORANGE}│{RESET}
{ORANGE}│{RESET}  {DIM}Gateway: {gw_host:<59}{RESET}{ORANGE}│{RESET}
{ORANGE}╰────────────────────────────────────────────────────────────────────────╯{RESET}
  {GREEN}●{RESET} {BOLD}Status:{RESET}    {GREEN}ONLINE{RESET} {DIM}(Authenticated as "{auth_email}" '{state.device_name}'){RESET}
  {CYAN}●{RESET} {BOLD}Session:{RESET}   {DIM}{state.session_id}{RESET}
  {ws_label} {ws_display}
  {sec_label}  {perm_badge}
  {ORANGE}●{RESET} {BOLD}Tools:{RESET}     {len(tools)} tools active {DIM}({tool_cats}){RESET}{update_notice}
{DIM}──────────────────────────────────────────────────────────────────────────{RESET}
  {DIM}Type {BOLD}'help'{RESET}{DIM} for commands | {BOLD}'update'{RESET}{DIM} to upgrade | {BOLD}Ctrl+C{RESET}{DIM} to quit.{RESET}
"""
    print(banner)


def print_invalid_token_card(reason: str = "Invalid or revoked client token"):
    """Render a clear, user-friendly invalid token explanation."""
    card = f"""
{RED}╭────────────────────────────────────────────────────────────────────────╮{RESET}
{RED}│{RESET} {BOLD}{RED}[x] Authentication Failed: Invalid Client Token{RESET}                         {RED}│{RESET}
{RED}│{RESET}                                                                        {RED}│{RESET}
{RED}│{RESET}  {reason[:68]:<68} {RED}│{RESET}
{RED}│{RESET}  {DIM}The token you entered does not exist or has been revoked.{RESET}            {RED}│{RESET}
{RED}│{RESET}                                                                        {RED}│{RESET}
{RED}│{RESET}  {BOLD}How to fix:{RESET}                                                           {RED}│{RESET}
{RED}│{RESET}  1. Open your ShitCode Dashboard: {CYAN}https://dashboard.shitcode.in{RESET}         {RED}│{RESET}
{RED}│{RESET}  2. Go to {BOLD}Devices{RESET} -> Copy your permanent {BOLD}Client Token{RESET} (sc_client_...)     {RED}│{RESET}
{RED}│{RESET}  3. Enter your valid token below.                                      {RED}│{RESET}
{RED}╰────────────────────────────────────────────────────────────────────────╯{RESET}
"""
    print(card)


def print_new_token_configuration_screen():
    """Display dedicated setup card for entering or pasting your Client Token."""
    card = f"""
{ORANGE}╭────────────────────────────────────────────────────────────────────────╮{RESET}
{ORANGE}│{RESET}  {BOLD}{ORANGE}ShitCode Local Client — Configure Client Token{RESET}                       {ORANGE}│{RESET}
{ORANGE}╰────────────────────────────────────────────────────────────────────────╯{RESET}
  {DIM}1. Open your Dashboard:{RESET} {CYAN}https://dashboard.shitcode.in{RESET}
  {DIM}2. Go to:{RESET} {BOLD}Devices{RESET} -> Copy your permanent {BOLD}Client Token{RESET}
  {DIM}3. Paste or enter your Client Token below.{RESET}

  {DIM}(Tip: You can also update config.json in the client folder directly){RESET}
"""
    print(card)


def print_token_reset_success_card():
    """Display dedicated card shown when token reset is confirmed."""
    card = f"""
{GREEN}╭────────────────────────────────────────────────────────────────────────╮{RESET}
{GREEN}│{RESET}  {BOLD}{GREEN}[+] Token Reset Successful{RESET}                                             {GREEN}│{RESET}
{GREEN}│{RESET}  {DIM}Your saved client token has been cleared from config.json.{RESET}            {GREEN}│{RESET}
{GREEN}│{RESET}  {BOLD}Enter your Client Token to continue.{RESET}                                  {GREEN}│{RESET}
{GREEN}╰────────────────────────────────────────────────────────────────────────╯{RESET}
  {DIM}1. Open your Dashboard:{RESET} {CYAN}https://dashboard.shitcode.in{RESET}
  {DIM}2. Go to:{RESET} {BOLD}Devices{RESET} -> Copy your Client Token (sc_client_...)
  {DIM}3. Paste or enter your Client Token below.{RESET}
"""
    print(card)
