"""Browser Automation Package for ShitCode.
Exports Playwright-powered browser opening, element clicking, text typing, content extraction,
visual screenshot capture, compound batch execution, and session closing tools.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from core.reporter import with_error_reporting
from tools.browser.manager import (
    BrowserManager,
    find_installed_browser,
    has_gui_display,
    is_browser_process_running,
    is_cdp_port_active,
    launch_user_browser_with_cdp,
    close_browser_processes,
    safe_print,
)


@with_error_reporting("browser_open")
async def browser_open(
    url: str,
    headless: Optional[bool] = None,
    fast_mode: bool = True,
    target: str = "auto",
    browser_name: Optional[str] = None,
    cdp_port: int = 9222,
    force_restart: bool = False,
) -> str:
    """Launch browser session or attach to user's everyday browser and navigate to target URL.

    Args:
        url: Target webpage URL to visit.
        headless: Force headless background mode (omits visible window) for isolated sandbox.
        fast_mode: Block heavy ad networks and tracking beacons for maximum speed.
        target: 'auto' (detect live user browser or fallback to sandbox), 'user' (everyday Chrome/Edge/Brave with live logins via CDP), or 'isolated' (dedicated clean Playwright sandbox). Note: Never invent or pass custom --user-data-dir shadow directories.
        browser_name: Specific browser to target ('chrome', 'edge', 'brave') if multiple exist.
        cdp_port: Chrome DevTools Protocol remote debugging port (default: 9222).
        force_restart: If True and browser is running without debugging enabled, automatically terminates existing browser processes and relaunches it with remote debugging (after user approval).
    """
    mgr = BrowserManager.get_instance()
    res = await mgr.open(
        url=url,
        headless=headless,
        fast_mode=fast_mode,
        target=target,
        browser_name=browser_name,
        cdp_port=cdp_port,
        force_restart=force_restart,
    )
    return json.dumps(res, indent=2, ensure_ascii=False)


@with_error_reporting("browser_click")
async def browser_click(selector: str, text: Optional[str] = None) -> str:
    """Click an element on the active web page by CSS selector or text."""
    mgr = BrowserManager.get_instance()
    res = await mgr.click(selector=selector, text=text)
    return json.dumps(res, indent=2, ensure_ascii=False)


@with_error_reporting("browser_type")
async def browser_type(selector: str, text: str, press_enter: bool = False) -> str:
    """Type text into an input field or form on the active web page."""
    mgr = BrowserManager.get_instance()
    res = await mgr.type_text(selector=selector, text=text, press_enter=press_enter)
    return json.dumps(res, indent=2, ensure_ascii=False)


@with_error_reporting("browser_extract")
async def browser_extract(format: str = "markdown", selector: Optional[str] = None) -> str:
    """Extract clean, token-efficient Markdown, interactive element catalog, or text from the active web page."""
    mgr = BrowserManager.get_instance()
    res = await mgr.extract(format=format, selector=selector)
    if res.get("success") and "content" in res:
        return res["content"]
    return json.dumps(res, indent=2, ensure_ascii=False)


@with_error_reporting("browser_screenshot")
async def browser_screenshot(full_page: bool = False, selector: Optional[str] = None, format: str = "png") -> Any:
    """Capture a screenshot of the active web page and return multimodal image blocks directly to AI."""
    mgr = BrowserManager.get_instance()
    res = await mgr.screenshot(full_page=full_page, selector=selector, format=format)
    if res.get("success") and "content" in res:
        return res
    return json.dumps(res, indent=2, ensure_ascii=False)


@with_error_reporting("browser_actions")
async def browser_actions(actions: list) -> Any:
    """Execute a batch of sequential browser actions in a single turn with live CLI feedback.
    Supported actions: goto, fill, fill_form, click, select, wait_for, assert_visible, extract_scoped, screenshot, wait.
    """
    mgr = BrowserManager.get_instance()
    res = await mgr.actions(actions_list=actions)
    if res.get("success") and "content" in res:
        return res
    return json.dumps(res, indent=2, ensure_ascii=False)


@with_error_reporting("browser_close")
async def browser_close(kill_process: bool = False, browser_name: Optional[str] = None) -> str:
    """Close the active browser session, and optionally terminate running OS browser processes.
    
    Args:
        kill_process: If True, terminates running operating system processes of the target browser.
        browser_name: Optional browser to target ('chrome', 'edge', 'brave').
    """
    mgr = BrowserManager.get_instance()
    res = await mgr.close(kill_process=kill_process, browser_name=browser_name)
    return json.dumps(res, indent=2, ensure_ascii=False)


__all__ = [
    "BrowserManager",
    "has_gui_display",
    "safe_print",
    "find_installed_browser",
    "is_cdp_port_active",
    "launch_user_browser_with_cdp",
    "close_browser_processes",
    "browser_open",
    "browser_click",
    "browser_type",
    "browser_extract",
    "browser_screenshot",
    "browser_actions",
    "browser_close",
]
