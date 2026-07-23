"""
Website scraper — Playwright (headless browser) + BeautifulSoup (text extraction).
Crawls a website, finds all internal pages, and extracts clean readable text.
"""

import logging
from urllib.parse import urlparse
import httpx
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Tags that contain noise, not content
NOISE_TAGS = ["nav", "footer", "header", "script", "style", "noscript", "iframe", "svg"]

# Max pages to scrape per website (prevents infinite crawls)
MAX_PAGES = 20

# Timeout per page in milliseconds
PAGE_TIMEOUT = 15000
MIN_TEXT_LENGTH = 50


async def scrape_website(url: str) -> list[dict]:
    """
    Scrape a website starting from the given URL.
    
    1. Visits the URL with a headless Chromium browser
    2. Discovers all internal links on each page
    3. Extracts clean text using BeautifulSoup
    
    Returns a list of {"url": str, "title": str, "text": str} dicts.
    """
    pages = []
    visited = set()

    # Normalize the starting URL
    if not url.startswith("http"):
        url = f"https://{url}"

    parsed_start = urlparse(url)
    base_domain = _normalize_domain(parsed_start.netloc)
    base_path = parsed_start.path.rstrip("/")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-gpu",
                "--disable-extensions",
                "--disable-background-networking",
                "--disable-renderer-backgrounding",
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
        )

        async def block_heavy_assets(route):
            if route.request.resource_type in {"image", "media", "font"}:
                await route.abort()
            else:
                await route.continue_()

        await context.route("**/*", block_heavy_assets)

        # Start with the main URL
        urls_to_visit = [url]

        while urls_to_visit and len(pages) < MAX_PAGES:
            current_url = urls_to_visit.pop(0)

            # Skip if already visited
            normalized = current_url.split("#")[0].rstrip("/")
            if normalized in visited:
                continue
            visited.add(normalized)

            page = await context.new_page()
            try:
                logger.info(f"Scraping: {current_url}")
                response = await page.goto(
                    current_url,
                    wait_until="domcontentloaded",
                    timeout=PAGE_TIMEOUT,
                )

                if not response or response.status >= 400:
                    logger.warning(f"Skipping {current_url} — status {response.status if response else 'None'}")
                    fallback_page = await _fetch_static_page(current_url)
                    if fallback_page:
                        pages.append(fallback_page)
                    continue

                # Wait for the page to actually finish loading (network idle)
                try:
                    await page.wait_for_load_state("networkidle", timeout=5000)
                except:
                    await page.wait_for_timeout(1500)

                # Get the rendered HTML
                html = await page.content()

                # Extract clean text
                text, title = _extract_text(html)

                if text and len(text.strip()) > MIN_TEXT_LENGTH:
                    pages.append({
                        "url": current_url,
                        "title": title,
                        "text": text,
                    })
                    logger.info(f"  ✓ Extracted {len(text)} chars from: {title}")

                # Discover internal links
                if len(pages) < MAX_PAGES:
                    links = await page.eval_on_selector_all(
                        "a[href]",
                        "elements => elements.map(e => e.href)"
                    )
                    for link in links:
                        link_normalized = link.split("#")[0].rstrip("/")
                        link_domain = _normalize_domain(urlparse(link).netloc)
                        link_path = urlparse(link).path.rstrip("/")
                        if (
                            link_domain == base_domain
                            and link_path.startswith(base_path)
                            and link_normalized not in visited
                            and link_normalized not in urls_to_visit
                            and not _is_file_link(link)
                        ):
                            urls_to_visit.append(link)

            except Exception as e:
                logger.warning(f"Error scraping {current_url}: {e}")
                fallback_page = await _fetch_static_page(current_url)
                if fallback_page:
                    pages.append(fallback_page)
                continue
            finally:
                if not page.is_closed():
                    await page.close()

        await browser.close()

    logger.info(f"Scraping complete: {len(pages)} pages from {base_domain}")
    return pages


async def _fetch_static_page(url: str) -> dict | None:
    """Fallback for pages where Playwright navigation fails."""
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=15,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            },
        ) as client:
            response = await client.get(url)

        content_type = response.headers.get("content-type", "")
        if response.status_code >= 400 or "text/html" not in content_type:
            return None

        text, title = _extract_text(response.text)
        if text and len(text.strip()) > MIN_TEXT_LENGTH:
            logger.info(f"  ✓ Static fallback extracted {len(text)} chars from: {title}")
            return {
                "url": url,
                "title": title,
                "text": text,
            }
    except Exception as e:
        logger.warning(f"Static fallback failed for {url}: {e}")

    return None


def _extract_text(html: str) -> tuple[str, str]:
    """
    Extract clean readable text from HTML using BeautifulSoup.
    Removes navigation, footers, scripts, and other noise.
    Returns (text, title).
    """
    soup = BeautifulSoup(html, "lxml")

    # Get the page title
    title = soup.title.string.strip() if soup.title and soup.title.string else "Untitled"

    # Remove noise elements
    for tag in soup(NOISE_TAGS):
        tag.decompose()

    # Also remove elements with common noise class names
    for selector in [
        '[class*="cookie"]', '[class*="popup"]', '[class*="modal"]',
        '[class*="sidebar"]', '[class*="advertisement"]', '[id*="cookie"]',
        '[role="navigation"]', '[role="banner"]',
    ]:
        for el in soup.select(selector):
            el.decompose()

    # Extract text
    text = soup.get_text(separator=" ", strip=True)

    # Clean up whitespace
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    text = "\n".join(lines)

    return text, title


def _is_file_link(url: str) -> bool:
    """Check if a URL points to a file (PDF, image, etc.) rather than a page."""
    file_extensions = {
        ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
        ".mp4", ".mp3", ".zip", ".tar", ".gz", ".exe", ".dmg",
        ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    }
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in file_extensions)


def _normalize_domain(domain: str) -> str:
    return domain.lower().removeprefix("www.")
