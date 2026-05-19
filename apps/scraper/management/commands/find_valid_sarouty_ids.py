"""Print currently visible Sarouty listing IDs from the sale index."""
import asyncio

from django.core.management.base import BaseCommand

from apps.scraper.listing_discovery import (
    SALE_INDEX_URL,
    extract_index_links_from_html,
    extract_listing_ids_from_html,
    fetch_index_html,
    fetch_listing_ids_from_page,
)


class Command(BaseCommand):
    help = "Find valid Sarouty listing IDs from the public sale index"

    def add_arguments(self, parser):
        parser.add_argument("--sample", type=int, default=20)

    def handle(self, *args, **options):
        sample_size = max(1, options["sample"])
        ids = asyncio.run(find_ids(sample_size))
        for listing_id in ids[:sample_size]:
            self.stdout.write(str(listing_id))
        if not ids:
            self.stdout.write("No listing IDs found.")


async def find_ids(sample_size: int) -> list[int]:
    ids = await fetch_listing_ids_from_page(SALE_INDEX_URL)
    if len(ids) >= sample_size:
        return ids

    html = await fetch_index_html(SALE_INDEX_URL)
    if not html:
        return ids

    seen = set(ids)
    for link in extract_index_links_from_html(html, mode="buy"):
        for listing_id in await fetch_listing_ids_from_page(link):
            if listing_id in seen:
                continue
            seen.add(listing_id)
            ids.append(listing_id)
            if len(ids) >= sample_size:
                return ids
    return ids
