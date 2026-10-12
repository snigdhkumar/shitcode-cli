"""Web content scraping and documentation extraction tools for MCP_NEW.
Extracts clean, readable markdown or text from web URLs using httpx and BeautifulSoup.
"""

from __future__ import annotations

import re
from typing import List, Optional, Union

import httpx
from core.reporter import with_error_reporting

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


def _html_to_markdown(html_content: str, char_limit: int = 50000) -> str:
    """Convert HTML string to clean, readable markdown."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, "html.parser")

        # Strip non-content elements
        for tag in soup(["script", "style", "nav", "footer", "aside", "noscript", "svg", "iframe"]):
            tag.decompose()

        # Extract title
        title = soup.title.string.strip() if soup.title and soup.title.string else ""

        # Extract main/article content if available
        main_content = soup.find("main") or soup.find("article") or soup.find("body") or soup

        # Convert headings
        for h in main_content.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            level = int(h.name[1])
            h.replace_with(f"\n\n{'#' * level} {h.get_text().strip()}\n\n")

        # Convert links
        for a in main_content.find_all("a", href=True):
            text = a.get_text().strip()
            href = a["href"]
            if text and href and not href.startswith(("javascript:", "#")):
                a.replace_with(f"[{text}]({href})")

        # Convert code blocks
        for pre in main_content.find_all("pre"):
            code_text = pre.get_text()
            pre.replace_with(f"\n```\n{code_text}\n```\n")

        # Convert inline code
        for code in main_content.find_all("code"):
            code.replace_with(f"`{code.get_text()}`")

        # Convert paragraphs & linebreaks
        for p in main_content.find_all("p"):
            p.replace_with(f"\n\n{p.get_text().strip()}\n\n")

        # Extract text and collapse multiple empty lines
        raw_text = main_content.get_text()
        clean_text = re.sub(r"\n{3,}", "\n\n", raw_text).strip()

        result = f"# {title}\n\n{clean_text}" if title else clean_text
        if len(result) > char_limit:
            result = result[:char_limit] + f"\n\n... [Content truncated at {char_limit} characters]"
        return result
    except Exception as e:
        # Fallback regex strip
        text = re.sub(r"<[^>]+>", " ", html_content)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:char_limit]


@with_error_reporting("web_extract")
async def web_extract(
    urls: Optional[Union[str, List[str]]] = None,
    format: str = "markdown",
    char_limit: int = 50000,
    url: Optional[str] = None,
) -> str:
    """Extract clean text or markdown content from one or more web URLs.

    Args:
        urls: A URL string or list of URLs to fetch and extract content from.
        format: Extraction format: 'markdown' or 'text' (default 'markdown').
        char_limit: Maximum characters to extract per URL (default 50000).
        url: Alias for a single URL string.
    """
    raw_target = urls if urls is not None else url
    if raw_target is None:
        return "Error: URL parameter ('url' or 'urls') is required."

    target_urls: List[str] = [raw_target] if isinstance(raw_target, str) else list(raw_target)

    results = []
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        timeout=30.0,
        follow_redirects=True,
    ) as client:
        for u in target_urls:
            url_str = str(u).strip()
            if not url_str.startswith(("http://", "https://")):
                results.append(f"### URL: {url_str}\nError: URL must begin with http:// or https://")
                continue

            try:
                resp = await client.get(url_str)
                resp.raise_for_status()
                md = _html_to_markdown(resp.text, char_limit=char_limit)
                results.append(f"### URL: {url_str} (Status: {resp.status_code})\n\n{md}")
            except httpx.HTTPStatusError as e:
                results.append(f"### URL: {url_str}\nHTTP error {e.response.status_code}: {e.response.reason_phrase}")
            except Exception as e:
                results.append(f"### URL: {url_str}\nFailed to fetch content: {e}")

    return "\n\n---\n\n".join(results)
