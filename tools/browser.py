"""Browser Automation Tool powered by Playwright with Persistent User Profile & High-Performance Batch Execution.

Features:
- Self-contained portable storage inside shitcode-cli/.browsers
- Persistent user logins/cookies in .browser_profile/
- Automatic headed desktop window with VPS headless detection
- Lean Chromium defaults (silenced audio, background bloat disabled)
- Route interception (drops heavy tracking beacons & video ad networks)
- Deterministic smart locators (resolves by placeholder, label, role, text, or CSS)
- Token-efficient interactive accessibility catalog extraction (~300 tokens)
- Compound batch action execution (browser_actions) with real-time step CLI reporting and diagnostics
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.browser_installer import ensure_browser_installed, is_browser_ready
from core.reporter import with_error_reporting

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


def _safe_print(text: str = ""):
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
                except Exception as headed_err:
                    last_error = headed_err
                    if is_missing_binary_err(headed_err) and attempt == 0:
                        logger.info("Playwright binary missing during headed launch. Auto-healing...")
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
                    logger.info("Playwright binary missing during headless launch. Auto-healing...")
                    self._was_installed_on_demand = True
                    await asyncio.to_thread(ensure_browser_installed, force=True)
                    continue

        # Attempt B: Fall back to system installed Chrome or Edge channels
        logger.info("Standard Chromium launch failed, attempting system browser channels (Chrome / Edge)...")
        for ch in ["chrome", "msedge"]:
            if try_headed_first:
                try:
                    ctx = await _try_launch_driver(headless=False, channel=ch)
                    return ctx, False
                except Exception:
                    pass
            try:
                ctx = await _try_launch_driver(headless=True, channel=ch)
                return ctx, True
            except Exception:
                pass

        raise RuntimeError(f"Could not launch browser through Playwright or system channels: {last_error}")

    async def _smart_locate(self, target: str) -> Any:
        """Deterministically resolve an element locator using progressive heuristics."""
        page = self._page
        if not page:
            raise RuntimeError("No active browser session")

        target = target.strip()

        # 0. Tag-constrained text selector detection (e.g. 'button:has-text("Male")' or 'a:text("Link")')
        # If the model specifies a restrictive tag that does not exist in the DOM (e.g. dropdown options
        # that render as <div> or <span> instead of <button>), extract the inner text and locate flexibly.
        text_match = re.search(r':(?:has-text|text)\((["\']?)(.*?)\1\)', target, re.IGNORECASE)
        if text_match:
            try:
                exact_loc = page.locator(target).first
                if await exact_loc.count() > 0:
                    return exact_loc
            except Exception:
                pass

            inner_text = text_match.group(2).strip()
            if inner_text:
                for candidate in (
                    page.get_by_text(inner_text, exact=False).first,
                    page.get_by_role("option", name=inner_text, exact=False).first,
                    page.get_by_role("button", name=inner_text, exact=False).first,
                    page.locator(f":is(button, div, span, li, a, [role='option'], [role='button']):has-text({json.dumps(inner_text)})").first,
                ):
                    try:
                        if await candidate.count() > 0:
                            return candidate
                    except Exception:
                        pass

        # 1. Direct CSS / XPath / text engine selector
        if target.startswith(("#", ".", "//", "xpath=", "css=", "[", "text=")):
            return page.locator(target).first

        # 2. Try by Accessibility Role (including dropdown options, comboboxes, menuitems)
        for role in ("button", "link", "tab", "menuitem", "option", "combobox", "checkbox", "radio"):
            try:
                loc = page.get_by_role(role, name=target, exact=False).first
                if await loc.count() > 0:
                    return loc
            except Exception:
                pass

        # 3. Try by Placeholder (for input fields)
        try:
            loc = page.get_by_placeholder(target, exact=False).first
            if await loc.count() > 0:
                return loc
        except Exception:
            pass

        # 4. Try by Form Label (<label> or aria-label)
        try:
            loc = page.get_by_label(target, exact=False).first
            if await loc.count() > 0:
                return loc
        except Exception:
            pass

        # 5. Try by Visible Text across any element
        try:
            loc = page.get_by_text(target, exact=False).first
            if await loc.count() > 0:
                return loc
        except Exception:
            pass

        # 6. Fallback: Interactive elements matching text
        try:
            loc = page.locator(f":is(button, div, span, li, a, [role='option'], [role='button']):has-text({json.dumps(target)})").first
            if await loc.count() > 0:
                return loc
        except Exception:
            pass

        # Final Fallback: standard locator
        return page.locator(target).first

    async def _get_page_hints(self) -> Dict[str, Any]:
        """Extract available buttons, inputs, and dropdown options on the current page to assist failure diagnosis."""
        if not self._page:
            return {}
        try:
            hint_script = """
            () => {
                const buttons = Array.from(document.querySelectorAll('button, [role="button"], input[type="submit"], input[type="button"], a.btn, a.button'))
                    .map(b => (b.innerText || b.value || b.getAttribute('aria-label') || '').trim())
                    .filter(t => t.length > 0 && t.length < 40)
                    .slice(0, 10);
                const inputs = Array.from(document.querySelectorAll('input:not([type="hidden"]), textarea, select'))
                    .map(i => (i.placeholder || i.name || i.getAttribute('aria-label') || '').trim())
                    .filter(t => t.length > 0 && t.length < 40)
                    .slice(0, 10);
                const options = Array.from(document.querySelectorAll('[role="option"], [role="menuitem"], .cursor-pointer'))
                    .map(o => (o.innerText || '').trim())
                    .filter(t => t.length > 0 && t.length < 40 && !buttons.includes(t))
                    .slice(0, 10);
                return { buttons, inputs, options };
            }
            """
            return await self._page.evaluate(hint_script)
        except Exception:
            return {}

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

        # If browser already running, simply navigate the active tab
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

        # Initialize Playwright instance
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

                loc = await self._smart_locate(target)
                await loc.click(timeout=5000)
                await asyncio.sleep(0.3)

                return {
                    "success": True,
                    "url": self._page.url,
                    "title": await self._page.title(),
                    "message": f"Successfully clicked element '{target}'. Current URL: {self._page.url}",
                }
            except Exception as e:
                hints = await self._get_page_hints()
                hint_msg = f" Available buttons: {hints.get('buttons')}" if hints.get("buttons") else ""
                return {"success": False, "error": f"Failed to click '{selector}': {e}.{hint_msg}", "hints": hints}

    async def type_text(self, selector: str, text: str, press_enter: bool = False) -> Dict[str, Any]:
        """Type text into form fields or editable areas."""
        async with self._lock:
            if not self.is_active():
                return {"success": False, "error": "No active browser session. Call browser_open first."}

            try:
                loc = await self._smart_locate(selector)
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
                hints = await self._get_page_hints()
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
                        loc = await self._smart_locate(selector)
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
                loc = await self._smart_locate(selector)
                img_bytes = await loc.screenshot(**shot_opts)
            else:
                img_bytes = await self._page.screenshot(**shot_opts)

            with open(filepath, "wb") as f:
                f.write(img_bytes)

            return {
                "success": True,
                "filename": filename,
                "path": str(filepath),
                "size_bytes": len(img_bytes),
                "url": self._page.url if self._page else "",
                "message": f"Screenshot saved to {filepath.name} ({len(img_bytes) // 1024} KB)",
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

            # If browser is not open yet, open it using _open_internal (safe from deadlock)
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
            _safe_print(f"\n{CYAN}╭─ Browser Actions ({total} steps) ──────────────────────────────╮{RESET}")

            failed_step_idx = None
            failure_info = None

            for idx, item in enumerate(actions_list):
                if not isinstance(item, dict):
                    err_msg = f"Step {idx+1} is not a valid action dictionary: {item}"
                    _safe_print(f"{CYAN}│{RESET} {RED}[✗] {idx+1}. Invalid action format{RESET}")
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
                        _safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                        step_reports.append({"step": idx + 1, "action": "goto", "status": "ok", "url": url, "elapsed_ms": dur_ms})

                    elif action_type in ("fill", "type"):
                        target = item.get("target") or item.get("selector") or ""
                        value = item.get("value") or item.get("text") or ""
                        loc = await self._smart_locate(target)
                        await loc.fill(value, timeout=timeout)
                        if item.get("press_enter"):
                            await loc.press("Enter")
                        dur_ms = int((time.time() - t0) * 1000)
                        val_preview = value if len(value) <= 15 else value[:12] + "..."
                        desc = f"fill \"{target}\" -> \"{val_preview}\""
                        _safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                        step_reports.append({"step": idx + 1, "action": "fill", "status": "ok", "target": target, "elapsed_ms": dur_ms})

                    elif action_type == "fill_form":
                        fields = item.get("fields") or {}
                        filled_count = 0
                        for f_target, f_val in fields.items():
                            loc = await self._smart_locate(f_target)
                            await loc.fill(str(f_val), timeout=timeout)
                            filled_count += 1
                        dur_ms = int((time.time() - t0) * 1000)
                        desc = f"fill_form ({filled_count} fields)"
                        _safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                        step_reports.append({"step": idx + 1, "action": "fill_form", "status": "ok", "count": filled_count, "elapsed_ms": dur_ms})

                    elif action_type == "click":
                        target = item.get("target") or item.get("selector") or ""
                        loc = await self._smart_locate(target)
                        await loc.click(timeout=timeout)
                        dur_ms = int((time.time() - t0) * 1000)
                        desc = f"click \"{target}\""
                        _safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                        step_reports.append({"step": idx + 1, "action": "click", "status": "ok", "target": target, "elapsed_ms": dur_ms})

                    elif action_type == "select":
                        target = item.get("target") or item.get("selector") or ""
                        value = item.get("value") or ""
                        loc = await self._smart_locate(target)
                        is_native_select = False
                        try:
                            tag_name = await loc.evaluate("el => el.tagName")
                            is_native_select = (tag_name == "SELECT")
                        except Exception:
                            pass

                        if is_native_select:
                            await loc.select_option(value, timeout=timeout)
                        else:
                            # Custom select/combobox (React, Tailwind, Radix):
                            # Click trigger to open dropdown, then click the option
                            await loc.click(timeout=timeout)
                            await asyncio.sleep(0.15)
                            opt_loc = await self._smart_locate(value)
                            await opt_loc.click(timeout=timeout)

                        dur_ms = int((time.time() - t0) * 1000)
                        desc = f"select \"{target}\" -> \"{value}\""
                        _safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                        step_reports.append({"step": idx + 1, "action": "select", "status": "ok", "target": target, "value": value, "elapsed_ms": dur_ms})

                    elif action_type in ("wait_for", "assert_visible"):
                        target = item.get("target") or item.get("selector") or ""
                        loc = await self._smart_locate(target)
                        await loc.wait_for(state="visible", timeout=timeout)
                        dur_ms = int((time.time() - t0) * 1000)
                        desc = f"assert_visible \"{target}\""
                        _safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                        step_reports.append({"step": idx + 1, "action": "assert_visible", "status": "ok", "target": target, "elapsed_ms": dur_ms})

                    elif action_type == "extract_scoped":
                        target = item.get("selector") or item.get("target") or ""
                        loc = await self._smart_locate(target)
                        await loc.wait_for(state="attached", timeout=timeout)
                        text = await loc.inner_text()
                        dur_ms = int((time.time() - t0) * 1000)
                        clean_text = text.strip().replace("\n", " ")[:60]
                        desc = f"extract_scoped \"{target}\" -> \"{clean_text}\""
                        _safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                        extracted_data[target] = text.strip()
                        step_reports.append({"step": idx + 1, "action": "extract_scoped", "status": "ok", "target": target, "text": text.strip()[:1000], "elapsed_ms": dur_ms})

                    elif action_type in ("wait", "sleep"):
                        ms = item.get("ms", 500)
                        await asyncio.sleep(ms / 1000.0)
                        desc = f"wait {ms}ms"
                        _safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({ms}ms){RESET}")
                        step_reports.append({"step": idx + 1, "action": "wait", "status": "ok", "ms": ms})

                    elif action_type == "screenshot":
                        res = await self._screenshot_internal()
                        dur_ms = int((time.time() - t0) * 1000)
                        desc = f"screenshot ({res.get('filename')})"
                        _safe_print(f"{CYAN}│{RESET} {GREEN}[✓]{RESET} {idx+1}. {desc:<50} {DIM}({dur_ms}ms){RESET}")
                        step_reports.append({"step": idx + 1, "action": "screenshot", "status": "ok", "path": res.get("path"), "elapsed_ms": dur_ms})

                    else:
                        raise ValueError(f"Unknown browser action: '{action_type}'")

                except Exception as step_err:
                    dur_ms = int((time.time() - t0) * 1000)
                    target_repr = item.get("target") or item.get("selector") or item.get("url") or ""
                    desc = f"{action_type} \"{target_repr}\" -> FAILED"
                    _safe_print(f"{CYAN}│{RESET} {RED}[✗]{RESET} {idx+1}. {desc:<50} {RED}({dur_ms}ms){RESET}")

                    # Mark subsequent steps as skipped
                    for skip_idx in range(idx + 1, total):
                        skip_item = actions_list[skip_idx]
                        skip_act = skip_item.get("action", "step") if isinstance(skip_item, dict) else "step"
                        _safe_print(f"{CYAN}│{RESET} {DIM}[-] {skip_idx+1}. {skip_act} (Skipped){RESET}")

                    failed_step_idx = idx + 1
                    hints = await self._get_page_hints()
                    failure_info = {
                        "error": str(step_err),
                        "step": idx + 1,
                        "action": action_type,
                        "target": target_repr,
                        "elapsed_ms": dur_ms,
                        "page_hints": hints,
                    }
                    break

            _safe_print(f"{CYAN}╰──────────────────────────────────────────────────────────╯{RESET}")
            total_elapsed_ms = int((time.time() - start_total) * 1000)

            # Failure branch
            if failure_info:
                _safe_print(f"{RED}[!] Batch execution failed at Step {failed_step_idx} ('{failure_info['action']}'):{RESET}")
                _safe_print(f"    Target:  \"{failure_info['target']}\"")
                _safe_print(f"    Reason:  {failure_info['error']}")
                _safe_print(f"    URL:     {self._page.url if self._page else 'unknown'}")
                if failure_info.get("page_hints", {}).get("buttons"):
                    _safe_print(f"    Available buttons: {failure_info['page_hints']['buttons']}")
                if failure_info.get("page_hints", {}).get("options"):
                    _safe_print(f"    Available options: {failure_info['page_hints']['options']}")
                _safe_print()

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

            # All succeeded branch
            _safe_print(f"{GREEN}[+] Completed in {total_elapsed_ms}ms (All {total} steps succeeded){RESET}\n")
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


# =====================================================================
# MCP Tool Functions Registered onto Client
# =====================================================================

@with_error_reporting("browser_open")
async def browser_open(url: str, headless: Optional[bool] = None, fast_mode: bool = True) -> str:
    """Launch browser session and navigate to target URL.
    Attempts headed desktop window first; automatically falls back to headless mode on VPS/remote machines.
    """
    mgr = BrowserManager.get_instance()
    res = await mgr.open(url=url, headless=headless, fast_mode=fast_mode)
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
async def browser_screenshot(full_page: bool = False, selector: Optional[str] = None, format: str = "png") -> str:
    """Capture a screenshot of the active web page."""
    mgr = BrowserManager.get_instance()
    res = await mgr.screenshot(full_page=full_page, selector=selector, format=format)
    return json.dumps(res, indent=2, ensure_ascii=False)


@with_error_reporting("browser_actions")
async def browser_actions(actions: list) -> str:
    """Execute a batch of sequential browser actions in a single turn with live CLI feedback.
    Supported actions: goto, fill, fill_form, click, select, wait_for, assert_visible, extract_scoped, screenshot, wait.
    Tips:
    - For target elements, you can use text, label, placeholder, role, or CSS selector.
    - For custom dropdown options, menu items, or modals, prefer plain visible text (e.g. 'Male') rather than tag selectors like 'button:has-text(...)'.
    - For selecting options in dropdowns, you can use action 'select' with target (the select/dropdown) and value (the desired option), or batch two 'click' actions (click dropdown -> click option).
    """
    mgr = BrowserManager.get_instance()
    res = await mgr.actions(actions_list=actions)
    return json.dumps(res, indent=2, ensure_ascii=False)


@with_error_reporting("browser_close")
async def browser_close() -> str:
    """Close the active browser session and release local resources."""
    mgr = BrowserManager.get_instance()
    res = await mgr.close()
    return json.dumps(res, indent=2, ensure_ascii=False)
