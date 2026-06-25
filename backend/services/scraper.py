"""
Website scraper — Playwright (headless browser) + BeautifulSoup (text extraction).
Crawls a website, finds all internal pages, and extracts clean readable text.
"""

import asyncio
import logging
from urllib.parse import urlparse, urljoin
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Tags that contain noise, not content
NOISE_TAGS = ["nav", "footer", "header", "script", "style", "noscript", "iframe", "svg"]

# Max pages to scrape per website (prevents infinite crawls)
MAX_PAGES = 20

# Timeout per page in milliseconds
PAGE_TIMEOUT = 15000


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
    base_domain = urlparse(url).netloc
    base_path = urlparse(url).path.rstrip("/")

    # Normalize the starting URL
    if not url.startswith("http"):
        url = f"https://{url}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-gpu",
                "--single-process",
                "--js-flags=--max-old-space-size=256"
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # Start with the main URL
        urls_to_visit = [url]

        while urls_to_visit and len(pages) < MAX_PAGES:
            current_url = urls_to_visit.pop(0)

            # Skip if already visited
            normalized = current_url.split("#")[0].rstrip("/")
            if normalized in visited:
                continue
            visited.add(normalized)

            try:
                logger.info(f"Scraping: {current_url}")
                response = await page.goto(
                    current_url,
                    wait_until="domcontentloaded",
                    timeout=PAGE_TIMEOUT,
                )

                if not response or response.status >= 400:
                    logger.warning(f"Skipping {current_url} — status {response.status if response else 'None'}")
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

                if text and len(text.strip()) > 50:
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
                        link_domain = urlparse(link).netloc
                        link_path = urlparse(link).path.rstrip("/")
                        if (
                            link_domain == base_domain
                            and link_path.startswith(base_path)
                            and link_normalized not in visited
                            and not _is_file_link(link)
                        ):
                            urls_to_visit.append(link)

            except Exception as e:
                logger.warning(f"Error scraping {current_url}: {e}")
                continue

        await browser.close()

    logger.info(f"Scraping complete: {len(pages)} pages from {base_domain}")
    return pages


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
