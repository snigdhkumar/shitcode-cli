"""Outbound WebSocket reverse tunnel and remote tool execution manager."""

from __future__ import annotations

import asyncio
from datetime import datetime
import inspect
import json
import os
from pathlib import Path
import socket
import sys
import time
from typing import Any, Dict, Optional
import urllib.parse
import websockets

from core.config import (
    load_config,
    reset_device_token,
    save_config,
    set_ask_permission,
    set_device_token,
)
from core.console import async_prompt_line, interactive_console_loop
from core.models import ClientState, TOOLS_MAP
from core.updater import (
    CLIENT_VERSION,
    PRODUCTION_GATEWAY_URL,
    check_for_updates_sync,
)
from ui.theme import BOLD, CYAN, DIM, GREEN, ORANGE, RED, RESET, YELLOW
from ui.views import print_banner, print_invalid_token_card


async def confirm_tool_execution(tool_name: str, arguments: Dict[str, Any], state: ClientState) -> str:
    """Prompt user in CLI for confirmation before running actions via single stdin reader."""
    state.is_prompting_permission = True
    snippet = ""
    if "command" in arguments:
        snippet = arguments["command"]
    elif "path" in arguments:
        snippet = arguments["path"]
    elif "code" in arguments:
        snippet = arguments["code"].splitlines()[0] if arguments["code"].splitlines() else "Python code"
    else:
        snippet = json.dumps(arguments, ensure_ascii=False)

    if len(snippet) > 80:
        snippet = snippet[:77] + "..."

    prompt_box = f"""
  {YELLOW}╭─ [Permission Request] AI wants to run tool: {BOLD}{tool_name}{RESET}{YELLOW} ─╮{RESET}
  {YELLOW}│{RESET} Target: {snippet:<60} {YELLOW}│{RESET}
  {YELLOW}╰─────────────────────────────────────────────────────────────────╯{RESET}
  {BOLD}Allow this action? [Y/n/always/quit]:{RESET} """

    print(prompt_box, end="", flush=True)

    loop = asyncio.get_running_loop()
    fut = loop.create_future()
    state.pending_perm_future = fut

    try:
        user_choice = await fut
        choice = user_choice.strip().lower()
    except Exception:
        choice = "n"
    finally:
        state.pending_perm_future = None
        state.is_prompting_permission = False

    if choice in ("y", "yes", ""):
        return "allow"
    elif choice in ("a", "always"):
        return "always"
    elif choice in ("q", "quit", "exit"):
        return "quit"
    else:
        return "deny"


async def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> str:
    """Execute a local tool function with arguments."""
    if tool_name not in TOOLS_MAP:
        raise ValueError(f"Tool '{tool_name}' is not registered on this client.")

    fn = TOOLS_MAP[tool_name]

    # Normalize alias parameter names
    norm_args = dict(arguments)
    if tool_name in ("grep_search", "search_files"):
        if "pattern" in norm_args and "query" not in norm_args:
            norm_args["query"] = norm_args["pattern"]
        elif "query" in norm_args and "pattern" not in norm_args:
            norm_args["pattern"] = norm_args["query"]
    elif tool_name == "web_extract":
        if "url" in norm_args and "urls" not in norm_args:
            norm_args["urls"] = [norm_args["url"]]
        elif "urls" in norm_args and "url" not in norm_args:
            norm_args["url"] = norm_args["urls"] if isinstance(norm_args["urls"], str) else (norm_args["urls"][0] if norm_args["urls"] else "")
    elif tool_name == "multi_patch_file":
        if "patches" in norm_args and "replacements" not in norm_args:
            norm_args["replacements"] = norm_args["patches"]
        elif "replacements" in norm_args and "patches" not in norm_args:
            norm_args["patches"] = norm_args["replacements"]
    elif tool_name in ("patch_file", "patch"):
        if "old_string" not in norm_args:
            if "old_str" in norm_args:
                norm_args["old_string"] = norm_args["old_str"]
            elif "old_text" in norm_args:
                norm_args["old_string"] = norm_args["old_text"]
        if "new_string" not in norm_args:
            if "new_str" in norm_args:
                norm_args["new_string"] = norm_args["new_str"]
            elif "new_text" in norm_args:
                norm_args["new_string"] = norm_args["new_text"]

    sig = inspect.signature(fn)
    valid_args = {}
    for param_name, _ in sig.parameters.items():
        if param_name in norm_args:
            valid_args[param_name] = norm_args[param_name]

    if inspect.iscoroutinefunction(fn):
        result = await fn(**valid_args)
    else:
        result = await asyncio.to_thread(fn, **valid_args)

    return str(result) if result is not None else ""


async def run_client_loop(
    device_token: str,
    workspace_dir: str,
    ask_permission: bool = False,
):
    """Maintain outbound WebSocket connection with smart token recovery and interactive lifecycle."""
    current_token = device_token
    server_ws_url = os.getenv("SHITCODE_BACKEND_URL", PRODUCTION_GATEWAY_URL)

    state = ClientState(
        workspace_dir=workspace_dir,
        ask_permission=ask_permission,
    )

    console_task = asyncio.create_task(interactive_console_loop(state))

    async def check_updates_bg():
        try:
            ver = await asyncio.to_thread(check_for_updates_sync)
            if ver:
                state.newer_version_available = ver
                print(f"\n{GREEN}[!] New version available: v{ver} (Current: v{CLIENT_VERSION}){RESET}")
                print(f"{GREEN}    Note: Run 'update' or 'shitcode update' to upgrade.{RESET}\n")
        except Exception:
            pass

    update_task = asyncio.create_task(check_updates_bg())
    backoff = 2

    while state.is_running:
        hostname = socket.gethostname()
        os_name = "windows" if sys.platform == "win32" else "linux"
        url = f"{server_ws_url}?token={urllib.parse.quote(current_token)}&name={urllib.parse.quote(hostname)}&os={os_name}"
        t_now = datetime.now().strftime("%H:%M:%S")
        print(f"\n{DIM}[{t_now}] [*] Connecting to ShitCode Cloud Gateway ({hostname} - {os_name})...{RESET}", flush=True)

        session_established = False

        try:
            async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                state.ws = ws
                backoff = 2

                welcome_raw = await ws.recv()
                try:
                    welcome = json.loads(welcome_raw)
                except Exception:
                    welcome = {}

                if welcome.get("type") == "error":
                    err_code = welcome.get("code")
                    err_msg = welcome.get("error", "Authentication error")

                    if err_code in (4003, 4008):
                        reset_device_token()
                        print_invalid_token_card(reason="Client token was rotated or revoked." if err_code == 4008 else err_msg)
                        new_token = await async_prompt_line(
                            state,
                            f"\n{BOLD}{ORANGE}[?] Enter your Client Token (sc_client_...):{RESET} "
                        )
                        if not new_token:
                            print(f"{DIM}[*] Exiting.{RESET}")
                            state.is_running = False
                            return
                        current_token = new_token
                        cfg = load_config()
                        cfg["device_token"] = new_token
                        save_config(cfg)
                        backoff = 0
                        continue
                    elif err_code == 4429:
                        print(f"\n{YELLOW}[!] Rate limit: {err_msg}. Cooling down for 30s...{RESET}")
                        await asyncio.sleep(30)
                        continue

                state.device_name = welcome.get("device_name", "Local PC")
                state.user_email = welcome.get("user_email") or "user"
                state.session_id = welcome.get("session_id", "active")
                session_established = True

                print_banner(state)

                async for message in ws:
                    if not state.is_running:
                        break

                    try:
                        data = json.loads(message)
                    except Exception:
                        continue

                    msg_type = data.get("type")

                    if msg_type == "call_tool":
                        call_id = data.get("call_id")
                        tool_name = data.get("tool")
                        arguments = data.get("arguments", {})

                        t_stamp = datetime.now().strftime("%H:%M:%S")

                        args_preview = json.dumps(arguments, ensure_ascii=False)
                        if len(args_preview) > 90:
                            args_preview = args_preview[:87] + "..."

                        print(f"\n{CYAN}[{t_stamp}]{RESET} {BOLD}╭─ AI Request:{RESET} {ORANGE}{tool_name}{RESET} {DIM}──────────────────────────────────╮{RESET}")
                        print(f"         {DIM}│ Args: {args_preview}{RESET}")
                        print(f"         {DIM}╰────────────────────────────────────────────────────────╯{RESET}")

                        if state.ask_permission:
                            perm_result = await confirm_tool_execution(tool_name, arguments, state)
                            if perm_result == "always":
                                state.ask_permission = False
                                set_ask_permission(False)
                                state.recently_changed_fields.add("security")
                                print(f"         {YELLOW}● Switched to Auto-Approve for the remainder of this session.{RESET}")
                            elif perm_result == "quit":
                                print(f"         {RED}● Session stopped by user.{RESET}")
                                state.is_running = False
                                await ws.close()
                                return
                            elif perm_result == "deny":
                                print(f"         {RED}[-] Action declined by user.{RESET}")
                                await ws.send(json.dumps({
                                    "type": "tool_result",
                                    "call_id": call_id,
                                    "success": False,
                                    "error": "Action declined by user on local machine.",
                                }))
                                continue

                        t_start = time.perf_counter()
                        try:
                            output = await execute_tool(tool_name, arguments)
                            elapsed_ms = int((time.perf_counter() - t_start) * 1000)
                            print(f"         {GREEN}[+] Completed in {elapsed_ms}ms{RESET} {DIM}(Returned result to AI){RESET}")

                            response = {
                                "type": "tool_result",
                                "call_id": call_id,
                                "success": True,
                                "result": output,
                            }
                        except Exception as e:
                            elapsed_ms = int((time.perf_counter() - t_start) * 1000)
                            print(f"         {RED}[!] Execution error ({elapsed_ms}ms): {e}{RESET}")

                            response = {
                                "type": "tool_result",
                                "call_id": call_id,
                                "success": False,
                                "error": str(e),
                            }

                        await ws.send(json.dumps(response))

                    elif msg_type == "ping":
                        await ws.send(json.dumps({"type": "pong"}))

        except websockets.exceptions.ConnectionClosed as cc:
            if not state.is_running:
                break

            if state.reconnect_with_new_token:
                current_token = state.reconnect_with_new_token
                state.reconnect_with_new_token = None
                backoff = 0
                continue

            if cc.code in (4003, 4008) or (not session_established and cc.code in (1006, 4001)):
                reset_device_token()
                reason_str = "This client token was revoked or refreshed from the ShitCode dashboard." if cc.code == 4008 else "The token was rejected by the ShitCode gateway."
                print_invalid_token_card(reason=reason_str)
                new_token = await async_prompt_line(
                    state,
                    f"\n{BOLD}{ORANGE}[?] Enter your Client Token (sc_client_...):{RESET} "
                )
                if not new_token:
                    print(f"{DIM}[*] Exiting.{RESET}")
                    state.is_running = False
                    return
                current_token = new_token
                set_device_token(new_token)
                backoff = 0
                continue

            elif cc.code == 4009:
                print(f"\n{YELLOW}╭────────────────────────────────────────────────────────────────────────╮{RESET}")
                print(f"{YELLOW}│{RESET} {BOLD}{YELLOW}Session Superseded (Code 4009){RESET}                                      {YELLOW}│{RESET}")
                print(f"{YELLOW}│{RESET} Another client instance just connected with this Client Token.          {YELLOW}│{RESET}")
                print(f"{YELLOW}│{RESET} {DIM}Policy: Each connected client has its own dedicated session.{RESET}           {YELLOW}│{RESET}")
                print(f"{YELLOW}╰────────────────────────────────────────────────────────────────────────╯{RESET}")
                ans = await async_prompt_line(
                    state,
                    f"{BOLD}[?] Reconnect and take over active session? [Y/n]: {RESET}"
                )
                if ans.lower() in ("y", "yes", ""):
                    backoff = 1
                    continue
                else:
                    print(f"{DIM}[*] Disconnected cleanly.{RESET}")
                    state.is_running = False
                    return

            elif cc.code == 4429:
                print(f"\n{YELLOW}[!] Connection rate limit reached ({cc.reason}). Cooling down for 30s...{RESET}")
                await asyncio.sleep(30)
                continue

            else:
                print(f"\n{RED}[!] Disconnected from server (Code {cc.code}: {cc.reason or 'Connection closed'}).{RESET}")

        except Exception as e:
            if not state.is_running:
                break
            print(f"\n{RED}[!] Connection failed: {e}{RESET}")

        if state.reconnect_with_new_token:
            current_token = state.reconnect_with_new_token
            state.reconnect_with_new_token = None
            backoff = 0
            continue

        if state.is_running:
            print(f"{DIM}[*] Reconnecting in {backoff}s... (Press Ctrl+C to cancel){RESET}")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)

    console_task.cancel()
    update_task.cancel()
