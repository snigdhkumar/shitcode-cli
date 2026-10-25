"""Smart Element Locator and Progressive Matching Heuristics for ShitCode Browser.
Resolves targets by CSS/XPath, accessibility role, placeholder, label, visible text, and tag fallbacks.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict


async def smart_locate(page: Any, target: str) -> Any:
    """Resolve an element on the page using progressive heuristics."""
    target = target.strip()

    # 0. Handle pseudo-selectors like button:has-text("...") or :text("...") with resilient fallback
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


async def get_page_hints(page: Any) -> Dict[str, Any]:
    """Extract available buttons, inputs, and dropdown options on the current page to assist failure diagnosis."""
    if not page:
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
        return await page.evaluate(hint_script)
    except Exception:
        return {}
