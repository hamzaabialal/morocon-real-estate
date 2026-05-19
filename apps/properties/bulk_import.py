"""CSV/Excel parsing for bulk listing imports.

Expected columns (all case-insensitive; only required ones marked *):
  yakeey_ref *        unique listing reference (string)
  transaction_type *  SALE or RENT
  property_category * VILLA / HOUSE / FLAT / RIAD / OFFICE / TERRAIN / COMMERCIAL_BUILDING
  property_type       APARTMENT / STUDIO / DUPLEX / TRIPLEX / RIAD / OFFICE / etc.
  city *              city name (case-insensitive)
  price *             integer MAD
  area *              decimal m²
  bedrooms            integer (default 0)
  bathrooms           integer (default 0)
  description         free text
  cover_image_url     optional public URL; if blank, AI generates one
"""
import io
import logging

from apps.locations.models import City


logger = logging.getLogger(__name__)


REQUIRED_FIELDS = {"yakeey_ref", "transaction_type", "property_category", "city", "price", "area"}
INT_FIELDS = {"bedrooms", "bathrooms"}
DECIMAL_FIELDS = {"price", "area"}
VALID_TRANSACTION_TYPES = {"SALE", "RENT"}
VALID_CATEGORIES = {"VILLA", "HOUSE", "FLAT", "RIAD", "OFFICE", "TERRAIN", "COMMERCIAL_BUILDING"}


def parse_file(file_obj):
    """Parse an uploaded CSV or Excel file into a list of normalized row dicts.

    Returns (rows, errors) — rows are ready-to-create dicts, errors describe
    rows that couldn't be parsed (with their 1-based row numbers).
    """
    filename = getattr(file_obj, "name", "uploaded")
    raw_bytes = file_obj.read()

    try:
        import pandas as pd
    except ImportError as exc:
        return [], [f"pandas is required for bulk import ({exc})"]

    try:
        if filename.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(raw_bytes))
        else:
            df = pd.read_csv(io.BytesIO(raw_bytes))
    except Exception as exc:
        return [], [f"Could not parse file: {exc}"]

    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

    missing = REQUIRED_FIELDS - set(df.columns)
    if missing:
        return [], [f"Missing required columns: {', '.join(sorted(missing))}"]

    city_cache = {c.name.lower(): c for c in City.objects.all()}
    rows = []
    errors = []

    for idx, raw_row in df.iterrows():
        row_no = idx + 2
        try:
            row = clean_row(raw_row, city_cache)
            rows.append(row)
        except ValueError as exc:
            errors.append(f"Row {row_no}: {exc}")

    return rows, errors


def clean_row(raw_row, city_cache):
    """Normalize one row + validate."""
    row = {}
    for col in raw_row.index:
        value = raw_row[col]
        if _is_blank(value):
            continue
        row[col] = value

    for field in REQUIRED_FIELDS:
        if field not in row:
            raise ValueError(f"missing required field '{field}'")

    row["yakeey_ref"] = str(row["yakeey_ref"]).strip()

    tx = str(row["transaction_type"]).strip().upper()
    if tx not in VALID_TRANSACTION_TYPES:
        raise ValueError(f"transaction_type must be SALE or RENT (got '{tx}')")
    row["transaction_type"] = tx

    cat = str(row["property_category"]).strip().upper().replace(" ", "_")
    if cat not in VALID_CATEGORIES:
        raise ValueError(f"property_category not recognized: '{cat}'")
    row["property_category"] = cat

    if "property_type" in row:
        row["property_type"] = str(row["property_type"]).strip().upper().replace(" ", "_")

    city_name = str(row["city"]).strip().lower()
    city = city_cache.get(city_name)
    if not city:
        raise ValueError(f"city '{row['city']}' not found (seed cities first)")
    row["city"] = city

    for field in DECIMAL_FIELDS:
        try:
            row[field] = float(row[field])
        except (TypeError, ValueError):
            raise ValueError(f"{field} must be numeric (got '{row[field]}')")

    for field in INT_FIELDS:
        if field in row:
            try:
                row[field] = int(float(row[field]))
            except (TypeError, ValueError):
                raise ValueError(f"{field} must be an integer (got '{row[field]}')")

    if "description" in row:
        row["description"] = str(row["description"]).strip()

    if "cover_image_url" in row:
        row["cover_image_url"] = str(row["cover_image_url"]).strip()

    return row


def _is_blank(v):
    if v is None:
        return True
    try:
        import math
        if isinstance(v, float) and math.isnan(v):
            return True
    except Exception:
        pass
    if isinstance(v, str) and not v.strip():
        return True
    return False


SAMPLE_CSV = """yakeey_ref,transaction_type,property_category,property_type,city,price,area,bedrooms,bathrooms,description
DEMO-001,SALE,VILLA,ISOLATED_HOUSE,Casablanca,4500000,320,4,3,Sun-drenched villa in Anfa with sea views
DEMO-002,SALE,RIAD,RIAD,Marrakech,6800000,280,5,4,Restored riad in the Medina with central fountain
DEMO-003,RENT,FLAT,APARTMENT,Rabat,12000,140,3,2,Modern apartment in Hassan with parking
"""
