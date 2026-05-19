"""Redis-backed listing deduplication for Sarouty scraping."""
from typing import Any

from django.core.cache import caches

REDIS_SET_KEY = "sarouty:scraped_ids"
EXPIRY_SECONDS = 30 * 24 * 60 * 60


def get_redis_client() -> Any:
    """Return the redis-py client backing Django's default cache."""
    cache = caches["default"]
    if hasattr(cache, "_cache") and hasattr(cache._cache, "get_client"):
        return cache._cache.get_client(None, write=True)
    raise RuntimeError("Default Django cache does not expose a Redis client.")


def is_already_scraped(listing_id: int) -> bool:
    """Return whether a listing id is present in the Redis dedup SET."""
    client = get_redis_client()
    return bool(client.sismember(REDIS_SET_KEY, str(listing_id)))


def mark_as_scraped(listing_id: int) -> None:
    """Add a listing id to the Redis dedup SET and refresh key expiry."""
    client = get_redis_client()
    client.sadd(REDIS_SET_KEY, str(listing_id))
    client.expire(REDIS_SET_KEY, EXPIRY_SECONDS)
