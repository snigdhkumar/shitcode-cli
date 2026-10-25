"""Interactive console event loop and startup prompt dialogues."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys
from typing import Optional

from core.config import (
    get_fallback_workspace,
    is_internal_client_path,
    reset_device_token,
    set_ask_permission,
    set_device_token,
    set_workspace_dir,
)
from core.models import ClientState, TOOLS_MAP
from core.terminal_io import clear_screen, read_console_line
from core.updater import execute_update_routine
from ui.theme import AMBER, BOLD, CYAN, DIM, GREEN, ORANGE, RED, RESET, YELLOW
from ui.views import (
    print_banner,
    print_new_token_configuration_screen,
    print_token_reset_success_card,
)


def prompt_startup_token_choice(saved_token: str) -> tuple[str, bool]:
    """Prompt user on startup whether to continue with saved token or configure a new one."""
    masked = f"{saved_token[:10]}...{saved_token[-6:]}" if len(saved_token) > 16 else saved_token
    menu = f"""
{ORANGE}╭─ Client Token Authentication ──────────────────────────────────────────╮{RESET}
{ORANGE}│{RESET}  {BOLD}Saved Client Token Found:{RESET} {CYAN}{masked}{RESET}
{ORANGE}│{RESET}                                                                        {ORANGE}│{RESET}
{ORANGE}│{RESET}  {BOLD}[1] Continue with saved client token{RESET} {DIM}(Press Enter){RESET}                    {ORANGE}│{RESET}
{ORANGE}│{RESET}  {BOLD}[2] Configure new client token{RESET}                                       {ORANGE}│{RESET}
{ORANGE}╰────────────────────────────────────────────────────────────────────────╯{RESET}
  {DIM}(Tip: You can change the token in config.json or type 'reset token' later){RESET}
"""
    print(menu)
    print(f"{BOLD}{ORANGE}[?] Select option [1/2] (default: 1):{RESET} ", end="", flush=True)
    try:
        choice = input().strip()
    except (KeyboardInterrupt, EOFError):
        print(f"\n{DIM}[*] Startup cancelled.{RESET}")
        return ("", False)

    if choice in ("2", "new", "configure", "c"):
        print_new_token_configuration_screen()
        new_token = prompt_for_token()
        if new_token:
            set_device_token(new_token)
            print(f"{GREEN}[+] New client token saved to config.json!{RESET}\n")
            return (new_token, True)
        return ("", True)

    return (saved_token, False)


def prompt_for_token() -> Optional[str]:
    """Interactively prompt user for a valid client token."""
    print(f"\n{BOLD}{ORANGE}[?] Enter your Client Token (sc_client_...):{RESET} ", end="", flush=True)
    try:
        token = input().strip()
    except (KeyboardInterrupt, EOFError):
        print(f"\n{DIM}[*] Setup cancelled.{RESET}")
        return None
    return token if token else None


def prompt_for_workspace(current_val: str = "") -> str:
    """Interactively prompt user for project workspace directory."""
    default_dir = current_val if current_val and not is_internal_client_path(current_val) else get_fallback_workspace()
    print(f"\n{BOLD}{ORANGE}[?] Enter project workspace directory for AI tools{RESET}")
    print(f"    {DIM}(Default: {default_dir}):{RESET} ", end="", flush=True)
    try:
        chosen = input().strip().strip("\"' ")
    except (KeyboardInterrupt, EOFError):
        chosen = ""

    target_dir = chosen if chosen else default_dir
    target_path = Path(target_dir).resolve()
    target_path.mkdir(parents=True, exist_ok=True)
    return str(target_path)


def apply_workspace(path_str: str):
    """Set process working directory and terminal module workdir."""
    p = Path(path_str).resolve()
    p.mkdir(parents=True, exist_ok=True)
    os.chdir(str(p))

    try:
        import tools.terminal as term_mod
        term_mod._CURRENT_WORKDIR = str(p)
    except Exception:
        pass


async def async_prompt_line(state: ClientState, prompt_text: str) -> str:
    """Prompt user for text line input safely routed through the single stdin reader."""
    print(prompt_text, end="", flush=True)
    loop = asyncio.get_running_loop()
    fut = loop.create_future()
    state.pending_line_future = fut
    try:
        line = await fut
        return line.strip()
    except Exception:
        return ""
    finally:
        state.pending_line_future = None


async def interactive_console_loop(state: ClientState):
    """Single unified background task reading stdin while client runs."""
    loop = asyncio.get_running_loop()

    from commands.handlers import process_command

    while state.is_running:
        try:
            raw_text, is_escape = await loop.run_in_executor(None, read_console_line, state)
            if not state.is_running:
                break

            cleaned = raw_text.strip()

            # 1. AI Tool Permission prompt (highest priority)
            if state.pending_perm_future and not state.pending_perm_future.done():
                if cleaned in ("__CTRL_O__", "ctrl+o", "\x0f"):
                    state.pending_perm_future.set_result("__ctrl_o__")
                elif is_escape or cleaned.lower() in ("n", "no", "cancel"):
                    state.pending_perm_future.set_result("n")
                else:
                    state.pending_perm_future.set_result(cleaned.lower())
                continue

            # 2. Line prompt for reconnect/token from run_client_loop
            if state.pending_line_future and not state.pending_line_future.done():
                if is_escape:
                    state.pending_line_future.set_result("")
                else:
                    state.pending_line_future.set_result(cleaned)
                continue

            # 3. Handle active console section prompts
            if state.active_prompt == "confirm_perm":
                state.active_prompt = None
                if is_escape or cleaned.lower() in ("n", "no", "cancel", "q", "exit"):
                    print(f"  {DIM}[*] Security Mode change cancelled.{RESET}\n")
                elif cleaned.lower() in ("y", "yes", ""):
                    state.ask_permission = not state.ask_permission
                    set_ask_permission(state.ask_permission)
                    state.recently_changed_fields.add("security")
                    clear_screen()
                    print_banner(state)
                    new_mode_str = "Interactive Approval (Ask)" if state.ask_permission else "Auto-Approve"
                    print(f"  {GREEN}[+] Security Mode updated to: {new_mode_str}{RESET}\n")
                else:
                    print(f"  {DIM}[*] Unrecognized option. Security Mode unchanged.{RESET}\n")
                continue

            if state.active_prompt == "input_workspace":
                clean_path_input = cleaned.strip("\"' ")
                if is_escape or clean_path_input.lower() in ("cancel", "q", "exit") or not clean_path_input:
                    state.active_prompt = None
                    print(f"  {DIM}[*] Workspace change cancelled.{RESET}\n")
                else:
                    new_path = Path(clean_path_input).expanduser().resolve()
                    if is_internal_client_path(new_path):
                        print(f"\n  {RED}[!] Warning:{RESET} Cannot set workspace to internal ShitCode client directory.\n")
                        state.active_prompt = None
                    else:
                        state.pending_workspace_target = str(new_path)
                        state.active_prompt = "confirm_workspace"
                        print(f"\n{BOLD}{YELLOW}[?] Confirm switching workspace to '{new_path}'? [Y/n]: {RESET}", end="", flush=True)
                continue

            if state.active_prompt == "confirm_workspace":
                target = state.pending_workspace_target
                state.active_prompt = None
                state.pending_workspace_target = None
                if is_escape or cleaned.lower() in ("n", "no", "cancel", "q", "exit"):
                    print(f"  {DIM}[*] Workspace switch cancelled.{RESET}\n")
                elif cleaned.lower() in ("y", "yes", ""):
                    try:
                        apply_workspace(target)
                        state.workspace_dir = target
                        set_workspace_dir(target)
                        state.recently_changed_fields.add("workspace")
                        clear_screen()
                        print_banner(state)
                        print(f"  {GREEN}[+] Workspace switched live to: {state.workspace_dir}{RESET}\n")
                    except Exception as e:
                        print(f"\n  {RED}[!] Failed to switch workspace: {e}{RESET}\n")
                else:
                    print(f"  {DIM}[*] Workspace switch cancelled.{RESET}\n")
                continue

            if state.active_prompt == "confirm_reset_token":
                state.active_prompt = None
                if is_escape or cleaned.lower() not in ("y", "yes"):
                    print(f"  {DIM}[*] Device token reset cancelled.{RESET}\n")
                else:
                    reset_device_token()
                    print_token_reset_success_card()
                    state.active_prompt = "input_new_token_after_reset"
                    print(f"{BOLD}{ORANGE}[?] Enter your new Device Token (sc_dev_...): {RESET}", end="", flush=True)
                continue

            if state.active_prompt == "input_new_token_after_reset":
                state.active_prompt = None
                new_tok = cleaned.strip()
                if is_escape or not new_tok or new_tok.lower() in ("cancel", "exit", "q"):
                    print(f"\n  {YELLOW}[!] No token entered. Stored token remains cleared in config.json.{RESET}")
                    print(f"  {DIM}[*] Disconnecting client. Run client again or edit config.json to connect.{RESET}\n")
                    state.is_running = False
                    if state.ws:
                        asyncio.create_task(state.ws.close())
                else:
                    set_device_token(new_tok)
                    print(f"\n  {GREEN}[+] New device token saved to config.json!{RESET}")
                    print(f"  {DIM}[*] Reconnecting to ShitCode Cloud Gateway with new token...{RESET}\n")
                    state.reconnect_with_new_token = new_tok
                    if state.ws:
                        asyncio.create_task(state.ws.close())
                continue

            if state.active_prompt == "confirm_update":
                state.active_prompt = None
                if is_escape or cleaned.lower() not in ("y", "yes"):
                    print(f"  {DIM}[*] Update cancelled.{RESET}\n")
                else:
                    execute_update_routine(skip_prompt=True)
                continue

            # 4. Handle Ctrl+O or 'expand' / 'verbose' to toggle enlarged AI request view
            if cleaned in ("__CTRL_O__", "ctrl+o", "\x0f", "expand", "verbose"):
                state.expanded_request_view = not getattr(state, "expanded_request_view", False)
                mode_str = "ENLARGED (Full parameters shown)" if state.expanded_request_view else "COMPACT (Truncated previews)"
                mode_color = GREEN if state.expanded_request_view else YELLOW
                print(f"\n  {mode_color}● AI Request View: {BOLD}{mode_str}{RESET}")
                print(f"    {DIM}Press {BOLD}Ctrl+O{RESET}{DIM} to toggle again.{RESET}")
                if getattr(state, "last_ai_request", None):
                    from core.tunnel import format_ai_request
                    last = state.last_ai_request
                    print(format_ai_request(last["tool"], last["arguments"], last["time"], expanded=state.expanded_request_view))
                print()
                continue

            # 5. Escape key pressed or user typed 'esc' / 'clear' -> Clear screen and restore main banner
            if is_escape or cleaned.lower() in ("esc", "escape"):
                clear_screen()
                print_banner(state)
                continue

            # 5. Empty Enter pressed -> Keep screen as-is
            if not cleaned:
                continue

            # 6. User entered a command -> dispatch
            process_command(cleaned, state, tools_map=TOOLS_MAP)

        except KeyboardInterrupt:
            print(f"\n{DIM}[*] Disconnecting client...{RESET}")
            state.is_running = False
            if state.ws:
                asyncio.create_task(state.ws.close())
            break
        except Exception:
            if not state.is_running:
                break
            await asyncio.sleep(0.1)
