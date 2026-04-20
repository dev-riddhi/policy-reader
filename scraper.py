"""
scraper.py
----------
Asynchronous Playwright-based web scraper.
Optimized for speed: disables images/CSS/fonts and uses specialized selectors.
"""

import re
import logging
import asyncio
import sys
from urllib.parse import urljoin, urlparse

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup

# ── Fix for Windows NotImplementedError (ProactorEventLoop) ──────────────────
if sys.platform == 'win32':
    try:
        if not isinstance(asyncio.get_event_loop_policy(), asyncio.WindowsProactorEventLoopPolicy):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

# ── Logging ────────────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
PAGE_TIMEOUT_MS = 20_000          # Faster timeout for minimal latency
MAX_POLICY_CHARS = 50_000         # Efficient context window

PRIVACY_LINK_PATTERNS = [
    r"privacy[\s\-_]?policy",
    r"privacy[\s\-_]?notice",
    r"data[\s\-_]?policy",
    r"cookie[\s\-_]?policy",
    r"gdpr",
    r"privacy",
]

JUNK_TAGS = {
    "script", "style", "noscript", "header", "footer",
    "nav", "aside", "form", "button", "svg", "img", "iframe",
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _is_valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def _clean_html(html: str) -> str:
    """Fast HTML cleaning using BeautifulSoup."""
    soup = BeautifulSoup(html, "lxml") # Use lxml for speed if available

    for tag in soup(JUNK_TAGS):
        tag.decompose()

    text = soup.get_text(separator="\n")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines)


async def _find_privacy_link(page_html: str, base_url: str) -> str | None:
    """Scan for privacy links in the page source."""
    soup = BeautifulSoup(page_html, "lxml")
    pattern = re.compile("|".join(PRIVACY_LINK_PATTERNS), re.I)

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        text = a.get_text(strip=True)

        if pattern.search(href) or pattern.search(text):
            absolute = urljoin(base_url, href)
            if _is_valid_url(absolute):
                return absolute
    return None


async def _route_intercept(route):
    """Intercept requests to block unnecessary resources (CSS, Images, Fonts)."""
    if route.request.resource_type in ["image", "media", "font", "stylesheet"]:
        await route.abort()
    else:
        await route.continue_()


# ── Public API ─────────────────────────────────────────────────────────────────

class ScraperError(Exception):
    """Raised when scraping fails."""


async def scrape_privacy_policy_async(url: str) -> dict:
    """
    Asynchronous version of the scraper.
    Optimized for minimal latency.
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    if not _is_valid_url(url):
        raise ScraperError(f"Invalid URL: {url}")

    async with async_playwright() as pw:
        # ── Optimization: Use local chrome if playwright chromium is missing ──
        try:
            browser = await pw.chromium.launch(headless=True)
        except Exception as e:
            logger.warning(f"Default Chromium missing, trying system Chrome/Edge: {e}")
            try:
                # Fallback 1: Google Chrome
                browser = await pw.chromium.launch(headless=True, channel="chrome")
            except:
                try:
                    # Fallback 2: Microsoft Edge
                    browser = await pw.chromium.launch(headless=True, channel="msedge")
                except Exception as final_e:
                    raise ScraperError(
                        "Could not launch browser. Please run '.venv\\Scripts\\playwright install chromium' "
                        f"or install Google Chrome/Edge. Error: {final_e}"
                    )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        
        page = await context.new_page()
        # Latency optimization: Block heavy resources
        await page.route("**/*", _route_intercept)

        try:
            # ── Initial load ───────────────────────────────────────────────
            try:
                logger.info(f"Opening: {url}")
                await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
                # Brief wait for common JS rendering patterns
                await page.wait_for_timeout(1000)
                html = await page.content()
            except PlaywrightTimeoutError:
                raise ScraperError(f"Timed out loading {url}")
            except Exception as e:
                raise ScraperError(f"Error loading {url}: {str(e)}")

            current_url = page.url
            is_policy_page = bool(re.compile("|".join(PRIVACY_LINK_PATTERNS), re.I).search(current_url))

            source = "direct"
            policy_url = current_url

            if not is_policy_page:
                logger.info("Url not recognized as policy; searching...")
                discovery_url = await _find_privacy_link(html, current_url)
                
                if discovery_url:
                    source = "discovered"
                    policy_url = discovery_url
                    logger.info(f"Navigating to discovered policy: {policy_url}")
                    await page.goto(policy_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
                    await page.wait_for_timeout(1000)
                    html = await page.content()
                else:
                    # If not discovered, just clean whatever we have (maybe it is the policy)
                    pass

            # ── Extract and clean ──────────────────────────────────────────
            text = _clean_html(html)

            if not text or len(text) < 100:
                raise ScraperError("Failed to extract meaningful text from the page.")

            truncated = len(text) > MAX_POLICY_CHARS
            return {
                "policy_url": policy_url,
                "text": text[:MAX_POLICY_CHARS] if truncated else text,
                "truncated": truncated,
                "source": source,
            }

        finally:
            await context.close()
            await browser.close()
