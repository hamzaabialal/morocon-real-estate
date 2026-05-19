"""Tests for the Sarouty API listing scraper."""
import asyncio

from django.db import DataError

from apps.scraper import listing_scraper


def api_listing(property_id=902719):
    return {
        "property_id": property_id,
        "property_sqft": 124,
        "total_bedroom": 2,
        "total_bathroom": 2,
        "property_furnished": "NO",
        "property_type": "Residential",
        "property_housing_type": "Appartement",
        "location_name": "Val Fleuri",
        "location_url_slug": "casablanca",
        "price": {"price": 1900000, "price_type": "sell"},
        "agent_company_id": 304,
        "agent_company_name": "TopImmobilier",
        "agent_company_phone": "+212670311548",
        "agent_company_email": "contact@example.com",
        "agent_company_logo": "https://example.com/logo.jpg",
        "agent_broker_name": "Agent Name",
        "agent_broker_phone": "+212670311548",
        "agent_broker_whatsapp_phone": "+212670311548",
        "images": [
            {"property_image_url": "https://example.com/image-1.jpg"},
            {"property_image_url": "https://example.com/image-2.jpg"},
        ],
    }


def api_detail():
    return {
        "property_id": 902719,
        "property_text_fr": "A real API listing description with enough detail.",
        "location": {
            "name_primary": "Val Fleuri",
            "url_city_slug": "casablanca",
            "coordinates_lat": 33.57,
            "coordinates_lon": -7.64,
        },
    }


def test_scrape_and_save_listing_fetches_detail_and_persists(monkeypatch):
    persisted = []

    async def fake_fetch_listing_detail(property_id):
        return api_detail()

    def fake_persist_api_listing(raw, job, url):
        persisted.append((raw, job, url))

    monkeypatch.setattr(
        listing_scraper,
        "fetch_listing_detail",
        fake_fetch_listing_detail,
    )
    monkeypatch.setattr(
        listing_scraper,
        "_persist_api_listing",
        fake_persist_api_listing,
    )

    result = asyncio.run(
        listing_scraper.scrape_and_save_listing(api_listing(), object())
    )

    assert result is True
    assert persisted[0][0]["property_id"] == 902719
    assert persisted[0][0]["location"]["coordinates_lat"] == 33.57
    assert persisted[0][2].endswith("listing_id=902719")


def test_scrape_and_save_listing_records_database_errors(monkeypatch):
    recorded_errors = []

    async def fake_fetch_listing_detail(property_id):
        return api_detail()

    def fake_persist_api_listing(raw, job, url):
        raise DataError("numeric field overflow")

    def fake_record_error(job, listing_id, url, message):
        recorded_errors.append((listing_id, message))

    monkeypatch.setattr(
        listing_scraper,
        "fetch_listing_detail",
        fake_fetch_listing_detail,
    )
    monkeypatch.setattr(
        listing_scraper,
        "_persist_api_listing",
        fake_persist_api_listing,
    )
    monkeypatch.setattr(listing_scraper, "_record_error", fake_record_error)

    result = asyncio.run(
        listing_scraper.scrape_and_save_listing(api_listing(850290), object())
    )

    assert result is False
    assert recorded_errors
    assert recorded_errors[0][0] == 850290
    assert "Database persistence failed" in recorded_errors[0][1]
    assert "numeric field overflow" in recorded_errors[0][1]


def test_scrape_listing_silently_dedups_missing_detail(monkeypatch):
    marked = []
    recorded_errors = []

    async def fake_fetch_listing_detail(property_id):
        return None

    def fake_mark_as_scraped(listing_id):
        marked.append(listing_id)

    def fake_record_error(job, listing_id, url, message):
        recorded_errors.append((listing_id, message))

    monkeypatch.setattr(
        listing_scraper,
        "fetch_listing_detail",
        fake_fetch_listing_detail,
    )
    monkeypatch.setattr(listing_scraper, "mark_as_scraped", fake_mark_as_scraped)
    monkeypatch.setattr(listing_scraper, "_record_error", fake_record_error)

    result = asyncio.run(listing_scraper.scrape_listing(850000, object()))

    assert result is False
    assert marked == [850000]
    assert recorded_errors == []
