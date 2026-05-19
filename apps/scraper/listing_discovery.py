"""Sarouty.ma listing id discovery from public index pages."""
import logging
import re
from urllib.parse import parse_qs, urlparse

from asgiref.sync import sync_to_async
from bs4 import BeautifulSoup

from apps.scraper.dedup import is_already_scraped

logger = logging.getLogger(__name__)

BASE_URL = "https://www.sarouty.ma/en"
SALE_INDEX_URL = "https://www.sarouty.ma/en/buy/"
RENT_INDEX_URL = "https://www.sarouty.ma/en/rent/"
INDEX_READY_SELECTOR = ".elementor-posts-container"
LISTING_ID_RE = re.compile(r"/property-details/\?listing_id=(\d+)")
DATA_LISTING_ID_RE = re.compile(r'data-listing-id=["\'](\d+)["\']')


async def fetch_listing_ids_from_page(url: str) -> list[int]:
    """Fetch one index page and return deduplicated Sarouty listing ids."""
    html = await fetch_index_html(url)
    if not html:
        return []

    return extract_listing_ids_from_html(html)


async def fetch_index_html(url: str) -> str | None:
    """Fetch a JS-rendered Sarouty index page with Playwright."""
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.goto(url, wait_until="networkidle", timeout=45000)
                try:
                    await page.wait_for_selector(INDEX_READY_SELECTOR, timeout=15000)
                except Exception:
                    logger.info(
                        "Sarouty index selector %s not visible on %s; using rendered body.",
                        INDEX_READY_SELECTOR,
                        url,
                    )
                return await page.content()
            finally:
                await browser.close()
    except Exception:
        logger.exception("Failed to fetch Sarouty index page %s", url)
        return None


def extract_listing_ids_from_html(html: str) -> list[int]:
    """Extract deduplicated listing ids from rendered index HTML."""
    soup = BeautifulSoup(html, "html.parser")
    ids = []
    seen = set()
    for listing_id_text in DATA_LISTING_ID_RE.findall(html):
        listing_id = int(listing_id_text)
        if listing_id in seen:
            continue
        seen.add(listing_id)
        ids.append(listing_id)

    for anchor in soup.find_all("a", href=True):
        listing_id = extract_listing_id(anchor["href"])
        if listing_id is None or listing_id in seen:
            continue
        seen.add(listing_id)
        ids.append(listing_id)
    return ids


def extract_index_links_from_html(html: str, mode: str = "buy") -> list[str]:
    """Extract likely listing index/category links from a rendered index page."""
    soup = BeautifulSoup(html, "html.parser")
    links = []
    seen = set()
    marker = f"/en/{mode}/"
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].split("#")[0]
        if marker not in href:
            continue
        if href.rstrip("/") in {SALE_INDEX_URL.rstrip("/"), RENT_INDEX_URL.rstrip("/")}:
            continue
        if not any(
            token in href
            for token in ["for-sale", "for-rent", "properties-for-sale", "properties-for-rent"]
        ):
            continue
        if href in seen:
            continue
        seen.add(href)
        links.append(href)
    return links


async def discover_all_listing_ids() -> list[int]:
    """Discover new listing ids from sale and rent index pages."""
    discovered_ids = []
    seen = set()

    for base_url, mode in [(SALE_INDEX_URL, "buy"), (RENT_INDEX_URL, "rent")]:
        for listing_id in await discover_section_listing_ids(base_url, mode):
            if listing_id not in seen:
                seen.add(listing_id)
                discovered_ids.append(listing_id)

    new_ids = []
    for listing_id in discovered_ids:
        already_scraped = await sync_to_async(is_already_scraped, thread_sensitive=True)(
            listing_id
        )
        if not already_scraped:
            new_ids.append(listing_id)
    return new_ids


async def discover_section_listing_ids(base_url: str, mode: str) -> list[int]:
    """Discover listing ids for one sale/rent section and linked sub-indexes."""
    section_ids = []
    seen_ids = set()
    seed_urls = [base_url]
    base_html = await fetch_index_html(base_url)
    if base_html:
        seed_urls.extend(extract_index_links_from_html(base_html, mode=mode))

    seen_urls = set()
    for seed_url in seed_urls:
        if seed_url in seen_urls:
            continue
        seen_urls.add(seed_url)
        page_num = 1
        while True:
            page_ids = await fetch_listing_ids_from_page(build_page_url(seed_url, page_num))
            if not page_ids:
                break
            for listing_id in page_ids:
                if listing_id in seen_ids:
                    continue
                seen_ids.add(listing_id)
                section_ids.append(listing_id)
            page_num += 1
    return section_ids


async def run_discovery(job) -> list[int]:
    """Run listing discovery and record the total new count on the job."""
    listing_ids = await discover_all_listing_ids()
    job.notes = f"Listing discovery found {len(listing_ids)} new Sarouty listing IDs."
    await sync_to_async(job.save, thread_sensitive=True)(update_fields=["notes"])
    return listing_ids


def extract_listing_id(href: str) -> int | None:
    """Extract a listing id from a Sarouty property-details href."""
    match = LISTING_ID_RE.search(href)
    if match:
        return int(match.group(1))

    parsed = urlparse(href)
    if parsed.path.rstrip("/") != "/property-details":
        return None

    listing_ids = parse_qs(parsed.query).get("listing_id")
    if not listing_ids or not listing_ids[0].isdigit():
        return None
    return int(listing_ids[0])


def build_page_url(base_url: str, page_num: int) -> str:
    """Build a Sarouty index page URL."""
    if page_num == 1:
        return base_url
    return f"{base_url.rstrip('/')}/page/{page_num}/"
