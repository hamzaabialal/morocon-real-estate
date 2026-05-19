"""Pure API scraper for Sarouty.ma property listings."""
import asyncio
import logging
import random
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.parse import urljoin

import httpx
from asgiref.sync import sync_to_async
from django.db import DataError, Error, transaction
from django.db.models import F
from django.utils import timezone

from apps.agencies.models import Agency
from apps.locations.models import City, Country, District, Neighborhood
from apps.properties.models import Property, PropertyFeatures, PropertyImage
from apps.scraper.dedup import mark_as_scraped
from apps.scraper.models import ScrapeError, ScrapeJob

logger = logging.getLogger(__name__)

API_BASE_URL = "https://b2c-be-prod.api.sarouty.ma"
PROPERTIES_API_URL = f"{API_BASE_URL}/api/properties"
SAROUTY_WEB_BASE_URL = "https://www.sarouty.ma"
CDN_BASE_URL = "https://sarouty-prod.s3.eu-west-3.amazonaws.com/"

API_DELAY_MIN = 0.3
API_DELAY_MAX = 0.8
PLAYWRIGHT_DELAY_MIN = 3.0
PLAYWRIGHT_DELAY_MAX = 7.0

HTTP_HEADERS = {
    "Accept": "application/json",
    "Accept-Language": "fr-MA,fr;q=0.9,ar;q=0.8",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
}

CITY_ALIASES = {
    "casa": "Casablanca",
    "casablanca": "Casablanca",
    "dar el beida": "Casablanca",
    "dar-el-beida": "Casablanca",
    "marrakech": "Marrakech",
    "marrakesh": "Marrakech",
    "mohammedia": "Mohammedia",
    "mohammédia": "Mohammedia",
    "dar bouazza": "Dar Bouazza",
    "dar-bouazza": "Dar Bouazza",
    "bouskoura": "Bouskoura",
    "rabat": "Rabat",
    "tanger": "Tanger",
    "tangier": "Tanger",
    "agadir": "Agadir",
    "fes": "Fès",
    "fez": "Fès",
    "fès": "Fès",
}

PROPERTY_TYPE_ALIASES = {
    "appartement": "APARTMENT",
    "apartment": "APARTMENT",
    "studio": "STUDIO",
    "duplex": "DUPLEX",
    "triplex": "TRIPLEX",
    "riad": "RIAD",
    "bureau": "OFFICE",
    "bureaux": "OFFICE",
    "office": "OFFICE",
    "villa": "ISOLATED_HOUSE",
    "maison": "ISOLATED_HOUSE",
    "house": "ISOLATED_HOUSE",
}

PROPERTY_CATEGORY_ALIASES = {
    "commercial": "COMMERCIAL_BUILDING",
    "residential": "FLAT",
    "terrain": "TERRAIN",
    "land": "TERRAIN",
    "villa": "VILLA",
    "riad": "RIAD",
    "office": "OFFICE",
    "bureau": "OFFICE",
}

FEATURE_ALIASES = {
    "ascenseur": "elevator",
    "elevator": "elevator",
    "parking": "outdoor_parking",
    "garage": "garage",
    "terrasse": "terrace",
    "terrace": "terrace",
    "balcon": "balcony",
    "balcony": "balcony",
    "jardin": "garden",
    "garden": "garden",
    "piscine": "pool",
    "pool": "pool",
    "sécurité": "security_agent",
    "securite": "security_agent",
    "concierge": "concierge",
    "fibre": "fiber_installation",
    "cheminée": "fireplace",
    "cheminee": "fireplace",
}


async def fetch_listing_page(page: int, limit: int = 50) -> dict | None:
    """Fetch one Sarouty listings API page."""
    await _sleep_api_delay()
    try:
        async with httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,
            headers=HTTP_HEADERS,
        ) as client:
            response = await client.get(
                PROPERTIES_API_URL,
                params={"limit": limit, "page": page},
            )
        if response.status_code != 200:
            logger.warning(
                "Sarouty properties API returned HTTP %s for page %s",
                response.status_code,
                page,
            )
            return None
        return response.json()
    except Exception:
        logger.exception("Failed to fetch Sarouty listing page %s", page)
        return None


async def fetch_listing_detail(property_id: int) -> dict | None:
    """Fetch one Sarouty listing detail payload."""
    await _sleep_api_delay()
    try:
        async with httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,
            headers=HTTP_HEADERS,
        ) as client:
            response = await client.get(f"{PROPERTIES_API_URL}/{property_id}")
        if response.status_code != 200:
            logger.warning(
                "Sarouty property detail API returned HTTP %s for %s",
                response.status_code,
                property_id,
            )
            return None
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(data, dict) and "data" in data:
            return data.get("data")
        return data if isinstance(data, dict) else None
    except Exception:
        logger.exception("Failed to fetch Sarouty listing detail %s", property_id)
        return None


async def _sleep_api_delay() -> None:
    await asyncio.sleep(random.uniform(API_DELAY_MIN, API_DELAY_MAX))


async def scrape_and_save_listing(listing_data: dict, job: ScrapeJob) -> bool:
    """Persist one listing row from Sarouty's list API."""
    listing_id = _int_value(listing_data.get("property_id"))
    if listing_id is None:
        await sync_to_async(_record_error, thread_sensitive=True)(
            job,
            None,
            PROPERTIES_API_URL,
            "Missing property_id in Sarouty listing row",
        )
        return False

    detail_data = await fetch_listing_detail(listing_id)
    merged = {**listing_data, **(detail_data or {})}
    url = _listing_url(listing_id)
    try:
        await sync_to_async(_persist_api_listing, thread_sensitive=True)(
            merged,
            job,
            url,
        )
        return True
    except (DataError, Error) as exc:
        logger.exception("Database persistence failed for Sarouty listing %s", listing_id)
        await sync_to_async(_record_error, thread_sensitive=True)(
            job,
            listing_id,
            url,
            _format_persistence_error(exc, merged),
        )
        return False
    except Exception as exc:
        logger.exception("Failed to save Sarouty listing %s", listing_id)
        await sync_to_async(_record_error, thread_sensitive=True)(
            job,
            listing_id,
            url,
            str(exc),
        )
        return False


async def scrape_listing(listing_id: int, job: ScrapeJob) -> bool:
    """Compatibility wrapper for queue-based retry tasks."""
    detail_data = await fetch_listing_detail(listing_id)
    if not detail_data:
        await sync_to_async(mark_as_scraped, thread_sensitive=True)(listing_id)
        return False
    return await scrape_and_save_listing(detail_data, job)


@transaction.atomic
def _persist_api_listing(raw: dict, job: ScrapeJob, url: str) -> None:
    listing_id = _int_value(raw.get("property_id"))
    if listing_id is None:
        raise ValueError("Missing property_id")

    agency = _resolve_agency(raw)
    city, district, neighborhood = _resolve_location(raw)

    price_data = raw.get("price") if isinstance(raw.get("price"), dict) else {}
    price = sanitize_decimal(
        price_data.get("price", raw.get("property_price")),
        default=Decimal("0.00"),
    )
    area = sanitize_decimal(raw.get("property_sqft"), default=Decimal("0.00"))
    latitude, longitude = _coordinates(raw)
    listing_type = _listing_type(raw)
    images = _image_urls(raw)
    description = _description(raw)
    title = _title(raw)
    address = _address(raw)

    property_obj, _ = Property.objects.update_or_create(
        sarouty_id=listing_id,
        defaults={
            "yakeey_ref": f"SAROUTY-{listing_id}",
            "yakeey_id": None,
            "enrichment_confidence": "NONE",
            "listing_type": listing_type,
            "transaction_type": listing_type,
            "property_category": normalize_property_category(
                raw.get("property_type") or raw.get("property_category")
            ),
            "property_type": normalize_property_type(raw.get("property_housing_type")),
            "status": "LISTED",
            "price": price,
            "currency": "DH",
            "area": area,
            "bedrooms": _int_value(raw.get("total_bedroom")) or 0,
            "bathrooms": _int_value(raw.get("total_bathroom")) or 0,
            "floor": _int_value(raw.get("property_floor")),
            "total_floors": _int_value(raw.get("property_floors_number")),
            "construction_year": _int_value(raw.get("property_build_year")),
            "furnished": str(raw.get("property_furnished") or "").upper() == "YES",
            "description": description or title,
            "cover_image_url": images[0] if images else "",
            "latitude": sanitize_decimal(latitude, max_value=90, allow_negative=True),
            "longitude": sanitize_decimal(longitude, max_value=180, allow_negative=True),
            "formatted_address": address,
            "main_address": address,
            "source_url": url,
            "marketplace_url": url,
            "agent_name": str(raw.get("agent_broker_name") or "")[:150],
            "agent_phone": _normalize_phone(raw.get("agent_broker_phone")) or "",
            "agency": agency,
            "city": city,
            "district": district,
            "neighborhood": neighborhood,
            "scrape_status": "SCRAPED",
            "last_scraped_at": timezone.now(),
            "listed_at": _safe_now(),
            "source": "manual",
        },
    )

    _save_images(property_obj, images)
    _save_features(property_obj, _amenities(raw))
    mark_as_scraped(listing_id)
    type(job).objects.filter(pk=job.pk).update(records_scraped=F("records_scraped") + 1)
    job.records_scraped += 1


def _resolve_agency(raw: dict) -> Agency | None:
    agency_id = raw.get("agent_company_id") or raw.get("property_agent_id")
    agency_name = str(raw.get("agent_company_name") or "").strip()
    if not agency_id and not agency_name:
        return None

    agency = None
    if agency_id:
        agency = Agency.objects.filter(sarouty_agency_id=str(agency_id)).first()
    if agency is None and agency_name:
        agency = Agency.objects.filter(name__iexact=agency_name).first()
    if agency is None:
        agency = Agency(name=agency_name or f"Sarouty Agency {agency_id}")

    agency.sarouty_agency_id = str(agency_id)[:100] if agency_id else None
    agency.sarouty_profile_url = _agency_profile_url(raw)
    agency.phone = _normalize_phone(raw.get("agent_company_phone")) or agency.phone
    agency.whatsapp = (
        _normalize_phone(raw.get("agent_broker_whatsapp_phone"))
        or _normalize_phone(raw.get("agent_company_phone"))
        or agency.whatsapp
    )
    agency.email = (raw.get("agent_company_email") or "").strip() or agency.email
    agency.logo_url = _absolute_cdn_url(raw.get("agent_company_logo")) or agency.logo_url
    agency.total_listings = _int_value(raw.get("total_properties")) or agency.total_listings
    agency.save()
    return agency


def _resolve_location(raw: dict):
    country, _ = Country.objects.get_or_create(code="MA", defaults={"name": "Morocco"})
    location = raw.get("location") if isinstance(raw.get("location"), dict) else {}
    city_name = normalize_city_name(
        raw.get("location_url_slug")
        or location.get("url_city_slug")
        or ""
    ) or "Unknown"
    neighborhood_name = normalize_location_name(
        raw.get("location_name")
        or location.get("name_primary")
        or ""
    )

    city, _ = City.objects.get_or_create(name=city_name, country=country)
    district = None
    neighborhood = None
    if neighborhood_name:
        district, _ = District.objects.get_or_create(name="Unknown", city=city)
        neighborhood, _ = Neighborhood.objects.get_or_create(
            name=neighborhood_name,
            district=district,
        )
    return city, district, neighborhood


def _coordinates(raw: dict) -> tuple:
    location = raw.get("location") if isinstance(raw.get("location"), dict) else {}
    lat = raw.get("property_latitude") or location.get("coordinates_lat")
    lng = raw.get("property_longitude") or location.get("coordinates_lon")
    return lat, lng


def _listing_type(raw: dict) -> str:
    price_data = raw.get("price") if isinstance(raw.get("price"), dict) else {}
    value = " ".join(
        str(item or "")
        for item in [
            price_data.get("price_type"),
            (raw.get("price_type") or {}).get("price_type_name_en")
            if isinstance(raw.get("price_type"), dict)
            else "",
            raw.get("property_type_sale_name_en"),
            raw.get("property_category_key"),
            raw.get("property_category"),
        ]
    ).lower()
    if "rent" in value or "louer" in value or "monthly" in value:
        return "RENT"
    return "SALE"


def _image_urls(raw: dict) -> list[str]:
    urls = []
    for image in raw.get("images") or []:
        if isinstance(image, dict):
            url = image.get("property_image_url")
            if url:
                urls.append(_absolute_cdn_url(url))
    return [url for url in dict.fromkeys(urls) if url]


def _description(raw: dict) -> str:
    for key in ["property_text_fr", "property_text_en", "property_text_ar"]:
        value = raw.get(key)
        if value:
            return re.sub(r"\s+", " ", str(value)).strip()
    return ""


def _title(raw: dict) -> str:
    for key in ["property_title_fr", "property_title_en", "property_title_ar"]:
        value = raw.get(key)
        if value:
            return re.sub(r"\s+", " ", str(value)).strip()
    return ""


def _address(raw: dict) -> str:
    location = raw.get("location") if isinstance(raw.get("location"), dict) else {}
    value = raw.get("property_address")
    if value:
        return re.sub(r"\s+", " ", str(value)).strip()[:255]
    parts = [
        raw.get("location_name") or location.get("name_primary"),
        normalize_city_name(raw.get("location_url_slug") or location.get("url_city_slug")),
    ]
    return ", ".join(str(part).strip() for part in parts if part)[:255]


def _agency_profile_url(raw: dict) -> str | None:
    client_id = raw.get("client_id") or raw.get("agent_company_id")
    if not client_id:
        return None
    return f"{SAROUTY_WEB_BASE_URL}/agent-details?agent_id={client_id}"


def _listing_url(listing_id: int) -> str:
    return f"{SAROUTY_WEB_BASE_URL}/en/property-details/?listing_id={listing_id}"


def _absolute_cdn_url(value: str | None) -> str | None:
    if not value:
        return None
    value = str(value)
    if value.startswith(("http://", "https://")):
        return value
    return urljoin(CDN_BASE_URL, value.lstrip("/"))


def _amenities(raw: dict) -> list[str]:
    amenities = []
    for key in ["amenities", "features", "property_amenities"]:
        values = raw.get(key) or []
        if isinstance(values, list):
            for value in values:
                if isinstance(value, dict):
                    value = value.get("name") or value.get("title") or value.get("amenity_name")
                if value:
                    amenities.append(str(value))
    return amenities


def _save_images(property_obj: Property, photo_urls: list[str]) -> None:
    existing_urls = set(
        PropertyImage.objects.filter(property=property_obj).values_list("url", flat=True)
    )
    new_images = [
        PropertyImage(property=property_obj, url=url, order=index, is_main=index == 0)
        for index, url in enumerate(photo_urls)
        if url not in existing_urls
    ]
    if new_images:
        PropertyImage.objects.bulk_create(new_images, ignore_conflicts=True)


def _save_features(property_obj: Property, amenities: list[str]) -> None:
    if not amenities:
        return
    bool_fields = {
        field.name
        for field in PropertyFeatures._meta.fields
        if field.get_internal_type() == "BooleanField"
    }
    defaults = {field_name: False for field_name in bool_fields}
    for amenity in amenities:
        field_name = normalize_feature_name(amenity)
        if field_name in bool_fields:
            defaults[field_name] = True
    PropertyFeatures.objects.update_or_create(property=property_obj, defaults=defaults)


@transaction.atomic
def _record_error(job: ScrapeJob, listing_id: int | None, url: str, message: str) -> None:
    ScrapeError.objects.create(
        job=job,
        listing_id=listing_id,
        url=url,
        error_message=message,
    )
    type(job).objects.filter(pk=job.pk).update(errors_count=F("errors_count") + 1)
    job.errors_count += 1


def _format_persistence_error(exc: Exception, raw: dict) -> str:
    return (
        "Database persistence failed: "
        f"{exc.__class__.__name__}: {exc}; "
        f"property_id={raw.get('property_id')!r}, "
        f"price={raw.get('price')!r}, area={raw.get('property_sqft')!r}, "
        f"lat={raw.get('property_latitude')!r}, lng={raw.get('property_longitude')!r}"
    )


def sanitize_decimal(value, max_value=None, allow_negative=False, default=None):
    if value is None:
        return default
    cleaned = re.sub(r"[^\d.\-]", "", str(value).strip())
    parts = cleaned.split(".")
    if len(parts) > 2:
        cleaned = "".join(parts[:-1]) + "." + parts[-1]
    if not cleaned or cleaned in (".", "-", "-."):
        return default
    try:
        d = Decimal(cleaned).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return default
    if not allow_negative and d < 0:
        return default
    cap = Decimal(str(max_value)) if max_value else Decimal("9999999999.99")
    if abs(d) > cap:
        return default
    return d


def _int_value(value) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _normalize_phone(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"(\+?212|0)\s?[5-7](?:[\s.\-]?\d){8}", str(value))
    if not match:
        return None
    return re.sub(r"[\s.\-+]", "", match.group(0))


def _safe_now():
    return timezone.now()


def normalize_agency_name(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().title()


def normalize_city_name(value: str | None) -> str:
    if not value:
        return ""
    cleaned = normalize_location_name(str(value).replace("-", " "))
    return CITY_ALIASES.get(cleaned.lower(), cleaned.title())


def normalize_location_name(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", str(value).strip())


def normalize_property_type(value: str | None) -> str:
    lowered = (value or "").lower()
    for token, normalized in PROPERTY_TYPE_ALIASES.items():
        if token in lowered:
            return normalized
    return "OFFICE" if "magasin" in lowered or "shop" in lowered else ""


def normalize_property_category(value: str | None) -> str:
    lowered = (value or "").lower()
    for token, normalized in PROPERTY_CATEGORY_ALIASES.items():
        if token in lowered:
            return normalized
    return "FLAT"


def normalize_feature_name(value: str) -> str:
    token = re.sub(r"\s+", "_", value.strip().lower())
    token = token.replace("-", "_")
    return FEATURE_ALIASES.get(token, token)
