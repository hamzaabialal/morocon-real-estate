"""Agency matching for PropertyFinder.ma collected agency records."""
from difflib import SequenceMatcher

from apps.agencies.models import Agency
from apps.locations.models import City
from apps.scraper.models import CollectedAgency


def normalize_phone(phone):
    """Normalize phone numbers for exact comparison."""
    if not phone:
        return ""
    digits = "".join(character for character in str(phone) if character.isdigit())
    if digits.startswith("0"):
        digits = "212" + digits[1:]
    return digits


def name_similarity(left, right):
    """Return fuzzy similarity between two agency names."""
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left.lower().strip(), right.lower().strip()).ratio()


def find_city(city_raw):
    """Find a City row from raw scraped city text."""
    if not city_raw:
        return None
    return City.objects.filter(name__iexact=city_raw.strip()).first()


def best_agency_match(collected_agency):
    """Find the best Agency match and confidence for one collected record."""
    normalized_collected_phone = normalize_phone(collected_agency.phone)
    if normalized_collected_phone:
        for agency in Agency.objects.exclude(phone=""):
            if normalize_phone(agency.phone) == normalized_collected_phone:
                return agency, 1.0

    best_agency = None
    best_confidence = 0.0
    city = find_city(collected_agency.city_raw)

    for agency in Agency.objects.all():
        similarity = name_similarity(collected_agency.name, agency.name)
        confidence = 0.0
        if similarity >= 0.6:
            confidence = min(0.9, similarity)
        if city and agency.city_id == city.id and similarity > 0.7:
            confidence = max(confidence, 0.75)
        if confidence > best_confidence:
            best_agency = agency
            best_confidence = confidence

    return best_agency, best_confidence


def create_agency_from_collected(collected_agency):
    """Create a new Agency from a collected PropertyFinder agency record."""
    city = find_city(collected_agency.city_raw)
    return Agency.objects.create(
        name=collected_agency.name,
        phone=collected_agency.phone or "",
        whatsapp=collected_agency.whatsapp,
        email=collected_agency.email,
        website=collected_agency.website,
        logo_url=collected_agency.logo_url,
        city=city,
        source="propertyfinder",
        propertyfinder_id=collected_agency.propertyfinder_id,
    )


def match_collected_agencies():
    """Match unprocessed collected agency records to existing agencies."""
    stats = {"matched": 0, "created": 0, "skipped": 0}

    for collected_agency in CollectedAgency.objects.filter(is_processed=False):
        if not collected_agency.name and not collected_agency.phone:
            collected_agency.is_processed = True
            collected_agency.save(update_fields=["is_processed"])
            stats["skipped"] += 1
            continue

        matched_agency, confidence = best_agency_match(collected_agency)
        if matched_agency and confidence >= 0.7:
            collected_agency.matched_agency = matched_agency
            collected_agency.match_confidence = confidence
            stats["matched"] += 1
        elif collected_agency.name:
            created_agency = create_agency_from_collected(collected_agency)
            collected_agency.matched_agency = created_agency
            collected_agency.match_confidence = confidence or 0.0
            stats["created"] += 1
        else:
            stats["skipped"] += 1

        collected_agency.is_processed = True
        collected_agency.save(
            update_fields=["matched_agency", "match_confidence", "is_processed"]
        )

    return stats
