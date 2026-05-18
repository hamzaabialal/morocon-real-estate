"""Parser for individual Sarouty.ma listing pages."""
import json
import logging
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from html import unescape
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.sarouty.ma/en"
SAROUTY_SUPPORT_PHONE = "212520506262"
REAL_AGENCY_BAD_KEYWORDS = [
    "sarouty",
    "details",
    "d\u00e9tails",
    "photos, prix",
    "informations",
    "property details",
    "trouver une agence",
    "find an agency",
]
BAD_AGENCY_KEYWORDS = ["sarouty", "détails", "immobilier", "photos, prix", "informations"]
BAD_DESCRIPTION_PHRASES = [
    "consultez les détails",
    "consultez les details",
    "consultez les détails complets",
    "consultez les details complets",
    "real estate agent",
    "full profile",
    "connect with trusted experts",
]


@dataclass
class SaroutyListing:
    sarouty_id: int
    price: Decimal | None
    property_type: str
    listing_type: str
    area: Decimal | None
    rooms: int | None
    bathrooms: int | None
    floor: int | None
    total_floors: int | None
    construction_year: int | None
    furnished: bool
    city_raw: str
    neighborhood_raw: str
    main_address: str
    latitude: Decimal | None
    longitude: Decimal | None
    description: str
    amenities: list[str]
    photo_urls: list[str]
    agency_name: str
    agency_phone: str | None
    agency_whatsapp: str | None
    agency_logo_url: str | None
    agency_profile_url: str | None


def parse_listing_html(html: str, listing_id: int) -> SaroutyListing | None:
    """Parse a Sarouty listing page into structured data."""
    try:
        # Detect Sarouty's "Property not available" empty page.
        if (
            "Property not available" in html
            or "property you're looking for isn't available" in html
        ):
            return None

        if not html or len(html.strip()) < 100:
            return None

        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)
        payloads = _json_payloads(soup)
        json_ld = _extract_from_json_ld(soup) or {}

        price = _extract_price(soup, text, payloads, json_ld)
        area = _extract_area(soup, text, payloads, json_ld)
        if price is None and area is None:
            return None

        latitude, longitude = _extract_coordinates(soup, payloads, json_ld)
        city_raw, neighborhood_raw = _extract_location_parts(
            soup, text, payloads, json_ld
        )

        listing = SaroutyListing(
            sarouty_id=listing_id,
            price=price,
            property_type=_extract_property_type(soup, text, payloads, json_ld),
            listing_type=_extract_listing_type(soup, text, payloads, json_ld),
            area=area,
            rooms=_extract_labeled_int(text, ["chambre", "pieces", "pièces", "rooms"]),
            bathrooms=_extract_labeled_int(
                text, ["salles de bain", "salle de bain", "bain", "bathrooms", "bathroom", "bath"]
            ),
            floor=_extract_floor(text)[0],
            total_floors=_extract_floor(text)[1],
            construction_year=_extract_year(text),
            furnished=_extract_furnished(text),
            city_raw=city_raw,
            neighborhood_raw=neighborhood_raw,
            main_address=_extract_address(soup, city_raw, neighborhood_raw, json_ld),
            latitude=latitude,
            longitude=longitude,
            description=_extract_description(soup, payloads, json_ld),
            amenities=_extract_amenities(soup),
            photo_urls=_extract_photo_urls(soup, payloads),
            agency_name=_extract_agency_name(soup, payloads),
            agency_phone=_extract_phone(soup, text),
            agency_whatsapp=_extract_whatsapp(soup),
            agency_logo_url=_extract_agency_logo(soup),
            agency_profile_url=_extract_agency_profile_url(soup),
        )
        return listing
    except Exception:
        logger.exception("Failed to parse Sarouty listing %s", listing_id)
        return None


def data_quality_ok(parsed) -> bool:
    """Returns True only if the parsed data looks like real listing content."""
    if parsed is None:
        return False
    if not parsed.price or parsed.price == 0:
        return False
    if not parsed.agency_name:
        return False
    if _normalize_phone(parsed.agency_name):
        return False
    if any(kw in parsed.agency_name.lower() for kw in REAL_AGENCY_BAD_KEYWORDS):
        return False
    if not parsed.description:
        return False
    if any(phrase in parsed.description.lower() for phrase in BAD_DESCRIPTION_PHRASES):
        return False
    if parsed.main_address and len(parsed.main_address) > 200:
        return False
    return True


def parse_listing_api_payload(payload: dict, listing_id: int) -> SaroutyListing | None:
    """Parse Sarouty's public property API payload into a listing object."""
    try:
        data = payload.get("data", payload)
        if isinstance(data, dict) and "data" in data:
            data = data["data"]
        if not isinstance(data, dict):
            return None

        location = data.get("location") or {}
        agent_company = data.get("agent_company") or {}
        agent_user = data.get("agent_user") or {}
        city = str(location.get("url_city_slug") or "").replace("-", " ").title()
        neighborhood = location.get("name_primary") or ""
        description = _clean_api_text(
            data.get("property_text_en")
            or data.get("property_text_fr")
            or data.get("property_text_ar")
        )
        title = _clean_api_text(
            data.get("property_title_en")
            or data.get("property_title_fr")
            or data.get("property_title_ar")
        )
        address = data.get("property_address") or ", ".join(
            part for part in [neighborhood, city] if part
        )
        images = [
            image.get("property_image_url")
            for image in data.get("images", [])
            if image.get("property_image_url")
        ]
        agency_name = (
            agent_company.get("agent_company_name")
            or agent_user.get("agent_user_name")
            or ""
        )
        phone = (
            agent_user.get("agent_user_phone")
            or agent_company.get("agent_company_phone")
            or agent_company.get("agent_company_phone2")
        )
        whatsapp = agent_user.get("agent_user_whatsapp_phone") or phone
        lat = _parse_decimal(
            str(
                data.get("property_latitude")
                or location.get("coordinates_lat")
                or ""
            )
        )
        lng = _parse_decimal(
            str(
                data.get("property_longitude")
                or location.get("coordinates_lon")
                or ""
            )
        )
        if lat == 0:
            lat = _parse_decimal(str(location.get("coordinates_lat") or ""))
        if lng == 0:
            lng = _parse_decimal(str(location.get("coordinates_lon") or ""))

        return SaroutyListing(
            sarouty_id=listing_id,
            price=_parse_decimal(str(data.get("property_price") or "")),
            property_type=str(
                data.get("property_housing_type")
                or data.get("property_type")
                or ""
            ),
            listing_type=_api_listing_type(data),
            area=_parse_decimal(str(data.get("property_sqft") or "")),
            rooms=_api_int(data.get("total_bedroom")),
            bathrooms=_api_int(data.get("total_bathroom")),
            floor=_api_int(data.get("property_floor")),
            total_floors=_api_int(data.get("property_floors_number")),
            construction_year=_api_int(data.get("property_build_year")),
            furnished=str(data.get("property_furnished") or "").upper() == "YES",
            city_raw=city,
            neighborhood_raw=str(neighborhood or ""),
            main_address=str(address or "")[:255],
            latitude=lat,
            longitude=lng,
            description=description or title,
            amenities=[],
            photo_urls=images,
            agency_name=str(agency_name or ""),
            agency_phone=_normalize_phone(str(phone or "")),
            agency_whatsapp=_normalize_phone(str(whatsapp or "")),
            agency_logo_url=agent_company.get("agent_company_logo"),
            agency_profile_url=None,
        )
    except Exception:
        logger.exception("Failed to parse Sarouty API payload %s", listing_id)
        return None


def _json_payloads(soup: BeautifulSoup) -> list:
    payloads = []
    for script in soup.find_all("script"):
        content = script.string or script.get_text()
        if not content:
            continue
        content = content.strip()
        if content.startswith("window.__") and "{" in content:
            content = content[content.find("{") :]
        if not content.startswith(("{", "[")):
            continue
        try:
            payloads.append(json.loads(content))
        except json.JSONDecodeError:
            continue
    return payloads


def _extract_from_json_ld(soup):
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            graph = data if isinstance(data, dict) else {}
            if "@graph" in graph:
                for item in graph["@graph"]:
                    if item.get("@type") in (
                        "Product",
                        "RealEstateListing",
                        "Offer",
                        "Place",
                    ):
                        return item
            if graph.get("@type") in ("Product", "RealEstateListing", "Offer"):
                return graph
        except Exception:
            continue
    return None


def _extract_price(
    soup: BeautifulSoup,
    text: str,
    payloads: list,
    json_ld: dict | None = None,
) -> Decimal | None:
    for value in _json_ld_values(json_ld, ["price", "lowPrice", "highPrice"]):
        price = _parse_decimal(str(value))
        if price:
            return price
    element = soup.find(attrs={"data-testid": re.compile(r"price", re.I)})
    if element:
        price = _parse_price_text(element.get_text(" ", strip=True))
        if price:
            return price

    for selector in ["[class*=price]"]:
        element = soup.select_one(selector)
        if element:
            price = _parse_price_text(element.get_text(" ", strip=True))
            if price:
                return price
    for value in _find_values(payloads, {"price", "amount"}):
        price = _parse_decimal(str(value))
        if price:
            return price
    for element in soup.find_all(["span", "div", "p", "h3", "h4", "h5"]):
        price = _parse_price_text(element.get_text(" ", strip=True))
        if price:
            return price
    return _parse_price_text(text)


def _parse_price_text(value: str) -> Decimal | None:
    match = re.search(r"([\d\s,.]+)\s*(?:DH|MAD|Dh)", value or "", re.I)
    if not match:
        return None
    cleaned = (
        match.group(1)
        .replace("DH", "")
        .replace("MAD", "")
        .replace("Dh", "")
        .replace(" ", "")
        .replace(",", "")
    )
    return _parse_decimal(cleaned)


def _extract_area(
    soup: BeautifulSoup,
    text: str,
    payloads: list,
    json_ld: dict | None = None,
) -> Decimal | None:
    for value in _json_ld_values(json_ld, ["floorSize", "size", "area"]):
        area = _parse_json_ld_area(value)
        if area:
            return area
    area_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:m²|m2|sqm)", text, re.I)
    if area_match:
        return _parse_decimal(area_match.group(1))
    for value in _find_values(payloads, {"area", "surface", "size"}):
        area = _parse_decimal(str(value))
        if area:
            return area
    return None


def _parse_decimal(value: str) -> Decimal | None:
    cleaned = re.sub(r"[^\d.,-]", "", value or "")
    if not cleaned:
        return None
    sign = "-" if cleaned.startswith("-") else ""
    cleaned = cleaned.replace("-", "")
    cleaned = cleaned.replace(" ", "").replace(",", ".")
    if cleaned.count(".") > 1:
        cleaned = cleaned.replace(".", "")
    try:
        return Decimal(sign + cleaned)
    except InvalidOperation:
        return None


def _extract_property_type(
    soup: BeautifulSoup,
    text: str,
    payloads: list,
    json_ld: dict | None = None,
) -> str:
    for value in _json_ld_values(json_ld, ["category", "additionalType", "@type"]):
        if isinstance(value, str) and value.strip():
            return value.strip()[:60]
    for value in _find_values(payloads, {"property_type", "propertyType", "type"}):
        if isinstance(value, str) and value.strip():
            return value.strip()[:60]
    lowered = text.lower()
    for label in ["appartement", "villa", "riad", "duplex", "terrain", "bureau"]:
        if label in lowered:
            return label
    return ""


def _extract_listing_type(
    soup: BeautifulSoup,
    text: str,
    payloads: list,
    json_ld: dict | None = None,
) -> str:
    for value in _json_ld_values(json_ld, ["businessFunction", "availability"]):
        lowered_value = str(value).lower()
        if "rent" in lowered_value:
            return "RENT"
        if "sell" in lowered_value or "sale" in lowered_value:
            return "SALE"
    lowered = text.lower()
    if "louer" in lowered or "location" in lowered or "rent" in lowered:
        return "RENT"
    if "acheter" in lowered or "vente" in lowered or "sale" in lowered:
        return "SALE"
    return "SALE"


def _extract_labeled_int(text: str, labels: list[str]) -> int | None:
    for label in labels:
        match = re.search(rf"(\d+)\s+{re.escape(label)}", text, re.I)
        if match:
            return int(match.group(1))
        match = re.search(rf"{re.escape(label)}\s*:?\s*(\d+)", text, re.I)
        if match:
            return int(match.group(1))
    return None


def _extract_floor(text: str) -> tuple[int | None, int | None]:
    match = re.search(r"(?:étage|etage|floor)\s*:?\s*(\d+)(?:\s*/\s*(\d+))?", text, re.I)
    if not match:
        return None, None
    floor = int(match.group(1))
    total = int(match.group(2)) if match.group(2) else None
    return floor, total


def _extract_year(text: str) -> int | None:
    match = re.search(r"(?:construction|construit|année|annee)\D*((?:19|20)\d{2})", text, re.I)
    return int(match.group(1)) if match else None


def _extract_furnished(text: str) -> bool:
    lowered = text.lower()
    return "meublé" in lowered or "meuble" in lowered or "furnished" in lowered


def _extract_location_parts(
    soup: BeautifulSoup,
    text: str,
    payloads: list,
    json_ld: dict | None = None,
) -> tuple[str, str]:
    address = _json_ld_address(json_ld)
    locality = address.get("addressLocality") or address.get("addressRegion") or ""
    neighborhood = address.get("addressNeighborhood") or ""
    if locality or neighborhood:
        return str(locality or "")[:120], str(neighborhood or "")[:120]

    locality = next(iter(_find_values(payloads, {"addressLocality", "city"})), "")
    neighborhood = next(iter(_find_values(payloads, {"neighborhood", "district"})), "")

    breadcrumbs = [
        item.get_text(" ", strip=True)
        for item in soup.select("[class*=breadcrumb] a, nav a")
        if item.get_text(" ", strip=True)
    ]
    if breadcrumbs:
        known_city = _first_known_city(breadcrumbs)
        locality = locality or known_city or breadcrumbs[-1]
        non_city_crumbs = [crumb for crumb in breadcrumbs if crumb != locality]
        if non_city_crumbs:
            neighborhood = neighborhood or non_city_crumbs[-1]

    if not locality:
        for city in ["Casablanca", "Marrakech", "Mohammedia", "Dar Bouazza", "Bouskoura", "Rabat", "Tanger", "Agadir", "Fès", "Fes"]:
            if city.lower() in text.lower():
                locality = city
                break

    return str(locality or "")[:120], str(neighborhood or "")[:120]


def _extract_address(
    soup: BeautifulSoup,
    city: str,
    neighborhood: str,
    json_ld: dict | None = None,
) -> str:
    address = _json_ld_address(json_ld)
    street = address.get("streetAddress")
    if street:
        return str(street)[:255]

    for selector in ["[class*=address]", "[class*=location]", "[data-testid*=location]"]:
        element = soup.select_one(selector)
        if element:
            address = element.get_text(" ", strip=True)
            if address and len(address) <= 200:
                return address[:255]
    return ", ".join(part for part in [neighborhood, city] if part)[:255]


def _extract_coordinates(
    soup: BeautifulSoup,
    payloads: list,
    json_ld: dict | None = None,
) -> tuple[Decimal | None, Decimal | None]:
    geo = json_ld.get("geo") if isinstance(json_ld, dict) else None
    if isinstance(geo, dict):
        lat = _parse_decimal(str(geo.get("latitude")))
        lng = _parse_decimal(str(geo.get("longitude")))
        if lat is not None and lng is not None:
            return lat, lng

    lat = _meta_decimal(soup, ["og:latitude", "place:location:latitude", "latitude"])
    lng = _meta_decimal(soup, ["og:longitude", "place:location:longitude", "longitude"])
    if lat is not None and lng is not None:
        return lat, lng

    for iframe in soup.find_all("iframe", src=True):
        src = iframe["src"]
        match = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", src)
        if match:
            return Decimal(match.group(1)), Decimal(match.group(2))
        query = parse_qs(urlparse(src).query)
        q = query.get("q") or query.get("ll") or query.get("center")
        if q and "," in q[0]:
            raw_lat, raw_lng = q[0].split(",", 1)
            return _parse_decimal(raw_lat), _parse_decimal(raw_lng)

    for element in soup.find_all(attrs={"data-lat": True}):
        lat = _parse_decimal(str(element.get("data-lat")))
        lng = _parse_decimal(str(element.get("data-lng") or element.get("data-lon")))
        if lat is not None and lng is not None:
            return lat, lng

    lat_value = next(iter(_find_values(payloads, {"latitude", "lat"})), None)
    lng_value = next(iter(_find_values(payloads, {"longitude", "lng", "lon"})), None)
    return _parse_decimal(str(lat_value)), _parse_decimal(str(lng_value))


def _meta_decimal(soup: BeautifulSoup, names: list[str]) -> Decimal | None:
    for name in names:
        meta = soup.find("meta", attrs={"property": name}) or soup.find(
            "meta", attrs={"name": name}
        )
        if meta and meta.get("content"):
            return _parse_decimal(meta["content"])
    return None


def _extract_description(
    soup: BeautifulSoup, payloads: list, json_ld: dict | None = None
) -> str:
    description = json_ld.get("description") if isinstance(json_ld, dict) else None
    if isinstance(description, str) and _valid_description(description):
        return description.strip()

    element = soup.find(attrs={"data-testid": re.compile(r"description", re.I)})
    if element:
        description = element.get_text(" ", strip=True)
        if _valid_description(description):
            return description

    for selector in ["[class*=description]", "section p"]:
        element = soup.select_one(selector)
        if element:
            description = element.get_text(" ", strip=True)
            if _valid_description(description):
                return description
    for value in _find_values(payloads, {"description"}):
        if isinstance(value, str) and _valid_description(value):
            return value.strip()
    return None


def _valid_description(value: str | None) -> bool:
    if not value:
        return False
    lowered = value.lower()
    if any(phrase in lowered for phrase in BAD_DESCRIPTION_PHRASES):
        return False
    return len(value.strip()) > 20


def _extract_amenities(soup: BeautifulSoup) -> list[str]:
    amenities = []
    container_selectors = "[class*=amenit], [class*=feature], [class*=equip], [data-testid*=feature]"
    elements = []
    for container in soup.select(container_selectors):
        children = container.find_all(["li", "span"], recursive=True)
        elements.extend(children or [container])
    for element in elements:
        text = element.get_text(" ", strip=True)
        if text and len(text) <= 80:
            amenities.append(_normalize_token(text))
    return sorted({item for item in amenities if item})


def _first_known_city(values: list[str]) -> str:
    known = {
        "casablanca",
        "marrakech",
        "marrakesh",
        "mohammedia",
        "dar bouazza",
        "bouskoura",
        "rabat",
        "tanger",
        "tangier",
        "agadir",
        "fes",
        "fez",
        "fès",
    }
    for value in values:
        if value.strip().lower() in known:
            return value
    return ""


def _extract_photo_urls(soup: BeautifulSoup, payloads: list) -> list[str]:
    urls = []
    json_ld = _extract_from_json_ld(soup) or {}
    for value in _json_ld_values(json_ld, ["image", "photo"]):
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and _looks_like_property_image(item):
                    urls.append(urljoin(BASE_URL, item))
        elif isinstance(value, str) and _looks_like_property_image(value):
            urls.append(urljoin(BASE_URL, value))

    for image in soup.find_all("img"):
        src = image.get("src") or image.get("data-src") or image.get("data-lazy-src")
        if src and _looks_like_property_image(src):
            urls.append(urljoin(BASE_URL, src))
    for value in _find_values(payloads, {"url", "src", "image"}):
        if isinstance(value, str) and _looks_like_property_image(value):
            urls.append(urljoin(BASE_URL, value))
    return list(dict.fromkeys(urls))


def _looks_like_property_image(url: str) -> bool:
    lowered = url.lower()
    return any(ext in lowered for ext in [".jpg", ".jpeg", ".png", ".webp"]) and not any(
        token in lowered for token in ["logo", "avatar", "icon"]
    )


def _extract_agency_name(soup: BeautifulSoup, payloads: list) -> str:
    agency_link = soup.find("a", href=re.compile(r"agence|agency", re.I))
    if agency_link:
        text = agency_link.get_text(" ", strip=True)
        if _valid_agency_name(text):
            return text[:200]

    contact_link = soup.find("a", href=re.compile(r"tel:|whatsapp|wa\.me", re.I))
    if contact_link:
        parent = contact_link
        for _ in range(4):
            parent = parent.parent
            if not parent:
                break
            text = _first_valid_agency_text(parent)
            if text:
                return text[:200]

    for selector in ["[class*=agency] [class*=name]", "[class*=agent] [class*=name]", "[class*=agency]", "[class*=agent]"]:
        element = soup.select_one(selector)
        if element:
            text = element.get_text(" ", strip=True)
            if _valid_agency_name(text):
                return text[:200]
    for value in _find_values(payloads, {"agency", "broker", "agent", "name"}):
        if isinstance(value, str) and _valid_agency_name(value):
            return value.strip()[:200]
    return ""


def _extract_phone(soup: BeautifulSoup, text: str) -> str | None:
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if href.lower().startswith("tel:"):
            phone = _normalize_phone(href)
            if phone:
                return phone

    for element in soup.select("[class*=phone], [class*=tel]"):
        phone = _normalize_phone(element.get_text(" ", strip=True))
        if phone:
            return phone

    match = re.search(r"(\+?212|0)\s?[5-7](?:[\s.\-]?\d){8}", text)
    return _normalize_phone(match.group(0)) if match else None


def _extract_whatsapp(soup: BeautifulSoup) -> str | None:
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if "whatsapp" in href.lower() or "wa.me" in href.lower():
            match = re.search(r"(\+?212|0)?[5-7]\d{8}", href.replace(" ", ""))
            if match:
                return _normalize_phone(match.group(0))
    return None


def _valid_agency_name(value: str | None) -> bool:
    if not value:
        return False
    lowered = value.strip().lower()
    if len(value.strip()) > 120:
        return False
    if _normalize_phone(value):
        return False
    return not any(keyword in lowered for keyword in REAL_AGENCY_BAD_KEYWORDS)


def _first_valid_agency_text(element) -> str:
    for candidate in element.find_all(["a", "span", "p", "h3", "h4", "h5"], recursive=True):
        text = candidate.get_text(" ", strip=True)
        if _valid_agency_name(text) and not _normalize_phone(text):
            return text
    return ""


def _normalize_phone(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"(\+?212|0)\s?[5-7](?:[\s.\-]?\d){8}", value.replace("tel:", ""))
    if not match:
        return None
    phone = re.sub(r"[\s.\-+]", "", match.group(0))
    if phone == SAROUTY_SUPPORT_PHONE:
        return None
    return phone


def _extract_agency_logo(soup: BeautifulSoup) -> str | None:
    for image in soup.find_all("img"):
        alt = (image.get("alt") or "").lower()
        src = image.get("src") or image.get("data-src")
        if src and any(token in alt for token in ["agency", "agence", "agent", "logo"]):
            return urljoin(BASE_URL, src)
    return None


def _extract_agency_profile_url(soup: BeautifulSoup) -> str | None:
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if "/trouver-une-agence/" in href and href.rstrip("/") != "/trouver-une-agence":
            return urljoin(BASE_URL, href).split("#")[0]
    return None


def _normalize_token(value: str) -> str:
    return re.sub(r"\s+", "_", value.strip().lower())


def _find_values(payloads: list, keys: set[str]):
    normalized_keys = {key.lower() for key in keys}
    for payload in payloads:
        yield from _find_values_recursive(payload, normalized_keys)


def _find_values_recursive(payload, keys: set[str]):
    if isinstance(payload, dict):
        for key, value in payload.items():
            if str(key).lower() in keys and value not in (None, ""):
                yield value
            if isinstance(value, (dict, list)):
                yield from _find_values_recursive(value, keys)
    elif isinstance(payload, list):
        for item in payload:
            yield from _find_values_recursive(item, keys)


def _json_ld_values(json_ld: dict | None, keys: list[str]):
    if not isinstance(json_ld, dict):
        return
    for key in keys:
        value = json_ld.get(key)
        if value not in (None, ""):
            yield value
    offers = json_ld.get("offers")
    if isinstance(offers, dict):
        for key in keys:
            value = offers.get(key)
            if value not in (None, ""):
                yield value


def _json_ld_address(json_ld: dict | None) -> dict:
    if not isinstance(json_ld, dict):
        return {}
    address = json_ld.get("address")
    return address if isinstance(address, dict) else {}


def _parse_json_ld_area(value) -> Decimal | None:
    if isinstance(value, dict):
        value = value.get("value") or value.get("amount")
    return _parse_decimal(str(value))


def _clean_api_text(value: str | None) -> str:
    if not value:
        return ""
    text = unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _api_listing_type(data: dict) -> str:
    value = " ".join(
        str(data.get(key) or "")
        for key in ["property_category", "property_type_sale_name_en", "listing_type"]
    ).lower()
    if "rent" in value or "louer" in value:
        return "RENT"
    return "SALE"


def _api_int(value) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None
