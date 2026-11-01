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
    has_gui_display,
    safe_print,
)


@with_error_reporting("browser_open")
async def browser_open(
    url: str,
    headless: Optional[bool] = None,
    fast_mode: bool = True,
) -> str:
    """Launch built-in Playwright persistent browser session and navigate to target URL.

    Dedicated to fast web automation, scraping, QA testing, and form filling with 100% selector reliability.
    For automating the user's personal everyday browser (Chrome/Edge/Brave with live logins), use Desktop Computer Control.

    Args:
        url: Target webpage URL to visit.
        headless: Force headless background mode (omits visible window). Default is headed when display is available.
        fast_mode: Block heavy ad networks and tracking beacons for maximum speed.
    """
    mgr = BrowserManager.get_instance()
    res = await mgr.open(
        url=url,
        headless=headless,
        fast_mode=fast_mode,
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
async def browser_close() -> str:
    """Close the active built-in browser session and save profile."""
    mgr = BrowserManager.get_instance()
    res = await mgr.close()
    return json.dumps(res, indent=2, ensure_ascii=False)


@with_error_reporting("browser_evaluate")
async def browser_evaluate(expression: str, arg: Optional[Any] = None) -> str:
    """Execute arbitrary JavaScript code or expressions in the active browser page context.

    Enables reading LocalStorage, dispatching synthetic events, reading dynamic JS variables,
    calculating element geometry, or inspecting client-side single-page app (SPA) state.

    Args:
        expression: JavaScript code, expression, or function to evaluate (e.g. 'document.title', 'window.scrollY', '() => localStorage.getItem("token")').
        arg: Optional JSON-serializable argument to pass into the evaluated function.
    """
    mgr = BrowserManager.get_instance()
    res = await mgr.evaluate(expression=expression, arg=arg)
    return json.dumps(res, indent=2, ensure_ascii=False)


@with_error_reporting("browser_console")
async def browser_console(
    level: Optional[str] = None,
    limit: int = 50,
    clear: bool = False,
) -> str:
    """Retrieve captured browser console messages, warnings, and uncaught runtime errors.

    Essential for debugging client-side JavaScript crashes, unhandled promise rejections,
    and API warning logs.

    Args:
        level: Optional log level filter ('error', 'warn', 'info', 'log', or 'all'). Default: 'all'.
        limit: Maximum number of recent log entries to return (default: 50, max: 200).
        clear: If True, clears the in-memory console buffer after reading.
    """
    mgr = BrowserManager.get_instance()
    res = await mgr.get_console_logs(level=level, limit=limit, clear=clear)
    return json.dumps(res, indent=2, ensure_ascii=False)


@with_error_reporting("browser_network")
async def browser_network(
    filter_type: Optional[str] = None,
    failed_only: bool = False,
    include_headers: bool = False,
    include_body: bool = False,
    limit: int = 50,
    clear: bool = False,
) -> str:
    """Capture and inspect HTTP network traffic, API calls, status codes, headers, and payloads.

    Allows external AI models to inspect fetch/XHR requests, trace failed API calls (4xx/5xx),
    and analyze payload responses.

    Args:
        filter_type: Optional resource filter ('all', 'api' / 'xhr' / 'fetch', 'document', 'script', 'stylesheet', 'image'). Default: 'all'.
        failed_only: If True, only returns failed requests or HTTP status codes >= 400.
        include_headers: If True, includes request and response headers.
        include_body: If True, includes captured response body (for XHR/fetch/JSON endpoints).
        limit: Maximum number of recent network requests to return (default: 50, max: 200).
        clear: If True, clears the in-memory network request buffer after reading.
    """
    mgr = BrowserManager.get_instance()
    res = await mgr.get_network_traffic(
        filter_type=filter_type,
        failed_only=failed_only,
        include_headers=include_headers,
        include_body=include_body,
        limit=limit,
        clear=clear,
    )
    return json.dumps(res, indent=2, ensure_ascii=False)


__all__ = [
    "BrowserManager",
    "has_gui_display",
    "safe_print",
    "browser_open",
    "browser_click",
    "browser_type",
    "browser_extract",
    "browser_screenshot",
    "browser_actions",
    "browser_evaluate",
    "browser_console",
    "browser_network",
    "browser_close",
]
