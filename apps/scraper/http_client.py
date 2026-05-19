"""HTTP and browser fetching helpers for Sarouty pages."""
import asyncio
import logging
import random

import httpx

from apps.scraper.rate_limiter import SAROUTY_RATE_LIMITER

logger = logging.getLogger(__name__)

PLAYWRIGHT_DELAY_MIN = 3.0
PLAYWRIGHT_DELAY_MAX = 7.0

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13.6; rv:126.0) "
    "Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) "
    "Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:125.0) "
    "Gecko/20100101 Firefox/125.0",
]


async def fetch_html(url: str, use_playwright: bool = False) -> str | None:
    """Fetch HTML from a URL, returning None on any failure."""
    try:
        await SAROUTY_RATE_LIMITER.acquire()
        await asyncio.sleep(random.uniform(PLAYWRIGHT_DELAY_MIN, PLAYWRIGHT_DELAY_MAX))

        if use_playwright:
            return await _fetch_with_playwright(url)
        return await _fetch_with_httpx(url)
    except Exception:
        logger.exception("Failed to fetch %s", url)
        return None


async def _fetch_with_httpx(url: str) -> str | None:
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "fr-MA,fr;q=0.9,ar;q=0.8",
    }
    try:
        async with httpx.AsyncClient(
            headers=headers,
            timeout=30,
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
        if response.status_code == 200:
            return response.text
        logger.warning("HTTP %s fetching %s", response.status_code, url)
        return None
    except Exception:
        logger.exception("HTTP fetch failed for %s", url)
        return None


async def _fetch_with_playwright(url: str) -> str | None:
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                page = await browser.new_page(
                    user_agent=random.choice(USER_AGENTS),
                    extra_http_headers={
                        "Accept-Language": "fr-MA,fr;q=0.9,ar;q=0.8"
                    },
                )
                await page.goto(url, wait_until="commit", timeout=60000)
                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=15000)
                except Exception:
                    logger.info("Timed out waiting for DOM content on %s", url)
                await page.wait_for_timeout(5000)
                return await page.content()
            finally:
                await browser.close()
    except Exception:
        logger.exception("Playwright fetch failed for %s", url)
        return None
