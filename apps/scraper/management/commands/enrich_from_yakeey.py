"""Enrich Sarouty properties with Yakeey financial data."""
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from ftfy import fix_text

from apps.properties.models import Property
from apps.scraper.listing_scraper import normalize_city_name, normalize_property_type


BATCH_SIZE = 200


class Command(BaseCommand):
    help = "Enrich Sarouty properties from a Yakeey parquet or CSV file"

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, dest="file_path")

    def handle(self, *args, **options):
        file_path = Path(options["file_path"])
        if not file_path.exists():
            raise CommandError(f"File not found: {file_path}")

        dataframe = load_dataframe(file_path)
        dataframe = fix_text_columns(dataframe)

        summary = {
            "matched_high": 0,
            "matched_medium": 0,
            "skipped": 0,
            "total_processed": 0,
        }

        for start in range(0, len(dataframe), BATCH_SIZE):
            batch = dataframe.iloc[start : start + BATCH_SIZE]
            with transaction.atomic():
                for _, row in batch.iterrows():
                    result = enrich_row(row)
                    summary["total_processed"] += 1
                    if result == "HIGH":
                        summary["matched_high"] += 1
                    elif result == "MEDIUM":
                        summary["matched_medium"] += 1
                    else:
                        summary["skipped"] += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Yakeey enrichment complete: "
                f"matched_high={summary['matched_high']}, "
                f"matched_medium={summary['matched_medium']}, "
                f"skipped={summary['skipped']}, "
                f"total_processed={summary['total_processed']}"
            )
        )


def load_dataframe(file_path: Path) -> pd.DataFrame:
    suffix = file_path.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(file_path)
    if suffix == ".csv":
        return pd.read_csv(file_path)
    raise CommandError("Unsupported file type. Use .parquet or .csv")


def fix_text_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    for column in dataframe.select_dtypes(include=["object", "string"]).columns:
        dataframe[column] = dataframe[column].map(
            lambda value: fix_text(value) if isinstance(value, str) else value
        )
    return dataframe


def enrich_row(row) -> str | None:
    city = normalize_city_name(text_value(row, ["city", "address_city", "location_city"]))
    neighborhood = text_value(
        row,
        ["neighborhood", "district", "address_neighborhood", "location_neighborhood"],
    )
    listing_type = normalize_listing_type(
        text_value(row, ["transactionType", "transaction_type", "listing_type"])
    )
    property_type = normalize_yakeey_property_type(
        text_value(row, ["type", "property_type", "propertyType"])
    )
    area = decimal_value(row_value(row, ["area", "surface", "builtArea", "livingArea"]))
    price = decimal_value(row_value(row, ["globalPrice", "price", "priceDetails_totalPrice"]))

    if not city or not listing_type or not property_type or area is None or price is None:
        return None

    candidates = Property.objects.filter(
        city__name__iexact=city,
        listing_type=listing_type,
        property_type__iexact=property_type,
    )
    if neighborhood:
        candidates = candidates.filter(neighborhood__name__iexact=neighborhood)

    best_match = None
    best_score = 0
    for prop in candidates:
        score = match_score(prop, city, neighborhood, property_type, area, price)
        if score > best_score:
            best_match = prop
            best_score = score

    if best_match is None or best_score < 4:
        return None

    confidence = "HIGH" if best_score == 5 else "MEDIUM"
    apply_enrichment(best_match, row, confidence)
    return confidence


def match_score(prop, city, neighborhood, property_type, area, price) -> int:
    score = 0
    if prop.city and prop.city.name.lower() == city.lower():
        score += 1
    if neighborhood and prop.neighborhood and prop.neighborhood.name.lower() == neighborhood.lower():
        score += 1
    if prop.property_type.lower() == property_type.lower():
        score += 1
    if within_percent(prop.area, area, Decimal("0.03")):
        score += 1
    if within_percent(prop.price, price, Decimal("0.05")):
        score += 1
    return score


def apply_enrichment(prop, row, confidence: str) -> None:
    prop.yakeey_id = text_value(row, ["userRef", "yakeey_id", "id"]) or prop.yakeey_id
    prop.enrichment_confidence = confidence
    prop.registration_fees = decimal_value(
        row_value(row, ["priceDetails_registrationFees"])
    )
    prop.land_registration_fees = decimal_value(
        row_value(row, ["priceDetails_landRegistrationFees"])
    )
    prop.notary_fees = decimal_value(
        row_value(row, ["priceDetails_notaryFeesWithoutTaxes"])
    )
    prop.total_acquisition_cost = decimal_value(
        row_value(row, ["priceDetails_totalPrice"])
    )
    prop.scrape_status = "ENRICHED"
    prop.save(
        update_fields=[
            "yakeey_id",
            "enrichment_confidence",
            "registration_fees",
            "land_registration_fees",
            "notary_fees",
            "total_acquisition_cost",
            "scrape_status",
            "updated_at",
        ]
    )


def row_value(row, columns: list[str]):
    for column in columns:
        if column in row and not pd.isna(row[column]):
            return row[column]
    return None


def text_value(row, columns: list[str]) -> str:
    value = row_value(row, columns)
    if value is None:
        return ""
    return str(value).strip()


def decimal_value(value) -> Decimal | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def within_percent(left, right, tolerance: Decimal) -> bool:
    left = decimal_value(left)
    right = decimal_value(right)
    if left is None or right in (None, Decimal("0")):
        return False
    return abs(left - right) / right <= tolerance


def normalize_listing_type(value: str) -> str:
    lowered = value.lower()
    if lowered in {"rent", "rental", "location", "louer", "RENT".lower()}:
        return "RENT"
    if lowered in {"sale", "sell", "vente", "acheter", "SALE".lower()}:
        return "SALE"
    return value.upper()


def normalize_yakeey_property_type(value: str) -> str:
    normalized = normalize_property_type(value)
    return normalized or value.strip().upper()
