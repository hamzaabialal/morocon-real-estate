"""Enrich existing Sarouty properties with Yakeey financial data."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from ftfy import fix_text

from apps.properties.models import Property
from apps.scraper.listing_scraper import normalize_property_type


BATCH_SIZE = 200
CITY_ALIASES = {
    "casablanca": "Casablanca",
    "casa blanca": "Casablanca",
    "marrakesh": "Marrakech",
    "marrakch": "Marrakech",
    "mohammédia": "Mohammedia",
    "mohammedia": "Mohammedia",
    "mohammadia": "Mohammedia",
    "dar bouazza": "Dar Bouazza",
    "darbouazza": "Dar Bouazza",
}


class Command(BaseCommand):
    help = "Enrich existing Sarouty properties from a Yakeey parquet or CSV file"

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, dest="file_path")

    def handle(self, *args, **options):
        file_path = resolve_file_path(Path(options["file_path"]))
        dataframe = load_dataframe(file_path)
        print_fee_column_diagnostics(dataframe)
        dataframe = fix_text_columns(dataframe)

        totals = {
            "high": 0,
            "medium": 0,
            "skipped": 0,
            "processed": 0,
            "enriched_ids": set(),
        }

        for batch_number, start in enumerate(range(0, len(dataframe), BATCH_SIZE), start=1):
            batch_counts = {"high": 0, "medium": 0, "skipped": 0}
            batch = dataframe.iloc[start : start + BATCH_SIZE]

            with transaction.atomic():
                for _, row in batch.iterrows():
                    result, property_id = enrich_row(row)
                    totals["processed"] += 1

                    if result == "HIGH":
                        batch_counts["high"] += 1
                        totals["high"] += 1
                        totals["enriched_ids"].add(property_id)
                    elif result == "MEDIUM":
                        batch_counts["medium"] += 1
                        totals["medium"] += 1
                        totals["enriched_ids"].add(property_id)
                    else:
                        batch_counts["skipped"] += 1
                        totals["skipped"] += 1

            self.stdout.write(
                f"Batch {batch_number}: "
                f"{batch_counts['high']} high, "
                f"{batch_counts['medium']} medium, "
                f"{batch_counts['skipped']} skipped"
            )

        self.stdout.write(f"Total Yakeey rows: {len(dataframe)}")
        self.stdout.write(f"HIGH confidence matches: {totals['high']}")
        self.stdout.write(f"MEDIUM confidence matches: {totals['medium']}")
        self.stdout.write(f"Skipped: {totals['skipped']}")
        self.stdout.write(f"Properties enriched: {len(totals['enriched_ids'])}")


def resolve_file_path(file_path: Path) -> Path:
    if file_path.exists():
        return file_path

    fallback = Path(file_path.name)
    if fallback.exists():
        return fallback

    raise CommandError(f"File not found: {file_path}")


def load_dataframe(file_path: Path) -> pd.DataFrame:
    suffix = file_path.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(file_path)
    if suffix == ".csv":
        return pd.read_csv(file_path)
    raise CommandError("Unsupported file type. Use .parquet or .csv.")


def print_fee_column_diagnostics(dataframe: pd.DataFrame) -> None:
    fee_columns = [
        column
        for column in dataframe.columns
        if "price" in column.lower()
        or "fee" in column.lower()
        or "notary" in column.lower()
        or "registration" in column.lower()
    ]
    print("Columns:", fee_columns)
    for column in fee_columns:
        values = dataframe[column].dropna()
        first_value = None if values.empty else values.iloc[0]
        print(
            f"{column}: first_non_null={first_value!r}; "
            f"nulls={dataframe[column].isna().sum()} / {len(dataframe)}"
        )


def fix_text_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    for column in dataframe.select_dtypes(include=["object", "string"]).columns:
        dataframe[column] = dataframe[column].map(fix_text_value)
    return dataframe


def fix_text_value(value: Any) -> Any:
    return fix_text(value) if isinstance(value, str) else value


def enrich_row(row) -> tuple[str | None, Any]:
    city = normalize_city(text_value(row, ["city", "mainCity", "mainInternalAddress_city"]))
    neighborhood = normalize_text(
        text_value(row, ["neighborhood", "mainNeighborhood", "mainInternalAddress_neighborhood"])
    )
    property_type = normalize_yakeey_property_type(
        text_value(row, ["type", "propertyType", "property_type"])
    )
    area = decimal_value(row_value(row, ["area", "listingArea", "builtArea"]))
    price = decimal_value(row_value(row, ["globalPrice", "price", "priceDetails_salePrice"]))

    if not city or not neighborhood or not property_type or area is None or price is None:
        return None, None

    candidates = Property.objects.filter(
        city__name__iexact=city,
        neighborhood__name__iexact=neighborhood,
        property_type__iexact=property_type,
    ).select_related("city", "neighborhood")

    best_match = None
    best_score = 0
    for prop in candidates.iterator():
        score = match_score(prop, city, neighborhood, property_type, area, price)
        if score > best_score:
            best_match = prop
            best_score = score

    if best_match is None or best_score < 4:
        return None, None

    confidence = "HIGH" if best_score == 5 else "MEDIUM"
    apply_enrichment(best_match, row, confidence)
    return confidence, best_match.pk


def match_score(prop: Property, city: str, neighborhood: str, property_type: str, area: Decimal, price: Decimal) -> int:
    score = 0
    if prop.city and prop.city.name.lower() == city.lower():
        score += 1
    if prop.neighborhood and prop.neighborhood.name.lower() == neighborhood.lower():
        score += 1
    if prop.property_type.lower() == property_type.lower():
        score += 1
    if within_percent(prop.area, area, Decimal("0.03")):
        score += 1
    if within_percent(prop.price, price, Decimal("0.05")):
        score += 1
    return score


def apply_enrichment(prop: Property, row, confidence: str) -> None:
    update_fields = [
        "yakeey_id",
        "enrichment_confidence",
        "scrape_status",
        "updated_at",
    ]

    prop.yakeey_id = text_value(row, ["userRef", "yakeey_id", "id"]) or prop.yakeey_id
    prop.enrichment_confidence = confidence
    prop.scrape_status = "ENRICHED"

    fee_fields = {
        "registration_fees": ["priceDetails_registrationFees"],
        "land_registration_fees": ["priceDetails_landRegistrationFees"],
        "notary_fees": ["priceDetails_notaryFeesWithoutTaxes"],
        "total_acquisition_cost": ["priceDetails_totalPrice"],
    }
    for field_name, columns in fee_fields.items():
        value = decimal_value(row_value(row, columns))
        if value is not None:
            setattr(prop, field_name, value)
            update_fields.append(field_name)

    prop.save(update_fields=update_fields)


def row_value(row, columns: list[str]):
    for column in columns:
        if column in row and not is_missing(row[column]):
            return row[column]
    return None


def text_value(row, columns: list[str]) -> str:
    value = row_value(row, columns)
    if value is None:
        return ""
    return str(value).strip()


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        return False
    if isinstance(missing, bool):
        return missing
    return False


def decimal_value(value) -> Decimal | None:
    if value is None or is_missing(value):
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return None


def within_percent(left, right, tolerance: Decimal) -> bool:
    left_decimal = decimal_value(left)
    right_decimal = decimal_value(right)
    if left_decimal is None or right_decimal in (None, Decimal("0.00")):
        return False
    return abs(left_decimal - right_decimal) / right_decimal <= tolerance


def normalize_city(value: str) -> str:
    cleaned = normalize_text(value)
    if not cleaned:
        return ""
    return CITY_ALIASES.get(cleaned.lower(), cleaned.title())


def normalize_text(value: str) -> str:
    return " ".join(str(value or "").strip().split())


def normalize_yakeey_property_type(value: str) -> str:
    normalized = normalize_property_type(value)
    return normalized or normalize_text(value).upper()
