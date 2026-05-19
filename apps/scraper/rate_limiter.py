"""Redis-backed rate limiting helpers for scraper requests."""
import asyncio
import time
from typing import Any

import redis
from django.conf import settings


def get_redis_client() -> Any:
    """Return a redis-py client for the configured Redis URL."""
    return redis.from_url(settings.REDIS_URL)


class RedisTokenBucket:
    """Async token bucket stored in Redis."""

    def __init__(self, key: str, rate: float, capacity: int):
        self.key = key
        self.rate = rate
        self.capacity = capacity

    async def acquire(self) -> None:
        """Wait until a token is available, then consume it."""
        while True:
            wait_time = await asyncio.get_event_loop().run_in_executor(
                None, self._try_acquire
            )
            if wait_time <= 0:
                return
            await asyncio.sleep(wait_time)

    def _try_acquire(self) -> float:
        client = get_redis_client()
        now = time.time()
        bucket = client.hgetall(self.key)

        tokens = self.capacity
        last_refill = now
        if bucket:
            tokens = float(self._hash_value(bucket, "tokens", self.capacity))
            last_refill = float(self._hash_value(bucket, "last_refill", now))

        elapsed = max(0, now - last_refill)
        tokens = min(self.capacity, tokens + elapsed * self.rate)

        if tokens >= 1:
            client.hset(
                self.key,
                mapping={"tokens": tokens - 1, "last_refill": now},
            )
            return 0

        client.hset(self.key, mapping={"tokens": tokens, "last_refill": now})
        return (1 - tokens) / self.rate

    @staticmethod
    def _hash_value(bucket: dict, name: str, default: float) -> float:
        return bucket.get(name) or bucket.get(name.encode()) or default


SAROUTY_RATE_LIMITER = RedisTokenBucket(
    key="sarouty:rate_limit",
    rate=1 / 3,
    capacity=1,
)
