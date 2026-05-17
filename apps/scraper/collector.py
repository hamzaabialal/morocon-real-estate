"""Polite public-page collector for PropertyFinder.ma agency information."""
import json
import random
import re
import time
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from django.utils import timezone

from apps.scraper.models import CollectedAgency, CollectionRun


BASE_URL = "https://www.propertyfinder.ma"
SEARCH_URL_TEMPLATE = BASE_URL + "/fr/recherche?c=2&page={page}"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13.6; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
]


class PropertyFinderCollector:
    """Collect publicly available agency data from PropertyFinder.ma listing pages."""

    def __init__(self, proxy=None, delay_min=2, delay_max=5):
        self.proxy = proxy
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.client = httpx.Client(
            follow_redirects=True,
            timeout=30,
            proxy=proxy,
            headers={"Accept-Language": "fr,en;q=0.8,ar;q=0.6"},
        )

    def close(self):
        """Close the underlying HTTP client."""
        self.client.close()

    def fetch_page(self, url):
        """Fetch a page with random user-agent, jitter delay, and retry on throttling."""
        time.sleep(random.uniform(self.delay_min, self.delay_max))
        last_error = None
        for attempt in range(1, 4):
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            try:
                response = self.client.get(url, headers=headers)
                if response.status_code in {429, 503} and attempt < 3:
                    time.sleep(random.uniform(self.delay_min, self.delay_max) * attempt)
                    continue
                response.raise_for_status()
                return response.text
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < 3:
                    time.sleep(random.uniform(self.delay_min, self.delay_max) * attempt)
        raise last_error

    def parse_listing_urls(self, html):
        """Extract likely listing URLs from a search result page."""
        soup = BeautifulSoup(html, "html.parser")
        urls = set()
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            lowered = href.lower()
            if any(token in lowered for token in ["/acheter/", "/louer/", "annonce"]):
                absolute_url = urljoin(BASE_URL, href)
                if urlparse(absolute_url).netloc.endswith("propertyfinder.ma"):
                    urls.add(absolute_url.split("#")[0])
        return sorted(urls)

    def parse_agency(self, html, url):
        """Parse agency contact details from a listing page."""
        soup = BeautifulSoup(html, "html.parser")
        payload = self.extract_json_payloads(soup)
        text = soup.get_text(" ", strip=True)

        agency_data = {
            "name": self.first_text(
                soup,
                [
                    "[data-testid*=agency]",
                    "[class*=agency]",
                    "[class*=broker]",
                    "[class*=agent]",
                ],
            ),
            "phone": self.extract_phone(text),
            "whatsapp": self.extract_whatsapp(soup, text),
            "email": self.extract_email(text),
            "website": self.extract_website(soup),
            "logo_url": self.extract_logo(soup),
            "city_raw": self.extract_city(soup, text),
            "propertyfinder_id": self.extract_propertyfinder_id(url, payload),
            "source_url": url,
            "raw_data": {"url": url, "json_payloads": payload},
        }

        for item in payload:
            self.merge_json_agency_data(agency_data, item)

        return agency_data if agency_data.get("name") or agency_data.get("phone") else {}

    def run(self, max_pages=100):
        """Collect agencies from search result pages and persist raw records."""
        run = CollectionRun.objects.create(started_at=timezone.now(), status="running")
        try:
            seen_listing_urls = set()
            for page_number in range(1, max_pages + 1):
                search_url = SEARCH_URL_TEMPLATE.format(page=page_number)
                search_html = self.fetch_page(search_url)
                run.pages_visited += 1

                listing_urls = self.parse_listing_urls(search_html)
                for listing_url in listing_urls:
                    if listing_url in seen_listing_urls:
                        continue
                    seen_listing_urls.add(listing_url)
                    listing_html = self.fetch_page(listing_url)
                    agency_data = self.parse_agency(listing_html, listing_url)
                    if not agency_data:
                        continue
                    run.agencies_found += 1
                    _, created = CollectedAgency.objects.update_or_create(
                        propertyfinder_id=agency_data.get("propertyfinder_id"),
                        defaults=agency_data,
                    ) if agency_data.get("propertyfinder_id") else CollectedAgency.objects.get_or_create(
                        source_url=agency_data["source_url"],
                        defaults=agency_data,
                    )
                    if created:
                        run.agencies_new += 1

                run.save(update_fields=["pages_visited", "agencies_found", "agencies_new"])

            run.status = "completed"
            run.finished_at = timezone.now()
            run.save(update_fields=["status", "finished_at", "pages_visited", "agencies_found", "agencies_new"])
            return run
        except Exception as exc:
            run.status = "failed"
            run.error_message = str(exc)
            run.finished_at = timezone.now()
            run.save(update_fields=["status", "error_message", "finished_at"])
            raise
        finally:
            self.close()

    def extract_json_payloads(self, soup):
        """Extract JSON and JSON-LD payloads embedded in the page."""
        payloads = []
        for script in soup.find_all("script"):
            content = script.string or script.get_text()
            if not content:
                continue
            content = content.strip()
            if not content.startswith("{") and not content.startswith("["):
                continue
            try:
                payloads.append(json.loads(content))
            except json.JSONDecodeError:
                continue
        return payloads

    def merge_json_agency_data(self, agency_data, payload):
        """Fill missing fields from nested JSON payloads when obvious keys exist."""
        if isinstance(payload, list):
            for item in payload:
                self.merge_json_agency_data(agency_data, item)
            return
        if not isinstance(payload, dict):
            return
        keys = {str(key).lower(): key for key in payload.keys()}
        agency_data["name"] = agency_data["name"] or payload.get(keys.get("name", ""))
        agency_data["phone"] = agency_data["phone"] or payload.get(keys.get("phone", ""))
        agency_data["email"] = agency_data["email"] or payload.get(keys.get("email", ""))
        agency_data["website"] = agency_data["website"] or payload.get(keys.get("url", ""))
        for value in payload.values():
            if isinstance(value, (dict, list)):
                self.merge_json_agency_data(agency_data, value)

    def first_text(self, soup, selectors):
        """Return the first non-empty text for a list of CSS selectors."""
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(" ", strip=True)
                if text:
                    return text[:200]
        return None

    def extract_phone(self, text):
        """Extract a likely Moroccan phone number from page text."""
        match = re.search(r"(\+?212|0)\s?[5-7](?:[\s.-]?\d){8}", text)
        return re.sub(r"\s+", "", match.group(0)) if match else None

    def extract_whatsapp(self, soup, text):
        """Extract a WhatsApp phone number from links or page text."""
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            if "wa.me" in href or "whatsapp" in href.lower():
                match = re.search(r"(\+?212|0)?[5-7]\d{8}", href.replace(" ", ""))
                if match:
                    return match.group(0)
        return self.extract_phone(text)

    def extract_email(self, text):
        """Extract an email address from page text."""
        match = re.search(r"[\w.\-+]+@[\w.\-]+\.\w+", text)
        return match.group(0) if match else None

    def extract_website(self, soup):
        """Extract a likely agency website URL."""
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            if href.startswith("http") and "propertyfinder.ma" not in href:
                return href
        return None

    def extract_logo(self, soup):
        """Extract a likely agency logo image URL."""
        for image in soup.find_all("img"):
            alt = (image.get("alt") or "").lower()
            src = image.get("src")
            if src and any(token in alt for token in ["agency", "agence", "logo"]):
                return urljoin(BASE_URL, src)
        return None

    def extract_city(self, soup, text):
        """Extract a raw city value when page markup exposes one."""
        for selector in ["[data-testid*=location]", "[class*=location]", "[class*=city]"]:
            element = soup.select_one(selector)
            if element:
                city = element.get_text(" ", strip=True)
                if city:
                    return city[:120]
        for city in ["Casablanca", "Rabat", "Marrakech", "Tanger", "Agadir", "Fès"]:
            if city.lower() in text.lower():
                return city
        return ""

    def extract_propertyfinder_id(self, url, payload):
        """Extract a stable PropertyFinder identifier from URL or embedded payload."""
        for item in payload:
            found = self.find_key_recursive(item, {"id", "reference", "referenceid"})
            if found:
                return str(found)[:120]
        match = re.search(r"(\d{5,})", url)
        return match.group(1) if match else None

    def find_key_recursive(self, payload, key_names):
        """Find the first matching key recursively in nested JSON payloads."""
        if isinstance(payload, dict):
            for key, value in payload.items():
                if str(key).lower() in key_names and value:
                    return value
                nested = self.find_key_recursive(value, key_names)
                if nested:
                    return nested
        if isinstance(payload, list):
            for item in payload:
                nested = self.find_key_recursive(item, key_names)
                if nested:
                    return nested
        return None
