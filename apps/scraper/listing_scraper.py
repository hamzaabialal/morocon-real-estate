"""Scrape and persist individual Sarouty.ma listing pages."""
import logging
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import httpx
from asgiref.sync import sync_to_async
from django.db import DataError, Error, transaction
from django.db.models import F
from django.utils import timezone

from apps.agencies.models import Agency
from apps.locations.models import City, Country, District, Neighborhood
from apps.properties.models import Property, PropertyFeatures, PropertyImage
from apps.scraper.dedup import mark_as_scraped
from apps.scraper.http_client import fetch_html
from apps.scraper.listing_parser import (
    SaroutyListing,
    data_quality_ok,
    parse_listing_api_payload,
    parse_listing_html,
)
from apps.scraper.models import ScrapeError

logger = logging.getLogger(__name__)

LISTING_URL = "https://www.sarouty.ma/en/property-details/?listing_id={listing_id}"

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

FEATURE_ALIASES = {
    "ascenseur": "elevator",
    "elevator": "elevator",
    "parking": "outdoor_parking",
    "parking_souterrain": "underground_parking",
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
    "climatisation": "centralized_air_conditioning",
    "chauffage": "centralized_heating",
    "cuisine_équipée": "equipped_kitchen",
    "cuisine_equipee": "equipped_kitchen",
    "cuisine_américaine": "american_kitchen",
    "cuisine_americaine": "american_kitchen",
    "fibre": "fiber_installation",
    "cheminée": "fireplace",
    "cheminee": "fireplace",
}


async def scrape_listing(listing_id: int, job) -> bool:
    """Returns True on success, False on failure. Never raises."""
    url = LISTING_URL.format(listing_id=listing_id)
    try:
        html = await fetch_html(url, use_playwright=False)
        parsed = parse_listing_html(html or "", listing_id) if html else None

        if not data_quality_ok(parsed):
            logger.info(
                "[%s] httpx gave low-quality data, retrying with Playwright",
                listing_id,
            )
            html = await fetch_html(url, use_playwright=True)
            if html:
                parsed = parse_listing_html(html, listing_id)

        if not data_quality_ok(parsed):
            api_payload = await fetch_listing_api_payload(listing_id)
            if api_payload:
                parsed = parse_listing_api_payload(api_payload, listing_id)

        if parsed is None:
            await sync_to_async(mark_as_scraped, thread_sensitive=True)(listing_id)
            return False

        if not data_quality_ok(parsed):
            await sync_to_async(_record_error, thread_sensitive=True)(
                job,
                listing_id,
                url,
                "Low-quality parse after Playwright fallback",
            )
            return False

        try:
            await sync_to_async(_persist_listing, thread_sensitive=True)(parsed, job, url)
        except (DataError, Error) as exc:
            logger.exception(
                "Database persistence failed for Sarouty listing %s", listing_id
            )
            await sync_to_async(_record_error, thread_sensitive=True)(
                job,
                listing_id,
                url,
                _format_persistence_error(exc, parsed),
            )
            return False
        return True
    except Exception as exc:
        logger.exception("Failed to scrape Sarouty listing %s", listing_id)
        await sync_to_async(_record_error, thread_sensitive=True)(
            job, listing_id, url, str(exc)
        )
        return False


async def fetch_listing_api_payload(listing_id: int) -> dict | None:
    """Fetch Sarouty's public JSON API for one listing."""
    api_url = f"https://b2c-be-prod.api.sarouty.ma/api/properties/{listing_id}"
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(api_url)
        if response.status_code != 200:
            logger.warning("Sarouty API returned HTTP %s for %s", response.status_code, listing_id)
            return None
        return response.json()
    except Exception:
        logger.exception("Failed to fetch Sarouty API payload for %s", listing_id)
        return None


@transaction.atomic
def _persist_listing(parsed: SaroutyListing, job, url: str) -> None:
    try:
        agency = _resolve_agency(parsed)
        city, district, neighborhood = _resolve_location(parsed)
        property_type = normalize_property_type(parsed.property_type)
        listing_type = (
            parsed.listing_type if parsed.listing_type in {"SALE", "RENT"} else "SALE"
        )
        raw = {
            "price": parsed.price,
            "area": parsed.area,
            "built_area": getattr(parsed, "built_area", None),
            "condominium_fees": getattr(parsed, "condominium_fees", None),
            "registration_fees": getattr(parsed, "registration_fees", None),
            "land_registration_fees": getattr(parsed, "land_registration_fees", None),
            "notary_fees": getattr(parsed, "notary_fees", None),
            "total_acquisition_cost": getattr(parsed, "total_acquisition_cost", None),
            "latitude": parsed.latitude,
            "longitude": parsed.longitude,
        }
        price = sanitize_decimal(raw.get("price"), default=Decimal("0.00"))
        area = sanitize_decimal(raw.get("area"), default=Decimal("0.00"))
        built_area = sanitize_decimal(raw.get("built_area"))
        condominium_fees = sanitize_decimal(raw.get("condominium_fees"))
        registration_fees = sanitize_decimal(raw.get("registration_fees"))
        land_registration_fees = sanitize_decimal(raw.get("land_registration_fees"))
        notary_fees = sanitize_decimal(raw.get("notary_fees"))
        total_acquisition_cost = sanitize_decimal(raw.get("total_acquisition_cost"))
        latitude = sanitize_decimal(
            raw.get("latitude"), max_value=90, allow_negative=True
        )
        longitude = sanitize_decimal(
            raw.get("longitude"), max_value=180, allow_negative=True
        )

        property_obj, _ = Property.objects.update_or_create(
            sarouty_id=parsed.sarouty_id,
            defaults={
                "yakeey_ref": f"SAROUTY-{parsed.sarouty_id}",
                "yakeey_id": None,
                "enrichment_confidence": "NONE",
                "listing_type": listing_type,
                "transaction_type": listing_type,
                "property_category": normalize_property_category(parsed.property_type),
                "property_type": property_type,
                "status": "LISTED",
                "price": price,
                "currency": "DH",
                "area": area,
                "built_area": built_area,
                "condominium_fees": condominium_fees,
                "bedrooms": parsed.rooms or 0,
                "bathrooms": parsed.bathrooms or 0,
                "floor": parsed.floor,
                "total_floors": parsed.total_floors,
                "construction_year": parsed.construction_year,
                "furnished": parsed.furnished,
                "description": parsed.description or "",
                "cover_image_url": parsed.photo_urls[0] if parsed.photo_urls else "",
                "latitude": latitude,
                "longitude": longitude,
                "registration_fees": registration_fees,
                "land_registration_fees": land_registration_fees,
                "notary_fees": notary_fees,
                "total_acquisition_cost": total_acquisition_cost,
                "formatted_address": parsed.main_address or "",
                "main_address": parsed.main_address or "",
                "source_url": url,
                "marketplace_url": url,
                "agent_name": parsed.agency_name or "",
                "agent_phone": parsed.agency_phone or "",
                "agency": agency,
                "city": city,
                "district": district,
                "neighborhood": neighborhood,
                "scrape_status": "SCRAPED",
                "last_scraped_at": timezone.now(),
                "listed_at": timezone.now(),
                "source": "manual",
            },
        )

        _save_images(property_obj, parsed.photo_urls)
        if parsed.amenities:
            _save_features(property_obj, parsed.amenities)

        mark_as_scraped(parsed.sarouty_id)
        type(job).objects.filter(pk=job.pk).update(
            records_scraped=F("records_scraped") + 1
        )
        job.records_scraped += 1
    except DataError:
        logger.exception(
            "Numeric or database range error while persisting Sarouty listing %s",
            parsed.sarouty_id,
        )
        raise


def _resolve_agency(parsed: SaroutyListing) -> Agency | None:
    if not parsed.agency_name:
        return None

    name = normalize_agency_name(parsed.agency_name)
    agency = Agency.objects.filter(name__iexact=name).first()
    if agency is None:
        agency = Agency(name=name)

    if parsed.agency_phone and not agency.phone:
        agency.phone = parsed.agency_phone
    if parsed.agency_whatsapp:
        agency.whatsapp = parsed.agency_whatsapp
    if parsed.agency_logo_url:
        agency.logo_url = parsed.agency_logo_url
    if parsed.agency_profile_url:
        agency.sarouty_profile_url = parsed.agency_profile_url
    agency.save()
    return agency


def _resolve_location(parsed: SaroutyListing):
    country, _ = Country.objects.get_or_create(code="MA", defaults={"name": "Morocco"})
    city_name = normalize_city_name(parsed.city_raw) or "Unknown"
    city, _ = City.objects.get_or_create(name=city_name, country=country)

    district = None
    neighborhood = None
    neighborhood_name = normalize_location_name(parsed.neighborhood_raw)
    if neighborhood_name:
        district, _ = District.objects.get_or_create(name="Unknown", city=city)
        neighborhood, _ = Neighborhood.objects.get_or_create(
            name=neighborhood_name,
            district=district,
        )
    return city, district, neighborhood


def _save_images(property_obj: Property, photo_urls: list[str]) -> None:
    existing_urls = set(
        PropertyImage.objects.filter(property=property_obj).values_list("url", flat=True)
    )
    new_images = [
        PropertyImage(
            property=property_obj,
            url=url,
            order=index,
            is_main=index == 0,
        )
        for index, url in enumerate(photo_urls)
        if url not in existing_urls
    ]
    if new_images:
        PropertyImage.objects.bulk_create(new_images, ignore_conflicts=True)


def _save_features(property_obj: Property, amenities: list[str]) -> None:
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

    PropertyFeatures.objects.update_or_create(
        property=property_obj,
        defaults=defaults,
    )


@transaction.atomic
def _record_error(job, listing_id: int, url: str, message: str) -> None:
    ScrapeError.objects.create(
        job=job,
        listing_id=listing_id,
        url=url,
        error_message=message,
    )
    type(job).objects.filter(pk=job.pk).update(errors_count=F("errors_count") + 1)
    job.errors_count += 1


def _format_persistence_error(exc: Exception, parsed: SaroutyListing) -> str:
    return (
        "Database persistence failed: "
        f"{exc.__class__.__name__}: {exc}; "
        f"price={parsed.price!r}, area={parsed.area!r}, "
        f"latitude={parsed.latitude!r}, longitude={parsed.longitude!r}, "
        f"property_type={parsed.property_type!r}, listing_type={parsed.listing_type!r}"
    )


def sanitize_decimal(
    value, max_value=None, allow_negative=False, default=None
):
    """Clamp parsed decimal values to a safe range."""
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


def normalize_agency_name(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().title()


def normalize_city_name(value: str | None) -> str:
    if not value:
        return ""
    cleaned = normalize_location_name(value)
    return CITY_ALIASES.get(cleaned.lower(), cleaned)


def normalize_location_name(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def normalize_property_type(value: str) -> str:
    lowered = (value or "").lower()
    if "appartement" in lowered or "apartment" in lowered:
        return "APARTMENT"
    if "duplex" in lowered:
        return "DUPLEX"
    if "riad" in lowered:
        return "RIAD"
    if "bureau" in lowered or "office" in lowered:
        return "OFFICE"
    if "villa" in lowered:
        return "ISOLATED_HOUSE"
    return ""


def normalize_property_category(value: str) -> str:
    lowered = (value or "").lower()
    if "terrain" in lowered:
        return "TERRAIN"
    if "villa" in lowered or "maison" in lowered or "house" in lowered:
        return "VILLA"
    if "bureau" in lowered or "commerce" in lowered or "office" in lowered:
        return "COMMERCIAL_BUILDING"
    if "riad" in lowered:
        return "RIAD"
    return "FLAT"


def normalize_feature_name(value: str) -> str:
    token = re.sub(r"\s+", "_", value.strip().lower())
    token = token.replace("-", "_")
    return FEATURE_ALIASES.get(token, token)
