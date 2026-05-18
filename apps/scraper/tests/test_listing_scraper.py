"""Tests for the individual listing scraper orchestration."""
import asyncio

from django.db import DataError

from apps.scraper import listing_scraper
from apps.scraper.listing_parser import SaroutyListing


def test_scrape_listing_uses_playwright_when_httpx_data_is_low_quality(monkeypatch):
    calls = []
    persisted = []

    async def fake_fetch_html(url, use_playwright=False):
        calls.append(use_playwright)
        return "html"

    def fake_parse_listing_html(html, listing_id):
        is_playwright = len(calls) == 2
        return SaroutyListing(
            sarouty_id=listing_id,
            price=1000000 if is_playwright else 0,
            property_type="Appartement",
            listing_type="SALE",
            area=90,
            rooms=None,
            bathrooms=None,
            floor=None,
            total_floors=None,
            construction_year=None,
            furnished=False,
            city_raw="Casablanca",
            neighborhood_raw="Maarif",
            main_address="Maarif, Casablanca",
            latitude=None,
            longitude=None,
            description=(
                "A real listing description with enough useful detail."
                if is_playwright
                else "Consultez les détails complets"
            ),
            amenities=[],
            photo_urls=[],
            agency_name="Best Home" if is_playwright else "Sarouty",
            agency_phone="0612345678" if is_playwright else "212520506262",
            agency_whatsapp=None,
            agency_logo_url=None,
            agency_profile_url=None,
        )

    def fake_persist_listing(parsed, job, url):
        persisted.append((parsed, job, url))

    monkeypatch.setattr(listing_scraper, "fetch_html", fake_fetch_html)
    monkeypatch.setattr(listing_scraper, "parse_listing_html", fake_parse_listing_html)
    monkeypatch.setattr(listing_scraper, "_persist_listing", fake_persist_listing)

    result = asyncio.run(listing_scraper.scrape_listing(902701, object()))

    assert result is True
    assert calls == [False, True]
    assert persisted[0][0].agency_phone == "0612345678"


def test_scrape_listing_records_database_errors(monkeypatch):
    recorded_errors = []

    async def fake_fetch_html(url, use_playwright=False):
        return "html"

    def fake_parse_listing_html(html, listing_id):
        return SaroutyListing(
            sarouty_id=listing_id,
            price=1000000,
            property_type="Appartement",
            listing_type="SALE",
            area=90,
            rooms=None,
            bathrooms=None,
            floor=None,
            total_floors=None,
            construction_year=None,
            furnished=False,
            city_raw="Casablanca",
            neighborhood_raw="Maarif",
            main_address="Maarif, Casablanca",
            latitude=None,
            longitude=None,
            description="A real listing description with enough useful detail.",
            amenities=[],
            photo_urls=[],
            agency_name="Best Home",
            agency_phone="0612345678",
            agency_whatsapp=None,
            agency_logo_url=None,
            agency_profile_url=None,
        )

    def fake_persist_listing(parsed, job, url):
        raise DataError("numeric field overflow")

    def fake_record_error(job, listing_id, url, message):
        recorded_errors.append((listing_id, message))

    monkeypatch.setattr(listing_scraper, "fetch_html", fake_fetch_html)
    monkeypatch.setattr(listing_scraper, "parse_listing_html", fake_parse_listing_html)
    monkeypatch.setattr(listing_scraper, "_persist_listing", fake_persist_listing)
    monkeypatch.setattr(listing_scraper, "_record_error", fake_record_error)

    result = asyncio.run(listing_scraper.scrape_listing(850290, object()))

    assert result is False
    assert recorded_errors
    assert recorded_errors[0][0] == 850290
    assert "Database persistence failed" in recorded_errors[0][1]
    assert "numeric field overflow" in recorded_errors[0][1]


def test_scrape_listing_silently_dedups_dead_listing(monkeypatch):
    marked = []
    recorded_errors = []

    async def fake_fetch_html(url, use_playwright=False):
        return "<html><body>Property not available</body></html>"

    def fake_parse_listing_html(html, listing_id):
        return None

    def fake_mark_as_scraped(listing_id):
        marked.append(listing_id)

    def fake_record_error(job, listing_id, url, message):
        recorded_errors.append((listing_id, message))

    monkeypatch.setattr(listing_scraper, "fetch_html", fake_fetch_html)
    monkeypatch.setattr(listing_scraper, "parse_listing_html", fake_parse_listing_html)
    monkeypatch.setattr(listing_scraper, "mark_as_scraped", fake_mark_as_scraped)
    monkeypatch.setattr(listing_scraper, "_record_error", fake_record_error)

    result = asyncio.run(listing_scraper.scrape_listing(850200, object()))

    assert result is False
    assert marked == [850200]
    assert recorded_errors == []
