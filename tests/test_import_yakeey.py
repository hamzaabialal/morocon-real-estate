import csv
import json

import pytest
from django.core.management import call_command

from apps.locations.models import City, District, Neighborhood
from apps.properties.models import Property, PropertyFeatures, PropertyImage


def write_import_csv(path, price="1200000", description="Appartement test"):
    fieldnames = [
        "userRef",
        "transactionType",
        "category",
        "type",
        "globalPrice",
        "currency",
        "area",
        "rooms",
        "bathrooms",
        "toilets",
        "floor",
        "totalFloors",
        "constructionYear",
        "furnished",
        "isNew",
        "generalState",
        "view",
        "description",
        "mainInternalAddress_city",
        "mainInternalAddress_district",
        "mainInternalAddress_neighborhood",
        "mainInternalAddress_formattedAddress",
        "location",
        "mainAddress",
        "publicUrl",
        "marketplaceUrl",
        "photos",
        "photos_url",
        "photos_count",
        "agent_fullName",
        "agent_phoneNumber",
        "propertyTag",
        "propertyStatus",
        "priceDetails_registrationFees",
        "priceDetails_totalPrice",
        "createDate",
        "listingDate",
        "builtArea",
        "condominiumFees",
        "occupationState",
        "closedResidence",
        "features_elevator",
        "features_balcony",
        "features_totalBalconyArea",
    ]
    row = {
        "userRef": "IMP-001",
        "transactionType": "SALE",
        "category": "FLAT",
        "type": "APARTMENT",
        "globalPrice": price,
        "currency": "DH",
        "area": "100",
        "rooms": "2",
        "bathrooms": "1",
        "toilets": "1",
        "floor": "3",
        "totalFloors": "5",
        "constructionYear": "2018",
        "furnished": "true",
        "isNew": "false",
        "generalState": "GOOD",
        "view": "Sea",
        "description": description,
        "mainInternalAddress_city": "casablanca",
        "mainInternalAddress_district": "Maarif",
        "mainInternalAddress_neighborhood": "Gauthier",
        "mainInternalAddress_formattedAddress": "Gauthier, Casablanca",
        "location": "[-7.6298,33.5908]",
        "mainAddress": "Gauthier",
        "publicUrl": "https://example.com/public",
        "marketplaceUrl": "https://example.com/marketplace",
        "photos": json.dumps(
            [{"url": "https://example.com/1.jpg", "order": 0, "main": True}]
        ),
        "photos_url": "https://example.com/1.jpg",
        "photos_count": "1",
        "agent_fullName": "Agent Test",
        "agent_phoneNumber": "212600000001",
        "propertyTag": "VERIFIED",
        "propertyStatus": "LISTED",
        "priceDetails_registrationFees": "50000",
        "priceDetails_totalPrice": "1250000",
        "createDate": "2024-01-01T10:00:00Z",
        "listingDate": "2024-01-02T10:00:00Z",
        "builtArea": "90",
        "condominiumFees": "300",
        "occupationState": "EMPTY",
        "closedResidence": "false",
        "features_elevator": "true",
        "features_balcony": "true",
        "features_totalBalconyArea": "8",
    }
    with path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(row)


@pytest.mark.django_db
def test_import_creates_and_deduplicates_locations(tmp_path):
    import_file = tmp_path / "yakeey.csv"
    write_import_csv(import_file)

    call_command("import_yakeey", file=str(import_file))
    call_command("import_yakeey", file=str(import_file))

    assert City.objects.filter(name="Casablanca").count() == 1
    city = City.objects.get(name="Casablanca")
    assert District.objects.filter(name="Maarif", city=city).count() == 1
    district = District.objects.get(name="Maarif", city=city)
    assert Neighborhood.objects.filter(name="Gauthier", district=district).count() == 1


@pytest.mark.django_db
def test_import_upserts_property_by_yakeey_ref(tmp_path):
    import_file = tmp_path / "yakeey.csv"
    write_import_csv(import_file, price="1200000", description="Original")
    call_command("import_yakeey", file=str(import_file))

    write_import_csv(import_file, price="1500000", description="Updated")
    call_command("import_yakeey", file=str(import_file))

    assert Property.objects.filter(yakeey_ref="IMP-001").count() == 1
    prop = Property.objects.get(yakeey_ref="IMP-001")
    assert prop.price == 1500000
    assert prop.description == "Updated"
    assert PropertyImage.objects.filter(property=prop).count() == 1
    assert PropertyFeatures.objects.get(property=prop).elevator is True
