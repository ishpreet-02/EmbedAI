"""
Website scraper — Playwright (headless browser) + BeautifulSoup (text extraction).
Crawls a website, finds all internal pages, and extracts clean readable text.

Link discovery strategies (tried in order):
  1. Standard <a href> crawling from the rendered page
  2. sitemap.xml discovery (fallback when crawling finds few links)
"""

import logging
import xml.etree.ElementTree as ET
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



# ── Sitemap Discovery ─────────────────────────────────────

async def _fetch_sitemap_urls(base_url: str, base_domain: str, base_path: str) -> list[str]:
    """
    Try to fetch and parse sitemap.xml for page URLs.
    Discovers sitemaps via:
      1. Direct URL (if user provided a sitemap link)
      2. robots.txt 'Sitemap: ...' directives
      3. Common paths (/sitemap.xml, /sitemap_index.xml, /sitemap/sitemap.xml)
    Handles standard urlsets and sitemap index files (<sitemapindex>).
    """
    parsed = urlparse(base_url)
    is_direct_sitemap = parsed.path.lower().endswith(".xml") or "sitemap" in parsed.path.lower()

    candidates: list[str] = []
    if is_direct_sitemap:
        candidates.append(base_url)

    std_candidates = [
        f"{parsed.scheme}://{parsed.netloc}/sitemap.xml",
        f"{parsed.scheme}://{parsed.netloc}/sitemap_index.xml",
        f"{parsed.scheme}://{parsed.netloc}/sitemap/sitemap.xml",
    ]

    all_urls: list[str] = []

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=6.0,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        },
    ) as client:
        # Check robots.txt for declared sitemaps
        try:
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            robots_resp = await client.get(robots_url)
            if robots_resp.status_code == 200:
                for line in robots_resp.text.splitlines():
                    line_clean = line.strip()
                    if line_clean.lower().startswith("sitemap:"):
                        sm_url = line_clean.split(":", 1)[1].strip()
                        if sm_url.startswith("http") and sm_url not in candidates:
                            candidates.append(sm_url)
        except Exception as e:
            logger.debug(f"[Scraper] robots.txt fetch failed: {e}")

        for std in std_candidates:
            if std not in candidates:
                candidates.append(std)

        for sitemap_url in candidates:
            try:
                response = await client.get(sitemap_url)
                if response.status_code != 200:
                    continue

                content_type = response.headers.get("content-type", "").lower()
                body = response.text.strip()

                # Ignore HTML fallback responses from Single Page Apps
                if "text/html" in content_type or body.lower().startswith("<!doctype") or body.lower().startswith("<html"):
                    continue

                sub_sitemaps, urls = _parse_sitemap_xml(body, base_domain, base_path)

                # If this was a sitemap index, fetch sub-sitemaps (up to 3)
                if sub_sitemaps and not urls:
                    logger.info(f"[Scraper] Found sitemap index with {len(sub_sitemaps)} sub-sitemaps at {sitemap_url}")
                    for sub_url in sub_sitemaps[:3]:
                        try:
                            sub_resp = await client.get(sub_url)
                            if sub_resp.status_code == 200:
                                _, sub_urls = _parse_sitemap_xml(sub_resp.text, base_domain, base_path)
                                urls.extend(sub_urls)
                                if len(urls) >= MAX_PAGES * 2:
                                    break
                        except Exception as sub_err:
                            logger.debug(f"[Scraper] Sub-sitemap fetch failed {sub_url}: {sub_err}")

                if urls:
                    logger.info(f"[Scraper] Found {len(urls)} URLs from {sitemap_url}")
                    all_urls.extend(urls)
                    break
            except Exception as e:
                logger.debug(f"[Scraper] Sitemap fetch failed for {sitemap_url}: {e}")
                continue

    # Deduplicate and cap
    seen = set()
    unique: list[str] = []
    for u in all_urls:
        normalized = u.split("#")[0].rstrip("/")
        if normalized not in seen:
            seen.add(normalized)
            unique.append(u)

    return unique[:MAX_PAGES * 2]


def _parse_sitemap_xml(xml_text: str, base_domain: str, base_path: str) -> tuple[list[str], list[str]]:
    """
    Parse XML text of a sitemap or sitemap index.
    Returns (sub_sitemaps, page_urls).
    """
    sub_sitemaps: list[str] = []
    urls: list[str] = []
    try:
        root = ET.fromstring(xml_text)
        ns = ""
        if root.tag.startswith("{"):
            ns = root.tag.split("}")[0] + "}"

        # 1. Sitemap index check
        for sm in root.findall(f".//{ns}sitemap"):
            loc = sm.find(f"{ns}loc")
            if loc is not None and loc.text:
                sub_sitemaps.append(loc.text.strip())

        # 2. Standard page URL check
        for url_elem in root.findall(f".//{ns}url"):
            loc = url_elem.find(f"{ns}loc")
            if loc is not None and loc.text:
                link = loc.text.strip()
                link_domain = _normalize_domain(urlparse(link).netloc)
                link_path = urlparse(link).path.rstrip("/")

                if (
                    link_domain == base_domain
                    and (not base_path or link_path.startswith(base_path))
                    and not _is_file_link(link)
                ):
                    urls.append(link)
    except ET.ParseError:
        logger.debug("[Scraper] Failed to parse sitemap XML")

    return sub_sitemaps, urls


# ── Main Scraper ──────────────────────────────────────────

async def scrape_website(url: str) -> list[dict]:
    """
    Scrape a website starting from the given URL.
    
    Discovery strategy (both are used together):
      1. Always fetch sitemap.xml first (cheap HTTP call) to seed the crawl queue
      2. Discover additional links via <a href> crawling on each visited page
    
    This ensures pages listed in the sitemap but not linked from the homepage
    are still scraped, dramatically improving coverage for JS-heavy sites.
    
    Returns a list of {"url": str, "title": str, "text": str} dicts.
    """
    pages = []
    visited = set()

    # Normalize the starting URL
    if not url.startswith("http"):
        url = f"https://{url}"

    parsed_start = urlparse(url)
    base_domain = _normalize_domain(parsed_start.netloc)
    is_direct_sitemap = parsed_start.path.lower().endswith(".xml") or "sitemap" in parsed_start.path.lower()
    base_path = "" if is_direct_sitemap else parsed_start.path.rstrip("/")

    # ── Step 1: Seed crawl queue from sitemap (always tried first) ────
    urls_to_visit = [] if is_direct_sitemap else [url]

    try:
        sitemap_urls = await _fetch_sitemap_urls(url, base_domain, base_path)
        if sitemap_urls:
            logger.info(f"[Scraper] Sitemap seeded {len(sitemap_urls)} URLs into crawl queue")
            start_normalized = url.split("#")[0].rstrip("/")
            for surl in sitemap_urls:
                surl_normalized = surl.split("#")[0].rstrip("/")
                if surl_normalized != start_normalized and surl_normalized not in urls_to_visit:
                    urls_to_visit.append(surl)
    except Exception as e:
        logger.debug(f"[Scraper] Sitemap pre-fetch failed (will rely on link crawling): {e}")

    # Fallback if user passed a direct sitemap URL but no URLs were parsed from it
    if not urls_to_visit:
        urls_to_visit = [f"{parsed_start.scheme}://{parsed_start.netloc}"]

    # ── Step 2: Crawl pages (Playwright) ──────────────────────────────
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

                # Discover additional internal links from the page
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
