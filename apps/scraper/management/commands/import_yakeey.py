"""Import Yakeey CSV/parquet listings into the core property models."""
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from ftfy import fix_text

from apps.locations.models import City, Country, District, Neighborhood
from apps.properties.models import Property, PropertyFeatures, PropertyImage


CITY_ALIASES = {
    "casablanca": "Casablanca",
    "CASABLANCA": "Casablanca",
    "CASA BLANCA": "Casablanca",
    "Casablanc": "Casablanca",
    "casablanc": "Casablanca",
    "marrakesh": "Marrakech",
    "MARRAKECH": "Marrakech",
    "marrakech": "Marrakech",
    "marraKECH": "Marrakech",
    "marrakch": "Marrakech",
    "MARRAKEH": "Marrakech",
    "mohammédia": "Mohammedia",
    "MOHAMMEDIA": "Mohammedia",
    "mohammedia": "Mohammedia",
    "Mohammadia": "Mohammedia",
    "MOHAMADIA": "Mohammedia",
    "Mohammédia": "Mohammedia",
    "DAR BOUAZZA": "Dar Bouazza",
    "dar bouazza": "Dar Bouazza",
    "darbouazza": "Dar Bouazza",
    "darb bouazza": "Dar Bouazza",
    "DARBOUAZZA": "Dar Bouazza",
    "BOUSKOURA": "Bouskoura",
    "bouskoura": "Bouskoura",
    "RABAT": "Rabat",
    "rabat": "Rabat",
    "TANGER": "Tanger",
    "tanger": "Tanger",
    "Tangier": "Tanger",
    "AGADIR": "Agadir",
    "agadir": "Agadir",
    "KENITRA": "Kenitra",
    "kenitra": "Kenitra",
    "Kénitra": "Kenitra",
    "SALE": "Salé",
    "sale": "Salé",
    "Sale": "Salé",
    "FES": "Fès",
    "fes": "Fès",
    "Fez": "Fès",
    "MEKNES": "Meknès",
}

FEATURE_FIELD_MAP = {
    "features_furniture": "furniture",
    "features_videoSurveillance": "video_surveillance",
    "features_privateGarden": "private_garden",
    "features_splitAirConditioning": "split_air_conditioning",
    "features_gym": "gym",
    "features_laundryRoom": "laundry_room",
    "features_loadLifter": "load_lifter",
    "features_sauna": "sauna",
    "features_equippedKitchen": "equipped_kitchen",
    "features_serviceDoor": "service_door",
    "features_storageSpace": "storage_space",
    "features_patio": "patio",
    "features_solarium": "solarium",
    "features_curtain": "curtain",
    "features_playground": "playground",
    "features_disabledAccess": "disabled_access",
    "features_outdoorParking": "outdoor_parking",
    "features_extractionSystem": "extraction_system",
    "features_elevator": "elevator",
    "features_privateHammam": "private_hammam",
    "features_garden": "garden",
    "features_wiring": "wiring",
    "features_coldStorage": "cold_storage",
    "features_privateSwimmingPool": "private_swimming_pool",
    "features_securityAgent": "security_agent",
    "features_undergroundParking": "underground_parking",
    "features_terrace": "terrace",
    "features_emergencyExit": "emergency_exit",
    "features_veranda": "veranda",
    "features_centralizedAirConditioning": "centralized_air_conditioning",
    "features_gatedCommunity": "gated_community",
    "features_janitor": "janitor",
    "features_electricWaterHeater": "electric_water_heater",
    "features_intercom": "intercom",
    "features_concierge": "concierge",
    "features_meetingRoom": "meeting_room",
    "features_greenSpaces": "green_spaces",
    "features_lobby": "lobby",
    "features_fireplace": "fireplace",
    "features_fiberInstallation": "fiber_installation",
    "features_splitHeating": "split_heating",
    "features_gasWaterHeater": "gas_water_heater",
    "features_maidsRooms": "maids_rooms",
    "features_interiorPatio": "interior_patio",
    "features_networkInstallation": "network_installation",
    "features_basement": "basement",
    "features_stove": "stove",
    "features_centralizedHeating": "centralized_heating",
    "features_thermalIsolation": "thermal_isolation",
    "features_americanKitchen": "american_kitchen",
    "features_balcony": "balcony",
    "features_domotique": "domotique",
    "features_undergroundParkingSpaces": "underground_parking_spaces",
    "features_totalBalconyArea": "total_balcony_area",
    "features_garage": "garage",
    "features_entryCode": "entry_code",
    "features_pool": "pool",
    "features_box": "box",
    "features_outdoorParkingSpaces": "outdoor_parking_spaces",
    "features_totalTerraceArea": "total_terrace_area",
    "features_gardenArea": "garden_area",
    "features_solariumArea": "solarium_area",
    "features_garageArea": "garage_area",
    "features_storageArea": "storage_area",
    "features_boxArea": "box_area",
}

NUMERIC_FEATURE_FIELDS = {
    "underground_parking_spaces",
    "outdoor_parking_spaces",
    "total_balcony_area",
    "total_terrace_area",
    "garden_area",
    "solarium_area",
    "garage_area",
    "storage_area",
    "box_area",
}

VALID_TRANSACTION_TYPES = {choice[0] for choice in Property.TRANSACTION_TYPE_CHOICES}
VALID_CATEGORIES = {choice[0] for choice in Property.CATEGORY_CHOICES}
VALID_TYPES = {choice[0] for choice in Property.TYPE_CHOICES}
VALID_STATUSES = {choice[0] for choice in Property.STATUS_CHOICES}
VALID_GENERAL_STATES = {choice[0] for choice in Property.GENERAL_STATE_CHOICES}
VALID_OCCUPATION_STATES = {choice[0] for choice in Property.OCCUPATION_STATE_CHOICES}


def clean_value(value):
    """Convert pandas NaN and blank strings to None."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def text_value(row, column, default=""):
    """Return a cleaned string value from a row."""
    value = clean_value(row.get(column))
    if value is None:
        return default
    return str(value).strip()


def decimal_value(value, default=None):
    """Convert scalar values to Decimal, guarding NaN and blanks."""
    value = clean_value(value)
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default


def int_value(value, default=None):
    """Convert scalar values to int, guarding NaN and blanks."""
    value = clean_value(value)
    if value is None:
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def bool_value(value) -> bool:
    """Convert pandas, string, and numeric booleans safely."""
    value = clean_value(value)
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def choice_value(value, valid_values, default=""):
    """Return a value only when it belongs to the configured model choices."""
    value = text_value({}, "", default="") if value is None else str(value).strip()
    if value in valid_values:
        return value
    return default


def datetime_value(value):
    """Parse a CSV/parquet datetime value into an aware datetime when possible."""
    value = clean_value(value)
    if value is None:
        return None
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    if hasattr(value, "tzinfo"):
        return timezone.make_aware(value) if timezone.is_naive(value) else value
    parsed = parse_datetime(str(value).strip())
    if parsed and timezone.is_naive(parsed):
        return timezone.make_aware(parsed)
    return parsed


def normalize_city_name(raw_name):
    """Normalize raw city names using aliases, then title-case fallback."""
    value = clean_value(raw_name)
    if value is None:
        return None
    value = str(value).strip()
    return CITY_ALIASES.get(value) or CITY_ALIASES.get(value.lower()) or value.title()


def parse_location(value):
    """Parse Yakeey location JSON formatted as [longitude, latitude]."""
    value = clean_value(value)
    if value is None:
        return None, None
    if not isinstance(value, (str, bytes)) and hasattr(value, "__iter__"):
        value = list(value)
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        longitude, latitude = value[0], value[1]
        return decimal_value(latitude), decimal_value(longitude)
    try:
        longitude, latitude = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None, None
    return decimal_value(latitude), decimal_value(longitude)


def parse_photos(value):
    """Parse Yakeey photos JSON into image dictionaries."""
    value = clean_value(value)
    if value is None:
        return []
    if not isinstance(value, (str, bytes)) and hasattr(value, "__iter__"):
        photos = list(value)
    else:
        try:
            photos = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
    if not isinstance(photos, list):
        return []

    parsed = []
    for index, photo in enumerate(photos):
        if not isinstance(photo, dict):
            continue
        url = clean_value(photo.get("url"))
        if not url:
            continue
        parsed.append(
            {
                "url": str(url),
                "order": int_value(photo.get("order"), default=index) or 0,
                "is_main": bool_value(photo.get("main")),
            }
        )
    return parsed


def parse_internal_address(value):
    """Parse the internalAddresses column and return the primary address dict."""
    value = clean_value(value)
    if value is None:
        return {}
    if not isinstance(value, (str, bytes)) and hasattr(value, "__iter__"):
        addresses = list(value)
    else:
        try:
            addresses = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
    if not isinstance(addresses, list):
        return {}
    for address in addresses:
        if isinstance(address, dict) and address.get("isPrimary"):
            return address
    return next((address for address in addresses if isinstance(address, dict)), {})


class Command(BaseCommand):
    """Import Yakeey listings from CSV or parquet into Django models."""

    help = "Import Yakeey CSV/parquet listings into the database."
    batch_size = 500

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, help="Path to Yakeey CSV/parquet file.")

    def handle(self, *args, **options):
        file_path = Path(options["file"])
        if not file_path.exists():
            raise CommandError(f"File not found: {file_path}")

        dataframe = self.read_dataframe(file_path)
        country, _ = Country.objects.get_or_create(
            code="MA", defaults={"name": "Morocco"}
        )

        stats = {"processed": 0, "created": 0, "updated": 0, "skipped": 0, "errors": 0}
        total_rows = len(dataframe)

        for start in range(0, total_rows, self.batch_size):
            batch = dataframe.iloc[start : start + self.batch_size]
            with transaction.atomic():
                for offset, row in enumerate(batch.to_dict("records"), start=start + 1):
                    if offset % 100 == 0:
                        self.stdout.write(f"Processed {offset}/{total_rows} rows...")
                    try:
                        with transaction.atomic():
                            outcome = self.import_row(row, country)
                    except Exception as exc:  # noqa: BLE001
                        stats["errors"] += 1
                        self.stderr.write(
                            f"Error on row {offset} ({text_value(row, 'userRef', 'unknown')}): {exc}"
                        )
                        continue

                    stats["processed"] += 1
                    stats[outcome] += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Import complete: "
                f"total processed={stats['processed']}, "
                f"created={stats['created']}, updated={stats['updated']}, "
                f"skipped={stats['skipped']}, errors={stats['errors']}"
            )
        )

    def read_dataframe(self, file_path):
        """Read parquet first and fall back to CSV when parquet parsing fails."""
        try:
            return pd.read_parquet(file_path)
        except Exception as parquet_error:  # noqa: BLE001
            try:
                return pd.read_csv(file_path)
            except Exception as csv_error:  # noqa: BLE001
                raise CommandError(
                    f"Could not read {file_path} as parquet or CSV. "
                    f"Parquet error: {parquet_error}; CSV error: {csv_error}"
                ) from csv_error

    def import_row(self, row, country):
        """Import one Yakeey row and return created, updated, or skipped."""
        yakeey_ref = text_value(row, "userRef")
        if not yakeey_ref:
            return "skipped"

        city_name = normalize_city_name(
            text_value(row, "mainInternalAddress_city")
            or text_value(row, "mainCity")
            or text_value(row, "city")
        )
        internal_address = parse_internal_address(row.get("internalAddresses"))
        if not city_name:
            city_name = normalize_city_name(internal_address.get("city"))
        if not city_name:
            raise ValueError("Missing city name.")

        city, _ = City.objects.get_or_create(name=city_name, defaults={"country": country})
        if city.country_id != country.id:
            city.country = country
            city.save(update_fields=["country"])

        district = None
        district_name = text_value(row, "mainInternalAddress_district") or text_value(
            internal_address, "district"
        )
        if district_name:
            district, _ = District.objects.get_or_create(
                name=district_name,
                city=city,
            )

        neighborhood = None
        neighborhood_name = text_value(
            row, "mainInternalAddress_neighborhood"
        ) or text_value(internal_address, "neighborhood")
        if neighborhood_name and district:
            neighborhood, _ = Neighborhood.objects.get_or_create(
                name=neighborhood_name,
                district=district,
            )

        latitude, longitude = parse_location(row.get("location"))
        description = fix_text(text_value(row, "description"))
        photos = parse_photos(row.get("photos"))

        defaults = {
            "transaction_type": choice_value(
                text_value(row, "transactionType"), VALID_TRANSACTION_TYPES, "SALE"
            ),
            "property_category": choice_value(
                text_value(row, "category"), VALID_CATEGORIES, ""
            ),
            "property_type": choice_value(text_value(row, "type"), VALID_TYPES, ""),
            "status": choice_value(text_value(row, "propertyStatus"), VALID_STATUSES, "LISTED"),
            "price": decimal_value(row.get("globalPrice"), default=Decimal("0")),
            "currency": text_value(row, "currency", "DH") or "DH",
            "area": decimal_value(row.get("area"), default=Decimal("0")),
            "built_area": decimal_value(row.get("builtArea")),
            "bedrooms": int_value(row.get("rooms"), default=0) or 0,
            "bathrooms": int_value(row.get("bathrooms"), default=0) or 0,
            "toilets": int_value(row.get("toilets"), default=0) or 0,
            "floor": int_value(row.get("floor")),
            "total_floors": int_value(row.get("totalFloors")),
            "construction_year": int_value(row.get("constructionYear")),
            "condominium_fees": int_value(row.get("condominiumFees")),
            "furnished": bool_value(row.get("furnished")),
            "is_new": bool_value(row.get("isNew")),
            "closed_residence": bool_value(row.get("closedResidence")),
            "is_verified": text_value(row, "propertyTag").upper() == "VERIFIED",
            "general_state": choice_value(
                text_value(row, "generalState"), VALID_GENERAL_STATES, ""
            ),
            "view": text_value(row, "view"),
            "occupation_state": choice_value(
                text_value(row, "occupationState"), VALID_OCCUPATION_STATES, ""
            ),
            "description": description,
            "cover_image_url": text_value(row, "photos_url"),
            "latitude": latitude,
            "longitude": longitude,
            "formatted_address": text_value(
                row, "mainInternalAddress_formattedAddress"
            )
            or text_value(internal_address, "formattedAddress"),
            "main_address": text_value(row, "mainAddress"),
            "source_url": text_value(row, "publicUrl"),
            "marketplace_url": text_value(row, "marketplaceUrl"),
            "agent_name": text_value(row, "agent_fullName"),
            "agent_phone": text_value(row, "agent_phoneNumber"),
            "registration_fees": decimal_value(row.get("priceDetails_registrationFees")),
            "total_acquisition_cost": decimal_value(row.get("priceDetails_totalPrice")),
            "city": city,
            "district": district,
            "neighborhood": neighborhood,
            "source": "yakeey",
            "property_tag": text_value(row, "propertyTag"),
            "listed_at": datetime_value(row.get("listingDate")),
            "created_at": datetime_value(row.get("createDate")),
        }

        property_obj, created = Property.objects.update_or_create(
            yakeey_ref=yakeey_ref,
            defaults=defaults,
        )

        PropertyImage.objects.filter(property=property_obj).delete()
        PropertyImage.objects.bulk_create(
            [
                PropertyImage(
                    property=property_obj,
                    url=photo["url"],
                    order=photo["order"],
                    is_main=photo["is_main"],
                )
                for photo in photos
            ]
        )

        feature_defaults = {}
        for csv_column, model_field in FEATURE_FIELD_MAP.items():
            if model_field in NUMERIC_FEATURE_FIELDS:
                feature_defaults[model_field] = decimal_value(row.get(csv_column))
            else:
                feature_defaults[model_field] = bool_value(row.get(csv_column))

        PropertyFeatures.objects.update_or_create(
            property=property_obj,
            defaults=feature_defaults,
        )

        return "created" if created else "updated"
