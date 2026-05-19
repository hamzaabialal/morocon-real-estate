"""Redis-backed listing deduplication for Sarouty scraping."""
import logging
from typing import Any

import redis
from django.conf import settings

REDIS_SET_KEY = "sarouty:scraped_ids"
EXPIRY_SECONDS = 30 * 24 * 60 * 60
logger = logging.getLogger(__name__)

_redis_client = None


def get_redis_client() -> Any:
    """Return a redis-py client for the configured Redis URL."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
            decode_responses=True,
        )
    return _redis_client


def is_already_scraped(listing_id: int) -> bool:
    """Return whether a listing id is present in the Redis dedup SET."""
    try:
        client = get_redis_client()
        return bool(client.sismember(REDIS_SET_KEY, str(listing_id)))
    except redis.RedisError:
        logger.warning("Redis dedup check failed for listing %s", listing_id, exc_info=True)
        return False


def mark_as_scraped(listing_id: int) -> None:
    """Add a listing id to the Redis dedup SET and refresh key expiry."""
    try:
        client = get_redis_client()
        client.sadd(REDIS_SET_KEY, str(listing_id))
        client.expire(REDIS_SET_KEY, EXPIRY_SECONDS)
    except redis.RedisError:
        logger.warning("Redis dedup mark failed for listing %s", listing_id, exc_info=True)


def filter_unscraped_ids(listing_ids: list[int]) -> set[int]:
    """Return listing ids that are not present in Redis, using one bulk round-trip."""
    if not listing_ids:
        return set()
    normalized_ids = [str(listing_id) for listing_id in listing_ids]
    try:
        client = get_redis_client()
        if hasattr(client, "smismember"):
            try:
                membership = client.smismember(REDIS_SET_KEY, normalized_ids)
            except redis.ResponseError as exc:
                if "unknown command" not in str(exc).lower():
                    raise
                membership = _pipeline_sismember(client, normalized_ids)
        else:
            membership = _pipeline_sismember(client, normalized_ids)
        return {
            listing_id
            for listing_id, already_scraped in zip(listing_ids, membership)
            if not already_scraped
        }
    except redis.RedisError:
        logger.warning("Redis bulk dedup check failed; scraping all ids", exc_info=True)
        return set(listing_ids)


def _pipeline_sismember(client: Any, listing_ids: list[str]) -> list[bool]:
    pipe = client.pipeline()
    for listing_id in listing_ids:
        pipe.sismember(REDIS_SET_KEY, listing_id)
    return pipe.execute()
