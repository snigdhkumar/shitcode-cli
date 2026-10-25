"""Browser Automation Manager powered by Playwright with Persistent User Profile & High-Performance Batch Execution.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.browser_installer import ensure_browser_installed, is_browser_ready
from tools.browser.locators import get_page_hints, smart_locate

logger = logging.getLogger("shitcode.tools.browser.manager")

# Workspace root & browser data directories
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
PROFILE_DIR = ROOT_DIR / ".browser_profile"
SCREENSHOTS_DIR = ROOT_DIR / "screenshots"


def has_gui_display() -> bool:
    """Detect if the current environment has a physical/desktop display available."""
    if sys.platform in ("win32", "darwin"):
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def safe_print(text: str = ""):
    """Print text safely handling Windows non-UTF8 charmap encodings."""
    try:
        print(text)
    except UnicodeEncodeError:
        try:
            safe_text = (
                text.replace("╭", "+")
                .replace("╮", "+")
                .replace("╰", "+")
                .replace("╯", "+")
                .replace("─", "-")
                .replace("│", "|")
                .replace("✓", "[v]")
                .replace("✗", "[x]")
            )
            print(safe_text)
        except Exception:
            pass


class BrowserManager:
    """Singleton controller managing the active Playwright browser session with persistent user profile."""

    _instance: Optional[BrowserManager] = None

    TRACKER_PATTERNS = (
        "google-analytics.com",
        "googletagmanager.com",
        "doubleclick.net",
        "connect.facebook.net",
        "facebook.com/tr",
        "hotjar.com",
        "segment.io",
        "adroll.com",
        "clarity.ms",
        "mixpanel.com",
        "criteo.net",
        "scorecardresearch.com",
        "taboola.com",
        "outbrain.com",
    )

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
        """Ensure Playwright package and browser binaries are ready."""
        if not is_browser_ready():
            success, msg = await asyncio.to_thread(ensure_browser_installed)
            if not success:
                return False, msg
            self._was_installed_on_demand = True
        return True, "Ready"

    async def _setup_route_interception(self, context: Any, fast_mode: bool = True):
        """Intercept network routes to drop heavy tracker beacons, analytics, and video ads."""
        if not fast_mode:
            return

        async def _route_handler(route: Any, request: Any):
            try:
                url_lower = request.url.lower()
                # 1. Abort known tracking & telemetry domains
                if any(p in url_lower for p in self.TRACKER_PATTERNS):
                    await route.abort()
                    return

                # 2. Abort video streaming bloat inside automated pages
                if request.resource_type in ("media",):
                    await route.abort()
                    return

                await route.continue_()
            except Exception:
                try:
                    await route.continue_()
                except Exception:
                    pass

        try:
            await context.route("**/*", _route_handler)
        except Exception as e:
            logger.debug(f"Route interception attach notice: {e}")

    async def _launch_browser(self, headless_preference: Optional[bool] = None) -> Tuple[Any, bool]:
        """Launch Chromium browser context using 3-tier resilient fallback."""
        gui_available = has_gui_display()
        try_headed_first = gui_available
        last_error: Optional[Exception] = None

        PROFILE_DIR.mkdir(parents=True, exist_ok=True)

        async def _try_launch_driver(headless: bool, channel: Optional[str] = None) -> Any:
            common_args = [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-extensions",
                "--disable-background-networking",
                "--disable-sync",
                "--disable-default-apps",
                "--mute-audio",
                "--disable-features=Translate,BackForwardCache,MediaRouter",
                "--disable-client-side-phishing-detection",
                "--metrics-recording-only",
                "--no-first-run",
            ]
            if not headless:
                common_args.extend([
                    "--start-maximized",
                    "--disable-blink-features=AutomationControlled",
                ])
                kwargs: Dict[str, Any] = {
                    "user_data_dir": str(PROFILE_DIR),
                    "headless": False,
                    "viewport": None,
                    "ignore_default_args": ["--enable-automation"],
                    "args": common_args,
                }
            else:
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
                except Exception as e:
                    last_error = e
                    if is_missing_binary_err(e) and attempt == 0:
                        logger.warning("Chromium executable missing. Auto-installing into .browsers/...")
                        ok, msg = await asyncio.to_thread(ensure_browser_installed)
                        if ok:
                            continue
                    try_headed_first = False

            # Headless fallback
            try:
                ctx = await _try_launch_driver(headless=True)
                return ctx, True
            except Exception as e:
                last_error = e
                if is_missing_binary_err(e) and attempt == 0:
                    logger.warning("Chromium executable missing in headless attempt. Auto-installing...")
                    ok, msg = await asyncio.to_thread(ensure_browser_installed)
                    if ok:
                        continue
                break

        # Attempt B: Fallback to System Chrome
        for channel in ("chrome", "msedge"):
            try:
                ctx = await _try_launch_driver(headless=not gui_available, channel=channel)
                return ctx, not gui_available
            except Exception as ch_err:
                logger.debug(f"Channel {channel} launch fallback notice: {ch_err}")

        raise RuntimeError(f"Could not launch browser: {last_error}")

    async def _open_internal(self, url: str, headless: Optional[bool] = None, fast_mode: bool = True) -> Dict[str, Any]:
        """Internal routine to navigate/open browser without acquiring self._lock (caller must manage lock)."""
        ready, msg = await self._ensure_ready()
        if not ready:
            return {"success": False, "error": f"Failed to initialize browser engine: {msg}"}

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return {"success": False, "error": "Playwright module not found after setup."}

        if not url.startswith(("http://", "https://", "about:", "file://")):
            url = "https://" + url

        if self.is_active():
            if has_gui_display() and self._is_headless:
                logger.info("Upgrading background headless session to visible desktop window...")
                await self._cleanup()
            else:
                try:
                    await self._page.goto(url, wait_until="domcontentloaded", timeout=15000)
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
                    cur = self._page.url
                    if cur and cur != "about:blank":
                        title = await self._page.title()
                        return {
                            "success": True,
                            "url": cur,
                            "title": title,
                            "mode": "headless" if self._is_headless else "headed (Visible Desktop Window)",
                            "profile": "persistent (.browser_profile)",
                            "message": f"Navigated existing tab to {cur} ('{title}') with notice: {e}",
                        }
                    logger.warning(f"Failed to navigate existing page, restarting browser: {e}")
                    await self._cleanup()

        if self._playwright is None:
            self._playwright = await async_playwright().start()

        try:
            self._context, self._is_headless = await self._launch_browser(headless_preference=headless)
            await self._setup_route_interception(self._context, fast_mode=fast_mode)
        except Exception as launch_err:
            await self._cleanup()
            return {"success": False, "error": f"Failed to launch browser: {launch_err}"}

        try:
            if self._context.pages:
                self._page = self._context.pages[0]
            else:
                self._page = await self._context.new_page()

            try:
                await self._page.goto(url, wait_until="domcontentloaded", timeout=15000)
            except Exception as goto_err:
                cur = self._page.url
                if not (cur and cur != "about:blank"):
                    raise goto_err

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
                res["message"] = f"[Notice: Chromium browser was downloaded on demand for first-time use] {res['message']}"
                self._was_installed_on_demand = False
            return res
        except Exception as nav_err:
            mode_str = "headless (VPS/Background)" if self._is_headless else "headed (Visible Desktop Window)"
            res = {
                "success": True,
                "url": url,
                "title": "Loaded",
                "mode": mode_str,
                "profile": "persistent (.browser_profile)",
                "warning": f"Opened with navigation notice: {nav_err}",
                "message": f"Browser opened to '{url}' (Notice: {nav_err})",
            }
            if self._was_installed_on_demand:
                res["installed_on_demand"] = True
                res["message"] = f"[Notice: Chromium browser was downloaded on demand for first-time use] {res['message']}"
                self._was_installed_on_demand = False
            return res

    async def open(self, url: str, headless: Optional[bool] = None, fast_mode: bool = True) -> Dict[str, Any]:
        """Launch browser session with persistent user profile and navigate to target URL."""
        async with self._lock:
            return await self._open_internal(url=url, headless=headless, fast_mode=fast_mode)

    async def click(self, selector: str, text: Optional[str] = None) -> Dict[str, Any]:
        """Click an interactive element on the page."""
        async with self._lock:
            if not self.is_active():
                return {"success": False, "error": "No active browser session. Call browser_open first."}

            try:
                target = selector
                if text and ":has-text" not in selector:
                    target = f"{selector}:has-text('{text}')"

                loc = await smart_locate(self._page, target)
                await loc.click(timeout=5000)
                await asyncio.sleep(0.3)

                return {
                    "success": True,
                    "url": self._page.url,
                    "title": await self._page.title(),
                    "message": f"Successfully clicked element '{target}'. Current URL: {self._page.url}",
                }
            except Exception as e:
                hints = await get_page_hints(self._page)
                hint_msg = f" Available buttons: {hints.get('buttons')}" if hints.get("buttons") else ""
                return {"success": False, "error": f"Failed to click '{selector}': {e}.{hint_msg}", "hints": hints}

    async def type_text(self, selector: str, text: str, press_enter: bool = False) -> Dict[str, Any]:
        """Type text into form fields or editable areas."""
        async with self._lock:
            if not self.is_active():
                return {"success": False, "error": "No active browser session. Call browser_open first."}

            try:
                loc = await smart_locate(self._page, selector)
                await loc.fill(text, timeout=5000)
                if press_enter:
                    await loc.press("Enter")
                    await asyncio.sleep(0.3)

                return {
                    "success": True,
                    "url": self._page.url,
                    "message": f"Typed text into '{selector}'" + (" and pressed Enter." if press_enter else "."),
                }
            except Exception as e:
                hints = await get_page_hints(self._page)
                hint_msg = f" Available inputs: {hints.get('inputs')}" if hints.get("inputs") else ""
                return {"success": False, "error": f"Failed to type into '{selector}': {e}.{hint_msg}", "hints": hints}

    async def extract(self, format: str = "markdown", selector: Optional[str] = None) -> Dict[str, Any]:
        """Extract clean readable text, interactive element catalog, or structure from the page."""
        async with self._lock:
            if not self.is_active():
                return {"success": False, "error": "No active browser session. Call browser_open first."}

            try:
                title = await self._page.title()
                current_url = self._page.url

                if format == "interactive":
                    interactive_script = """
                    () => {
                        const items = [];
                        const nodes = document.querySelectorAll('button, a[href], input, textarea, select, [role="button"], [role="link"]');
                        for (const el of nodes) {
                            if (el.offsetParent === null && el.offsetWidth === 0 && el.offsetHeight === 0) continue;
                            const tag = el.tagName.toLowerCase();
                            let name = (el.innerText || el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.name || el.value || '').trim();
                            name = name.replace(/\\s+/g, ' ').substring(0, 50);
                            if (!name && tag === 'a') continue;

                            let sel = '';
                            if (el.id) sel = '#' + el.id;
                            else if (el.name) sel = `${tag}[name="${el.name}"]`;
                            else if (el.placeholder) sel = `${tag}[placeholder="${el.placeholder}"]`;
                            else if (name) sel = `${tag}:has-text("${name.substring(0, 25)}")`;
                            else sel = tag;

                            items.push({
                                tag: tag,
                                type: el.type || undefined,
                                name: name,
                                selector: sel
                            });
                            if (items.length >= 60) break;
                        }
                        return items;
                    }
                    """
                    elements = await self._page.evaluate(interactive_script)
                    return {
                        "success": True,
                        "url": current_url,
                        "title": title,
                        "format": "interactive",
                        "total_elements": len(elements),
                        "interactive_elements": elements,
                    }

                if format == "html":
                    if selector:
                        el = await self._page.query_selector(selector)
                        content = await el.inner_html() if el else "Element not found"
                    else:
                        content = await self._page.content()
                    return {"success": True, "url": current_url, "title": title, "content": content[:20000]}

                if selector:
                    try:
                        loc = await smart_locate(self._page, selector)
                        await loc.wait_for(state="attached", timeout=3000)
                        text = await loc.inner_text()
                        return {
                            "success": True,
                            "url": current_url,
                            "title": title,
                            "scoped_selector": selector,
                            "content": text.strip()[:10000],
                        }
                    except Exception:
                        pass

                extract_script = """
                (sel) => {
                    const root = sel ? document.querySelector(sel) : document.body;
                    if (!root) return 'Selected element not found';

                    const clone = root.cloneNode(true);
                    const removeSelectors = ['script', 'style', 'svg', 'noscript', 'iframe'];
                    removeSelectors.forEach(s => clone.querySelectorAll(s).forEach(el => el.remove()));

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

    async def _screenshot_internal(self, full_page: bool = False, selector: Optional[str] = None, format: str = "png") -> Dict[str, Any]:
        """Internal screenshot routine without acquiring self._lock (caller must manage lock)."""
        if not self.is_active():
            return {"success": False, "error": "No active browser session. Call browser_open first."}

        try:
            screenshots_dir = ROOT_DIR / "screenshots"
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            ext = "jpg" if format.lower() in ("jpeg", "jpg") else "png"
            filename = f"screenshot_{int(time.time())}.{ext}"
            filepath = screenshots_dir / filename

            shot_opts: Dict[str, Any] = {"full_page": full_page}
            if ext == "jpg":
                shot_opts["type"] = "jpeg"
                shot_opts["quality"] = 80

            if selector:
                loc = await smart_locate(self._page, selector)
                img_bytes = await loc.screenshot(**shot_opts)
            else:
                img_bytes = await self._page.screenshot(**shot_opts)

            with open(filepath, "wb") as f:
                f.write(img_bytes)

            try:
                from tools.media import optimize_image_for_vision
                opt_bytes, opt_mime, opt_note = optimize_image_for_vision(img_bytes, max_dimension=1280, quality=75)
            except Exception:
                opt_bytes, opt_mime, opt_note = img_bytes, ("image/jpeg" if ext == "jpg" else "image/png"), f"{len(img_bytes) // 1024} KB"

            b64_data = base64.b64encode(opt_bytes).decode("ascii")
            page_url = self._page.url if self._page else ""

            return {
                "success": True,
                "filename": filename,
                "path": str(filepath),
                "size_bytes": len(img_bytes),
                "url": page_url,
                "b64_data": b64_data,
                "mime_type": opt_mime,
                "message": f"Screenshot saved to {filepath.name} ({len(img_bytes) // 1024} KB raw, vision payload: {opt_note})",
                "content": [
                    {
                        "type": "text",
                        "text": f"Screenshot captured from {page_url or 'active page'} (saved locally to {filepath.name}, vision payload: {opt_note})."
                    },
                    {
                        "type": "image",
                        "data": b64_data,
                        "mimeType": opt_mime
                    }
                ]
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to take screenshot: {e}"}

    async def screenshot(self, full_page: bool = False, selector: Optional[str] = None, format: str = "png") -> Dict[str, Any]:
        """Capture screenshot and save to workspace screenshots directory."""
        async with self._lock:
            return await self._screenshot_internal(full_page=full_page, selector=selector, format=format)

    async def actions(self, actions_list: list) -> Dict[str, Any]:
        """Execute a batch of sequential browser actions with live CLI reporting and failure diagnostics."""
        async with self._lock:
            ready, msg = await self._ensure_ready()
            if not ready:
                return {"success": False, "error": f"Failed to initialize browser engine: {msg}"}

            if not actions_list or not isinstance(actions_list, list):
                return {"success": False, "error": "Parameter 'actions' must be a non-empty list of action objects."}

            if not self.is_active():
                first_url = None
                for a in actions_list:
                    if isinstance(a, dict) and a.get("action") == "goto" and a.get("url"):
                        first_url = a.get("url")
                        break
                init_res = await self._open_internal(first_url or "https://google.com")
                if not init_res.get("success"):
                    return {"success": False, "error": f"Failed to start browser for batch actions: {init_res.get('error')}"}

            total = len(actions_list)
            step_reports: List[Dict[str, Any]] = []
            extracted_data: Dict[str, Any] = {}
            start_total = time.time()

            from ui.theme import BOLD, CYAN, DIM, GREEN, RED, RESET, YELLOW
            safe_print(f"\n{CYAN}╭─ Browser Actions ({total} steps) ──────────────────────────────╮{RESET}")

            failed_step_idx = None
            failure_info = None
            last_screenshot: Optional[Dict[str, Any]] = None

            for idx, item in enumerate(actions_list):
                if not isinstance(item, dict):
                    err_msg = f"Step {idx+1} is not a valid action dictionary: {item}"
                    safe_print(f"{CYAN}│{RESET} {RED}[✗] {idx+1}. Invalid action format{RESET}")
                    failed_step_idx = idx + 1
                    failure_info = {"error": err_msg, "step": idx + 1, "action": "invalid", "target": "format"}
                    break

                action_type = item.get("action", "").lower().strip()
                timeout = item.get("timeout", 3000)
                t0 = time.time()

                try:
                    if action_type == "goto":
                        url = item.get("url") or item.get("target") or "https://google.com"
                        if not url.startswith(("http://", "https://", "about:", "file://")):
                            url = "https://" + url
                        await self._page.goto(url, wait_until="domcontentloaded", timeout=timeout if timeout > 5000 else 15000)
                        dur_ms = int((time.time() - t0) * 1000)
                        desc = f"goto {url}"
                        safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                        step_reports.append({"step": idx + 1, "action": "goto", "status": "ok", "url": url, "elapsed_ms": dur_ms})

                    elif action_type in ("fill", "type"):
                        target = item.get("target") or item.get("selector") or ""
                        value = item.get("value") or item.get("text") or ""
                        loc = await smart_locate(self._page, target)
                        await loc.fill(value, timeout=timeout)
                        if item.get("press_enter"):
                            await loc.press("Enter")
                        dur_ms = int((time.time() - t0) * 1000)
                        val_preview = value if len(value) <= 15 else value[:12] + "..."
                        desc = f"fill \"{target}\" -> \"{val_preview}\""
                        safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                        step_reports.append({"step": idx + 1, "action": "fill", "status": "ok", "target": target, "elapsed_ms": dur_ms})

                    elif action_type == "fill_form":
                        fields = item.get("fields") or {}
                        filled_count = 0
                        for f_target, f_val in fields.items():
                            loc = await smart_locate(self._page, f_target)
                            await loc.fill(str(f_val), timeout=timeout)
                            filled_count += 1
                        dur_ms = int((time.time() - t0) * 1000)
                        desc = f"fill_form ({filled_count} fields)"
                        safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                        step_reports.append({"step": idx + 1, "action": "fill_form", "status": "ok", "count": filled_count, "elapsed_ms": dur_ms})

                    elif action_type == "click":
                        target = item.get("target") or item.get("selector") or ""
                        loc = await smart_locate(self._page, target)
                        await loc.click(timeout=timeout)
                        dur_ms = int((time.time() - t0) * 1000)
                        desc = f"click \"{target}\""
                        safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                        step_reports.append({"step": idx + 1, "action": "click", "status": "ok", "target": target, "elapsed_ms": dur_ms})

                    elif action_type == "select":
                        target = item.get("target") or item.get("selector") or ""
                        val = item.get("value") or item.get("text") or ""
                        loc = await smart_locate(self._page, target)
                        try:
                            await loc.select_option(value=val, timeout=timeout)
                        except Exception:
                            try:
                                await loc.select_option(label=val, timeout=timeout)
                            except Exception:
                                await loc.click(timeout=timeout)
                                opt_loc = await smart_locate(self._page, val)
                                await opt_loc.click(timeout=timeout)

                        dur_ms = int((time.time() - t0) * 1000)
                        desc = f"select \"{target}\" -> \"{val}\""
                        safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                        step_reports.append({"step": idx + 1, "action": "select", "status": "ok", "target": target, "value": val, "elapsed_ms": dur_ms})

                    elif action_type in ("wait_for", "assert_visible"):
                        target = item.get("target") or item.get("selector") or ""
                        loc = await smart_locate(self._page, target)
                        await loc.wait_for(state="visible", timeout=timeout if timeout > 3000 else 5000)
                        dur_ms = int((time.time() - t0) * 1000)
                        desc = f"{action_type} \"{target}\""
                        safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                        step_reports.append({"step": idx + 1, "action": action_type, "status": "ok", "target": target, "elapsed_ms": dur_ms})

                    elif action_type == "extract_scoped":
                        target = item.get("target") or item.get("selector") or ""
                        loc = await smart_locate(self._page, target)
                        text = await loc.inner_text(timeout=timeout)
                        dur_ms = int((time.time() - t0) * 1000)
                        clean_text = text.strip()[:20] + "..." if len(text.strip()) > 20 else text.strip()
                        desc = f"extract_scoped \"{target}\" -> \"{clean_text}\""
                        safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                        extracted_data[target] = text.strip()
                        step_reports.append({"step": idx + 1, "action": "extract_scoped", "status": "ok", "target": target, "text": text.strip()[:1000], "elapsed_ms": dur_ms})

                    elif action_type in ("wait", "sleep"):
                        ms = item.get("ms", 500)
                        await asyncio.sleep(ms / 1000.0)
                        desc = f"wait {ms}ms"
                        safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({ms}ms){RESET}")
                        step_reports.append({"step": idx + 1, "action": "wait", "status": "ok", "ms": ms})

                    elif action_type == "screenshot":
                        res = await self._screenshot_internal()
                        if res.get("success"):
                            last_screenshot = res
                        dur_ms = int((time.time() - t0) * 1000)
                        desc = f"screenshot ({res.get('filename')})"
                        safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                        step_reports.append({"step": idx + 1, "action": "screenshot", "status": "ok", "path": res.get("path"), "elapsed_ms": dur_ms})

                    else:
                        raise ValueError(f"Unknown browser action: '{action_type}'")

                except Exception as step_err:
                    dur_ms = int((time.time() - t0) * 1000)
                    target_repr = item.get("target") or item.get("selector") or item.get("url") or ""
                    desc = f"{action_type} \"{target_repr}\" -> FAILED"
                    safe_print(f"{CYAN}│{RESET} {RED}[✗]{RESET} {idx+1}. {desc:<50} {RED}({dur_ms}ms){RESET}")

                    for skip_idx in range(idx + 1, total):
                        skip_item = actions_list[skip_idx]
                        skip_act = skip_item.get("action", "step") if isinstance(skip_item, dict) else "step"
                        safe_print(f"{CYAN}│{RESET} {DIM}[-] {skip_idx+1}. {skip_act} (Skipped){RESET}")

                    failed_step_idx = idx + 1
                    hints = await get_page_hints(self._page)
                    failure_info = {
                        "error": str(step_err),
                        "step": idx + 1,
                        "action": action_type,
                        "target": target_repr,
                        "elapsed_ms": dur_ms,
                        "page_hints": hints,
                    }
                    break

            safe_print(f"{CYAN}╰──────────────────────────────────────────────────────────╯{RESET}")
            total_elapsed_ms = int((time.time() - start_total) * 1000)

            if failure_info:
                safe_print(f"{RED}[!] Batch execution failed at Step {failed_step_idx} ('{failure_info['action']}'):{RESET}")
                safe_print(f"    Target:  \"{failure_info['target']}\"")
                safe_print(f"    Reason:  {failure_info['error']}")
                safe_print(f"    URL:     {self._page.url if self._page else 'unknown'}")
                if failure_info.get("page_hints", {}).get("buttons"):
                    safe_print(f"    Available buttons: {failure_info['page_hints']['buttons']}")
                if failure_info.get("page_hints", {}).get("options"):
                    safe_print(f"    Available options: {failure_info['page_hints']['options']}")
                safe_print()

                hint_str = ""
                if failure_info.get("page_hints", {}).get("buttons"):
                    hint_str = f" Available buttons on page: {failure_info['page_hints']['buttons']}."
                if failure_info.get("page_hints", {}).get("options"):
                    hint_str += f" Available options on page: {failure_info['page_hints']['options']}."
                if failure_info.get("page_hints", {}).get("inputs"):
                    hint_str += f" Available inputs on page: {failure_info['page_hints']['inputs']}."

                return {
                    "success": False,
                    "failed_step": failed_step_idx,
                    "failed_action": failure_info["action"],
                    "target": failure_info["target"],
                    "error": f"Step {failed_step_idx} ('{failure_info['action']}') failed: {failure_info['error']}.{hint_str}",
                    "current_url": self._page.url if self._page else "",
                    "completed_steps": len(step_reports),
                    "total_steps": total,
                    "page_hints": failure_info.get("page_hints", {}),
                    "step_reports": step_reports,
                    "elapsed_ms": total_elapsed_ms,
                }

            safe_print(f"{GREEN}[+] Completed in {total_elapsed_ms}ms (All {total} steps succeeded){RESET}\n")
            title = await self._page.title() if self._page else ""
            res_dict: Dict[str, Any] = {
                "success": True,
                "message": f"All {total} browser actions executed successfully in {total_elapsed_ms}ms.",
                "total_steps": total,
                "completed_steps": total,
                "current_url": self._page.url if self._page else "",
                "title": title,
                "elapsed_ms": total_elapsed_ms,
                "step_reports": step_reports,
            }
            if extracted_data:
                res_dict["extracted"] = extracted_data
            if last_screenshot and "content" in last_screenshot:
                res_dict["content"] = last_screenshot["content"]
            return res_dict

    async def close(self) -> Dict[str, Any]:
        """Close the active browser session, flushing state to persistent profile."""
        async with self._lock:
            return await self._cleanup()

    async def _cleanup(self) -> Dict[str, Any]:
        """Internal cleanup closing pages, context, and driver."""
        try:
            if self._context:
                await self._context.close()
        except Exception as e:
            logger.debug(f"Context close error: {e}")

        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.debug(f"Playwright stop error: {e}")

        self._page = None
        self._context = None
        self._playwright = None
        return {"success": True, "message": "Browser session closed successfully (user profile saved)."}
