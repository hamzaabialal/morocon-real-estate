"""Tests for Sarouty listing discovery."""
import asyncio

from apps.scraper import listing_discovery


def test_fetch_listing_ids_from_page_deduplicates_ids(monkeypatch):
    html = """
    <a href="/property-details/?listing_id=902701">A</a>
    <a href="https://www.sarouty.ma/property-details/?listing_id=902702">B</a>
    <button data-listing-id="902703">Save</button>
    <a href="/property-details/?listing_id=902701">Duplicate</a>
    <a href="/acheter/">Ignore</a>
    """

    async def fake_fetch_index_html(url):
        return html

    monkeypatch.setattr(listing_discovery, "fetch_index_html", fake_fetch_index_html)

    ids = asyncio.run(
        listing_discovery.fetch_listing_ids_from_page("https://www.sarouty.ma/acheter/")
    )

    assert ids == [902703, 902701, 902702]


def test_discover_all_listing_ids_paginates_and_filters_scraped(monkeypatch):
    async def fake_fetch_listing_ids_from_page(url):
        if url == listing_discovery.SALE_INDEX_URL:
            return [1, 2]
        if url == listing_discovery.SALE_INDEX_URL + "page/2/":
            return [2, 3]
        if url == listing_discovery.RENT_INDEX_URL:
            return [3, 4]
        return []

    monkeypatch.setattr(
        listing_discovery,
        "fetch_listing_ids_from_page",
        fake_fetch_listing_ids_from_page,
    )
    async def fake_fetch_index_html(url):
        return ""

    monkeypatch.setattr(listing_discovery, "fetch_index_html", fake_fetch_index_html)
    monkeypatch.setattr(
        listing_discovery,
        "is_already_scraped",
        lambda listing_id: listing_id == 2,
    )

    ids = asyncio.run(listing_discovery.discover_all_listing_ids())

    assert ids == [1, 3, 4]


def test_run_discovery_updates_job_notes(monkeypatch):
    class FakeJob:
        def __init__(self):
            self.notes = ""
            self.saved_update_fields = None

        def save(self, update_fields=None):
            self.saved_update_fields = update_fields

    async def fake_discover_all_listing_ids():
        return [902701, 902702]

    monkeypatch.setattr(
        listing_discovery,
        "discover_all_listing_ids",
        fake_discover_all_listing_ids,
    )
    job = FakeJob()

    ids = asyncio.run(listing_discovery.run_discovery(job))

    assert ids == [902701, 902702]
    assert job.notes == "Listing discovery found 2 new Sarouty listing IDs."
    assert job.saved_update_fields == ["notes"]
