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
    "browser_close",
]
