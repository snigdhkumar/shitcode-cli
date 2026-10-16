"""Browser automation and web interaction tool for ShitCode CLI.
Uses Playwright with automated Chromium.
Headless fallback: attempts headed desktop window first; seamlessly falls back to headless mode on remote/VPS servers.
Lazy on-demand installation: does not require Playwright/Chromium until first browser use.
"""

from __future__ import annotations

import asyncio
import base64
import html
import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from core.reporter import with_error_reporting
import os
import sys
from core.browser_installer import ensure_browser_installed, is_browser_ready

logger = logging.getLogger("shitcode.tools.browser")

# Workspace root & browser data directories
ROOT_DIR = Path(__file__).resolve().parent.parent
PROFILE_DIR = ROOT_DIR / ".browser_profile"
SCREENSHOTS_DIR = ROOT_DIR / "screenshots"


def has_gui_display() -> bool:
    """Detect if the current environment has a physical/desktop display available."""
    if sys.platform in ("win32", "darwin"):
        return True
    # Linux / Unix: check X11 or Wayland display environment variables
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


class BrowserManager:
    """Singleton controller managing the active Playwright browser session with persistent user profile."""

    _instance: Optional[BrowserManager] = None

    def __init__(self):
        self._playwright: Optional[Any] = None
        self._context: Optional[Any] = None
        self._page: Optional[Any] = None
        self._is_headless: bool = False
        self._was_installed_on_demand: bool = False
        self._lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> BrowserManager:
        if cls._instance is None:
            cls._instance = BrowserManager()
        return cls._instance

    def is_active(self) -> bool:
        return self._page is not None and not self._page.is_closed()

    async def _ensure_ready(self) -> Tuple[bool, str]:
        """Verify playwright & chromium are available in .browsers, downloading on demand if needed."""
        if not is_browser_ready():
            self._was_installed_on_demand = True
            success, msg = await asyncio.to_thread(ensure_browser_installed)
            if not success:
                return False, msg
        return True, "Ready"

    async def _launch_browser(self, headless_preference: Optional[bool] = None) -> Tuple[Any, bool]:
        """Launch browser using persistent context with 3-tier fallback and desktop appearance.
        
        Tier 1: Playwright automated Chromium in .browsers/ with persistent user profile.
        Tier 2: Auto-healing if missing executable error, runs installer and retries.
        Tier 3: Fallback to system installed Chrome or Edge (no ms-playwright binaries needed).
        """
        gui_available = has_gui_display()
        # On desktop systems with a screen (Windows, macOS, Linux with DISPLAY):
        # ALWAYS prioritize a visible, maximized desktop window (just like Antigravity IDE).
        # On remote VPS / servers without a GUI display:
        # Automatically launch in headless mode without display errors.
        try_headed_first = gui_available
        last_error: Optional[Exception] = None

        PROFILE_DIR.mkdir(parents=True, exist_ok=True)

        async def _try_launch_driver(headless: bool, channel: Optional[str] = None) -> Any:
            common_args = [
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ]
            if not headless:
                # Desktop mode: maximized window, standard flags, normal appearance
                common_args.extend([
                    "--start-maximized",
                    "--disable-blink-features=AutomationControlled",
                ])
                kwargs: Dict[str, Any] = {
                    "user_data_dir": str(PROFILE_DIR),
                    "headless": False,
                    "viewport": None,  # Full desktop window size
                    "ignore_default_args": ["--enable-automation"],
                    "args": common_args,
                }
            else:
                # Headless mode for remote / VPS servers
                kwargs: Dict[str, Any] = {
                    "user_data_dir": str(PROFILE_DIR),
                    "headless": True,
                    "viewport": {"width": 1280, "height": 800},
                    "args": common_args,
                }

            if channel:
                kwargs["channel"] = channel

            return await self._playwright.chromium.launch_persistent_context(**kwargs)

        def is_missing_binary_err(err: Exception) -> bool:
            msg = str(err).lower()
            return "executable doesn't exist" in msg or "playwright install" in msg or "run 'playwright" in msg

        # Attempt A: Standard Playwright Chromium in .browsers with auto-healing
        for attempt in range(2):
            if try_headed_first:
                try:
                    ctx = await _try_launch_driver(headless=False)
                    return ctx, False
                except Exception as headed_err:
                    last_error = headed_err
                    if is_missing_binary_err(headed_err) and attempt == 0:
                        logger.info("Playwright binary missing during headed launch. Auto-healing with ensure_browser_installed(force=True)...")
                        self._was_installed_on_demand = True
                        await asyncio.to_thread(ensure_browser_installed, force=True)
                        continue
                    logger.info(f"Headed launch failed ({headed_err}), attempting headless...")

            try:
                ctx = await _try_launch_driver(headless=True)
                return ctx, True
            except Exception as headless_err:
                last_error = headless_err
                if is_missing_binary_err(headless_err) and attempt == 0:
                    logger.info("Playwright binary missing during headless launch. Auto-healing with ensure_browser_installed(force=True)...")
                    self._was_installed_on_demand = True
                    await asyncio.to_thread(ensure_browser_installed, force=True)
                    continue

        # Attempt B: Fall back to system installed Chrome or Edge channels
        logger.info("Standard Chromium launch failed, attempting system browser channels (Chrome / Edge)...")
        for ch in ["chrome", "msedge"]:
            if try_headed_first:
                try:
                    ctx = await _try_launch_driver(headless=False, channel=ch)
                    logger.info(f"Successfully launched system browser channel '{ch}' (headed).")
                    return ctx, False
                except Exception:
                    pass
            try:
                ctx = await _try_launch_driver(headless=True, channel=ch)
                logger.info(f"Successfully launched system browser channel '{ch}' (headless).")
                return ctx, True
            except Exception:
                pass

        raise RuntimeError(f"Could not launch browser through Playwright or system channels: {last_error}")

    async def open(self, url: str, headless: Optional[bool] = None) -> Dict[str, Any]:
        """Launch browser session with persistent user profile and navigate to target URL."""
        async with self._lock:
            ready, msg = await self._ensure_ready()
            if not ready:
                return {"success": False, "error": f"Failed to initialize browser engine: {msg}"}

            try:
                from playwright.async_api import async_playwright
            except ImportError:
                return {"success": False, "error": "Playwright module not found after setup."}

            if not url.startswith(("http://", "https://", "about:", "file://")):
                url = "https://" + url

            # If browser already running, simply navigate the active tab
            if self.is_active():
                # If running on desktop GUI but session is currently invisible headless,
                # close headless session and reopen as a visible desktop window!
                if has_gui_display() and self._is_headless:
                    logger.info("Upgrading background headless session to visible desktop window...")
                    await self._cleanup()
                else:
                    try:
                        await self._page.goto(url, wait_until="domcontentloaded", timeout=20000)
                        title = await self._page.title()
                        return {
                            "success": True,
                            "url": self._page.url,
                            "title": title,
                            "mode": "headless" if self._is_headless else "headed (Visible Desktop Window)",
                            "profile": "persistent (.browser_profile)",
                            "message": f"Navigated existing tab to {self._page.url} ('{title}')",
                        }
                    except Exception as e:
                        logger.warning(f"Failed to navigate existing page, restarting browser: {e}")
                        await self._cleanup()

            # Initialize Playwright instance
            if self._playwright is None:
                self._playwright = await async_playwright().start()

            try:
                self._context, self._is_headless = await self._launch_browser(headless_preference=headless)
            except Exception as launch_err:
                await self._cleanup()
                return {"success": False, "error": f"Failed to launch browser: {launch_err}"}

            try:
                # Reuse the primary page created with persistent context or open a new one
                if self._context.pages:
                    self._page = self._context.pages[0]
                else:
                    self._page = await self._context.new_page()

                await self._page.goto(url, wait_until="domcontentloaded", timeout=25000)
                title = await self._page.title()

                mode_str = "headless (VPS/Background)" if self._is_headless else "headed (Visible Desktop Window)"
                res: Dict[str, Any] = {
                    "success": True,
                    "url": self._page.url,
                    "title": title,
                    "mode": mode_str,
                    "profile": "persistent (.browser_profile)",
                    "message": f"Browser launched in {mode_str} with persistent profile and opened {self._page.url} ('{title}')",
                }
                if self._was_installed_on_demand:
                    res["installed_on_demand"] = True
                    res["install_notice"] = "Chromium browser engine was downloaded into shitcode-cli/.browsers/ on demand."
                    self._was_installed_on_demand = False
                return res
            except Exception as nav_err:
                res = {
                    "success": True,
                    "url": url,
                    "title": "Loaded",
                    "mode": "headless" if self._is_headless else "headed",
                    "profile": "persistent (.browser_profile)",
                    "warning": f"Opened with navigation notice: {nav_err}",
                }
                if self._was_installed_on_demand:
                    res["installed_on_demand"] = True
                    self._was_installed_on_demand = False
                return res

    async def click(self, selector: str, text: Optional[str] = None) -> Dict[str, Any]:
        """Click an interactive element on the page."""
        async with self._lock:
            if not self.is_active():
                return {"success": False, "error": "No active browser session. Call browser_open first."}

            try:
                target = selector
                if text and ":has-text" not in selector:
                    target = f"{selector}:has-text('{text}')"

                # Wait for element and click
                await self._page.wait_for_selector(target, timeout=8000)
                await self._page.click(target, timeout=8000)
                # Wait briefly for DOM or URL transition
                await asyncio.sleep(0.5)

                return {
                    "success": True,
                    "url": self._page.url,
                    "title": await self._page.title(),
                    "message": f"Successfully clicked element '{target}'. Current URL: {self._page.url}",
                }
            except Exception as e:
                return {"success": False, "error": f"Failed to click '{selector}': {e}"}

    async def type_text(self, selector: str, text: str, press_enter: bool = False) -> Dict[str, Any]:
        """Type text into form fields or editable areas."""
        async with self._lock:
            if not self.is_active():
                return {"success": False, "error": "No active browser session. Call browser_open first."}

            try:
                await self._page.wait_for_selector(selector, timeout=8000)
                await self._page.fill(selector, text, timeout=8000)
                if press_enter:
                    await self._page.press(selector, "Enter")
                    await asyncio.sleep(0.5)

                return {
                    "success": True,
                    "url": self._page.url,
                    "message": f"Typed text into '{selector}'" + (" and pressed Enter." if press_enter else "."),
                }
            except Exception as e:
                return {"success": False, "error": f"Failed to type into '{selector}': {e}"}

    async def extract(self, format: str = "markdown", selector: Optional[str] = None) -> Dict[str, Any]:
        """Extract clean readable text or structure from the page."""
        async with self._lock:
            if not self.is_active():
                return {"success": False, "error": "No active browser session. Call browser_open first."}

            try:
                title = await self._page.title()
                current_url = self._page.url

                if format == "html":
                    if selector:
                        el = await self._page.query_selector(selector)
                        content = await el.inner_html() if el else "Element not found"
                    else:
                        content = await self._page.content()
                    return {"success": True, "url": current_url, "title": title, "content": content[:20000]}

                # Token-efficient Markdown extraction
                extract_script = """
                (sel) => {
                    const root = sel ? document.querySelector(sel) : document.body;
                    if (!root) return 'Selected element not found';

                    // Clone to strip non-visual bloat
                    const clone = root.cloneNode(true);
                    const removeSelectors = ['script', 'style', 'svg', 'noscript', 'iframe'];
                    removeSelectors.forEach(s => clone.querySelectorAll(s).forEach(el => el.remove()));

                    // Extract text with readable headings
                    let text = clone.innerText || clone.textContent || '';
                    return text.replace(/\\n{3,}/g, '\\n\\n').trim();
                }
                """
                raw_text = await self._page.evaluate(extract_script, selector)
                clean_text = raw_text.strip() if raw_text else "(Page has no readable text)"

                header = f"# {title}\n**URL:** {current_url}\n\n---\n\n"
                return {
                    "success": True,
                    "url": current_url,
                    "title": title,
                    "content": header + clean_text[:15000],
                }
            except Exception as e:
                return {"success": False, "error": f"Failed to extract content: {e}"}

    async def screenshot(self, full_page: bool = False, selector: Optional[str] = None) -> Dict[str, Any]:
        """Capture screenshot and save to workspace screenshots directory."""
        async with self._lock:
            if not self.is_active():
                return {"success": False, "error": "No active browser session. Call browser_open first."}

            try:
                screenshots_dir = ROOT_DIR / "screenshots"
                screenshots_dir.mkdir(parents=True, exist_ok=True)
                filename = f"screenshot_{int(time.time())}.png"
                filepath = screenshots_dir / filename

                if selector:
                    el = await self._page.query_selector(selector)
                    if not el:
                        return {"success": False, "error": f"Element '{selector}' not found for screenshot."}
                    img_bytes = await el.screenshot()
                else:
                    img_bytes = await self._page.screenshot(full_page=full_page)

                filepath.write_bytes(img_bytes)
                b64_data = base64.b64encode(img_bytes).decode("ascii")

                return {
                    "success": True,
                    "file_path": str(filepath).replace("\\", "/"),
                    "url": self._page.url,
                    "title": await self._page.title(),
                    "base64_preview": f"data:image/png;base64,{b64_data[:60]}...({len(img_bytes)} bytes)",
                    "message": f"Screenshot saved to {filepath.name} ({len(img_bytes)} bytes)",
                }
            except Exception as e:
                return {"success": False, "error": f"Failed to capture screenshot: {e}"}

    async def close(self) -> Dict[str, Any]:
        """Close browser context and clean up resources."""
        async with self._lock:
            return await self._cleanup()

    async def _cleanup(self) -> Dict[str, Any]:
        try:
            if self._page and not self._page.is_closed():
                await self._page.close()
        except Exception:
            pass

        try:
            if self._context:
                await self._context.close()
        except Exception:
            pass

        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass

        self._page = None
        self._context = None
        self._playwright = None
        return {"success": True, "message": "Browser session closed successfully (user profile saved)."}


# =====================================================================
# MCP Tool Functions Registered onto Client
# =====================================================================

@with_error_reporting("browser_open")
async def browser_open(url: str, headless: Optional[bool] = None) -> str:
    """Launch browser session and navigate to target URL.
    Attempts headed desktop window first; automatically falls back to headless mode on VPS/remote machines.
    """
    mgr = BrowserManager.get_instance()
    res = await mgr.open(url=url, headless=headless)
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
    """Extract clean, token-efficient Markdown or text from the active web page."""
    mgr = BrowserManager.get_instance()
    res = await mgr.extract(format=format, selector=selector)
    if res.get("success") and "content" in res:
        return res["content"]
    return json.dumps(res, indent=2, ensure_ascii=False)


@with_error_reporting("browser_screenshot")
async def browser_screenshot(full_page: bool = False, selector: Optional[str] = None) -> str:
    """Capture a screenshot of the active web page."""
    mgr = BrowserManager.get_instance()
    res = await mgr.screenshot(full_page=full_page, selector=selector)
    return json.dumps(res, indent=2, ensure_ascii=False)


@with_error_reporting("browser_close")
async def browser_close() -> str:
    """Close the active browser session and release local resources."""
    mgr = BrowserManager.get_instance()
    res = await mgr.close()
    return json.dumps(res, indent=2, ensure_ascii=False)
