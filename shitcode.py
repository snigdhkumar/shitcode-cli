#!/usr/bin/env python3
"""ShitCode Local Client Agent.
Maintains a secure, outbound-only WebSocket reverse tunnel connecting your local computer
to AI assistants (ChatGPT, Claude Desktop, Cursor) via the ShitCode Gateway.
Zero open ports, zero port forwarding, with native Windows (PowerShell) and Linux (Bash) execution.
"""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
import sys
from typing import Any, Dict, Optional

# Ensure root directory is on sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Ensure Playwright browser binaries are stored self-contained in shitcode-cli/.browsers
if "PLAYWRIGHT_BROWSERS_PATH" not in os.environ:
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(ROOT_DIR / ".browsers")

# Core config helpers
from core.config import (
    get_fallback_workspace,
    is_internal_client_path,
    load_config,
    reset_device_token,
    save_config,
    set_ask_permission,
    set_device_token,
    set_workspace_dir,
)

# Theme and ANSI terminal styling
from ui.theme import (
    AMBER,
    BOLD,
    CYAN,
    DIM,
    GRAY,
    GREEN,
    ORANGE,
    RED,
    RESET,
    YELLOW,
    init_terminal,
)

# Initialize ANSI terminal processing
init_terminal()

# Models and tool registry
from core.models import ClientState, MODIFYING_TOOLS, TOOLS_MAP

# Auto-update and version routines
from core.updater import (
    CLIENT_VERSION,
    PRODUCTION_GATEWAY_URL,
    UPDATE_CHECK_URL,
    check_for_updates_sync,
    execute_update_routine,
    is_newer_version,
    load_client_version,
    parse_semver,
)

# Terminal I/O routines
from core.terminal_io import (
    clear_screen,
    get_clipboard_text,
    read_console_line,
)

# UI views, banners, and dialog cards
from ui.views import (
    get_system_badge,
    get_tool_categories as views_get_tool_categories,
    print_banner as views_print_banner,
    print_invalid_token_card,
    print_new_token_configuration_screen,
    print_startup_intro,
    print_token_reset_success_card,
)

# Command handlers
from commands.handlers import (
    handle_interactive_help,
    handle_interactive_status,
    handle_interactive_tools,
    process_command,
)

# Interactive console loop and startup prompts
from core.console import (
    apply_workspace,
    async_prompt_line,
    interactive_console_loop,
    prompt_for_token,
    prompt_for_workspace,
    prompt_startup_token_choice,
)

# Reverse tunnel and tool execution
from core.tunnel import (
    confirm_tool_execution,
    execute_tool,
    run_client_loop,
)


def get_tool_categories(tools_map: Optional[Dict[str, Any]] = None) -> str:
    """Dynamically determine loaded tool module categories."""
    target_map = tools_map if tools_map is not None else TOOLS_MAP
    return views_get_tool_categories(target_map)


def print_banner(state: ClientState, client_version: str = CLIENT_VERSION, tools_map: Optional[Dict[str, Any]] = None):
    """Render status banner with active tools mapping."""
    target_map = tools_map if tools_map is not None else TOOLS_MAP
    views_print_banner(state, client_version=client_version, tools_map=target_map)


def main():
    """Main CLI entrypoint with argument parsing and session launch."""
    if len(sys.argv) > 1 and sys.argv[1].lower() in ("update", "upgrade"):
        skip = any(arg.lower() in ("-y", "--yes") for arg in sys.argv[2:])
        success = execute_update_routine(skip_prompt=skip)
        sys.exit(0 if success else 1)

    if len(sys.argv) > 1 and sys.argv[1].lower() == "browser":
        from commands.handlers import handle_interactive_browser
        subarg = " ".join(sys.argv[2:])
        handle_interactive_browser(subarg)
        sys.exit(0)

    parser = argparse.ArgumentParser(
        prog="shitcode",
        description=f"{BOLD}{ORANGE}ShitCode Local Client Agent (v{CLIENT_VERSION}){RESET}\n"
                    "Connects your local machine to ChatGPT, Claude, and external AI agents over a secure reverse tunnel.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""{BOLD}examples:{RESET}
  shitcode.bat                (Windows 1-Click)
  ./shitcode.sh               (Linux 1-Click)
  python shitcode.py
  python shitcode.py update
  python shitcode.py update -y
  python shitcode.py --ask-permission
  python shitcode.py --workspace ~/projects
  python shitcode.py --token sc_client_...
  python shitcode.py --reset-token

{BOLD}dashboard:{RESET}
  Get your Client Token and view active connections at: {CYAN}https://dashboard.shitcode.in{RESET}
"""
    )
    parser.add_argument("-t", "--token", help="Client Token from dashboard.shitcode.in (sc_client_...)")
    parser.add_argument("-w", "--workspace", help="Base workspace directory for file and terminal operations")
    parser.add_argument("-p", "--ask-permission", action="store_true", help="Prompt for manual confirmation before executing shell commands or code")
    parser.add_argument("--reset-token", action="store_true", help="Clear saved client token from config.json and prompt for a new one")
    parser.add_argument("-v", "--version", action="version", version=f"ShitCode Client v{CLIENT_VERSION}")

    args = parser.parse_args()

    print_startup_intro()
    cfg = load_config()

    if args.reset_token:
        reset_device_token()
        print(f"\n{GREEN}[+] Stored client token cleared from config.json.{RESET}")

    raw_workspace = args.workspace or cfg.get("workspace_dir") or ""
    if not raw_workspace or is_internal_client_path(raw_workspace):
        print(f"\n{AMBER}╭─ Project Workspace Configuration ──────────────────────────────────────╮{RESET}")
        print(f"{AMBER}│{RESET} Please select the project directory where you want the AI to work.     {AMBER}│{RESET}")
        print(f"{AMBER}│{RESET} {DIM}(To keep internal client files safe, do not select ShitCode/client){RESET}     {AMBER}│{RESET}")
        print(f"{AMBER}╰────────────────────────────────────────────────────────────────────────╯{RESET}")
        chosen_workspace = prompt_for_workspace(raw_workspace)
        set_workspace_dir(chosen_workspace)
        workspace_path = chosen_workspace
    else:
        workspace_path = raw_workspace

    apply_workspace(workspace_path)

    if args.token:
        token = args.token
    elif args.reset_token:
        print_new_token_configuration_screen()
        token = prompt_for_token()
        if not token:
            print(f"\n{RED}[!] Client token is required to connect. Exiting.{RESET}")
            sys.exit(1)
        set_device_token(token)
        print(f"{GREEN}[+] Client token saved to config.json!{RESET}")
    else:
        saved_token = load_config().get("client_token") or load_config().get("device_token") or os.getenv("SHITCODE_CLIENT_TOKEN") or os.getenv("SHITCODE_DEVICE_TOKEN")
        if saved_token:
            token, _ = prompt_startup_token_choice(saved_token)
            if not token:
                print(f"\n{RED}[!] Client token is required to connect. Exiting.{RESET}")
                sys.exit(1)
        else:
            print_new_token_configuration_screen()
            token = prompt_for_token()
            if not token:
                print(f"\n{RED}[!] Client token is required to connect. Exiting.{RESET}")
                sys.exit(1)
            set_device_token(token)
            print(f"{GREEN}[+] Client token saved to config.json!{RESET}")

    ask_permission = args.ask_permission or cfg.get("ask_permission", False)

    try:
        asyncio.run(run_client_loop(
            device_token=token,
            workspace_dir=str(Path(workspace_path).resolve()),
            ask_permission=ask_permission,
        ))
    except KeyboardInterrupt:
        print(f"\n\n{DIM}[*] ShitCode Client stopped by user.{RESET}")


if __name__ == "__main__":
    main()
