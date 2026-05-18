"""Sarouty.ma agency directory scraping."""
import logging
import re
from urllib.parse import urljoin, urlparse

from asgiref.sync import sync_to_async
from bs4 import BeautifulSoup
from django.db import transaction

from apps.agencies.models import Agency
from apps.locations.models import City, Country
from apps.scraper.http_client import fetch_html

logger = logging.getLogger(__name__)

BASE_URL = "https://www.sarouty.ma/en"
DIRECTORY_URL = BASE_URL + "/trouver-une-agence/?page={page_num}"

CITY_ALIASES = {
    "casa": "Casablanca",
    "casablanca": "Casablanca",
    "dar el beida": "Casablanca",
    "dar-el-beida": "Casablanca",
    "rabat": "Rabat",
    "marrakesh": "Marrakech",
    "marrakech": "Marrakech",
    "marrakech medina": "Marrakech",
    "tanger": "Tanger",
    "tangier": "Tanger",
    "agadir": "Agadir",
    "fes": "Fes",
    "fès": "Fes",
    "fez": "Fes",
    "kenitra": "Kenitra",
    "kénitra": "Kenitra",
    "sale": "Sale",
    "salé": "Sale",
    "temara": "Temara",
    "témara": "Temara",
    "meknes": "Meknes",
    "meknès": "Meknes",
}

CARD_SELECTORS = [
    "[data-testid*=agency]",
    "[class*=agency]",
    "[class*=agence]",
    "[class*=broker]",
    "[class*=agent]",
    "article",
]

PROFILE_URL_PATTERNS = [
    re.compile(r"/trouver-une-agence/[^/?#]+", re.IGNORECASE),
    re.compile(r"/agenc[ey]/[^/?#]+", re.IGNORECASE),
    re.compile(r"/agent/[^/?#]+", re.IGNORECASE),
]


async def fetch_agency_directory_page(page_num: int) -> list[dict]:
    """Fetch and parse one Sarouty agency directory page."""
    url = DIRECTORY_URL.format(page_num=page_num)
    html = await fetch_html(url, use_playwright=False)
    if not html:
        return []

    try:
        soup = BeautifulSoup(html, "html.parser")
        agencies = []
        seen_urls = set()

        for card in _candidate_cards(soup):
            agency = _parse_agency_card(card)
            if not agency:
                continue
            profile_url = agency["sarouty_profile_url"]
            if profile_url in seen_urls:
                continue
            seen_urls.add(profile_url)
            agencies.append(agency)

        return agencies
    except Exception:
        logger.exception("Failed to parse Sarouty agency directory page %s", page_num)
        return []


async def scrape_all_agencies() -> dict:
    """Scrape all Sarouty agency directory pages and upsert Agency rows."""
    summary = {"total_found": 0, "created": 0, "updated": 0}
    page_num = 1

    while True:
        agencies = await fetch_agency_directory_page(page_num)
        if not agencies:
            break

        summary["total_found"] += len(agencies)
        for agency_data in agencies:
            created = await sync_to_async(_upsert_agency, thread_sensitive=True)(
                agency_data
            )
            if created:
                summary["created"] += 1
            else:
                summary["updated"] += 1

        page_num += 1

    return summary


def normalize_city_name(value: str | None) -> str:
    """Normalize city names using known Moroccan aliases."""
    if not value:
        return ""
    cleaned = re.sub(r"\s+", " ", value).strip()
    return CITY_ALIASES.get(cleaned.lower(), cleaned)


def _candidate_cards(soup: BeautifulSoup) -> list:
    cards = []
    for selector in CARD_SELECTORS:
        cards.extend(soup.select(selector))

    if cards:
        return cards

    anchors = []
    for anchor in soup.find_all("a", href=True):
        if _is_profile_href(anchor["href"]):
            anchors.append(anchor.parent or anchor)
    return anchors


def _parse_agency_card(card) -> dict | None:
    profile_anchor = _find_profile_anchor(card)
    if not profile_anchor:
        return None

    profile_url = urljoin(BASE_URL, profile_anchor["href"]).split("#")[0]
    name = _extract_name(card, profile_anchor)
    if not name:
        return None

    return {
        "name": name,
        "phone": _extract_phone(card.get_text(" ", strip=True)),
        "logo_url": _extract_logo(card),
        "sarouty_profile_url": profile_url,
        "sarouty_agency_id": _extract_agency_id(card, profile_url),
        "city": normalize_city_name(_extract_city(card)),
    }


def _find_profile_anchor(card):
    for anchor in card.find_all("a", href=True):
        if _is_profile_href(anchor["href"]):
            return anchor
    if getattr(card, "name", None) == "a" and card.get("href"):
        if _is_profile_href(card["href"]):
            return card
    return None


def _is_profile_href(href: str) -> bool:
    if not href:
        return False
    parsed = urlparse(urljoin(BASE_URL, href))
    if not parsed.netloc.endswith("sarouty.ma"):
        return False
    path = parsed.path.rstrip("/")
    if path in {"", "/trouver-une-agence"}:
        return False
    return any(pattern.search(path) for pattern in PROFILE_URL_PATTERNS)


def _extract_name(card, profile_anchor) -> str:
    for selector in ["h1", "h2", "h3", "[class*=name]", "[class*=title]"]:
        element = card.select_one(selector)
        if element:
            text = element.get_text(" ", strip=True)
            if text:
                return text[:200]

    image = card.find("img")
    if image and image.get("alt"):
        return image["alt"].replace("-Img.png", "").replace("_", " ").strip()[:200]

    return profile_anchor.get_text(" ", strip=True)[:200]


def _extract_phone(text: str) -> str | None:
    match = re.search(r"(\+?212|0)\s?[5-7](?:[\s.\-]?\d){8}", text)
    return re.sub(r"[\s.\-]", "", match.group(0)) if match else None


def _extract_logo(card) -> str | None:
    image = card.find("img")
    if not image:
        return None
    src = image.get("src") or image.get("data-src") or image.get("data-lazy-src")
    return urljoin(BASE_URL, src) if src else None


def _extract_agency_id(card, profile_url: str) -> str | None:
    for attr in ["data-agency-id", "data-id", "data-testid"]:
        value = card.get(attr)
        if value:
            return str(value)[:100]

    slug = urlparse(profile_url).path.rstrip("/").split("/")[-1]
    return slug[:100] if slug else None


def _extract_city(card) -> str:
    for selector in ["[class*=city]", "[class*=location]", "[data-testid*=location]"]:
        element = card.select_one(selector)
        if element:
            text = element.get_text(" ", strip=True)
            if text:
                return text[:120]

    text = card.get_text(" ", strip=True)
    for alias, canonical in CITY_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", text, re.IGNORECASE):
            return canonical
    return ""


@transaction.atomic
def _upsert_agency(agency_data: dict) -> bool:
    name = re.sub(r"\s+", " ", agency_data["name"]).strip()
    agency = Agency.objects.filter(name__iexact=name).first()
    created = agency is None
    if created:
        agency = Agency(name=name)

    agency.sarouty_agency_id = agency_data.get("sarouty_agency_id") or None
    agency.sarouty_profile_url = agency_data.get("sarouty_profile_url") or None
    agency.logo_url = agency_data.get("logo_url") or agency.logo_url
    if agency_data.get("phone") and not agency.phone:
        agency.phone = agency_data["phone"]

    city_name = agency_data.get("city")
    if city_name and not agency.city_id:
        country, _ = Country.objects.get_or_create(code="MA", defaults={"name": "Morocco"})
        city, _ = City.objects.get_or_create(
            name=city_name,
            country=country,
        )
        agency.city = city

    agency.save()
    return created
