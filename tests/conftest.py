from decimal import Decimal

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.agencies.models import Agency, User
from apps.locations.models import City, Country, District, Neighborhood
from apps.properties.models import Property


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def morocco():
    country, _ = Country.objects.get_or_create(code="MA", defaults={"name": "Morocco"})
    return country


@pytest.fixture
def city(morocco):
    city, _ = City.objects.get_or_create(name="Casablanca", country=morocco)
    return city


@pytest.fixture
def district(city):
    district, _ = District.objects.get_or_create(name="Maarif", city=city)
    return district


@pytest.fixture
def neighborhood(district):
    neighborhood, _ = Neighborhood.objects.get_or_create(
        name="Gauthier", district=district
    )
    return neighborhood


@pytest.fixture
def agency(city):
    return Agency.objects.create(
        name="Yakeey Test Agency",
        phone="212600000000",
        email="agency@example.com",
        city=city,
        source="self_registered",
    )


@pytest.fixture
def agency_user(agency):
    return User.objects.create_user(
        email="owner@example.com",
        password="strong-password",
        first_name="Agency",
        last_name="Owner",
        role=User.Role.AGENCY_OWNER,
        agency=agency,
    )


@pytest.fixture
def authenticated_agency_user(api_client, agency_user):
    refresh = RefreshToken.for_user(agency_user)
    token = str(refresh.access_token)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return {"client": api_client, "user": agency_user, "token": token}


@pytest.fixture
def sample_property(city, district, neighborhood, agency):
    return Property.objects.create(
        yakeey_ref="TEST-001",
        transaction_type="SALE",
        property_category="FLAT",
        property_type="APARTMENT",
        status="LISTED",
        price=Decimal("1200000.00"),
        currency="DH",
        area=Decimal("95.00"),
        bedrooms=2,
        bathrooms=1,
        toilets=1,
        city=city,
        district=district,
        neighborhood=neighborhood,
        agency=agency,
        description="Test apartment in Casablanca",
        cover_image_url="https://example.com/image.jpg",
    )
