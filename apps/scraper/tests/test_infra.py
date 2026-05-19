"""Foundational tests for scraper infrastructure helpers."""
import asyncio

from apps.scraper import dedup, rate_limiter
from apps.scraper.rate_limiter import RedisTokenBucket, SAROUTY_RATE_LIMITER


class FakeRedis:
    def __init__(self):
        self.hashes = {}
        self.sets = {}
        self.expiry = {}

    def hgetall(self, key):
        return self.hashes.get(key, {})

    def hset(self, key, mapping):
        self.hashes[key] = dict(mapping)

    def sismember(self, key, value):
        return value in self.sets.get(key, set())

    def sadd(self, key, value):
        self.sets.setdefault(key, set()).add(value)

    def expire(self, key, seconds):
        self.expiry[key] = seconds


def test_sarouty_rate_limiter_singleton_configuration():
    assert SAROUTY_RATE_LIMITER.key == "sarouty:rate_limit"
    assert SAROUTY_RATE_LIMITER.rate == 1 / 3
    assert SAROUTY_RATE_LIMITER.capacity == 1


def test_token_bucket_consumes_available_token(monkeypatch):
    fake_redis = FakeRedis()
    bucket = RedisTokenBucket(key="test:rate_limit", rate=1 / 3, capacity=1)

    monkeypatch.setattr(rate_limiter, "get_redis_client", lambda: fake_redis)

    wait_time = bucket._try_acquire()

    assert wait_time == 0
    assert fake_redis.hashes["test:rate_limit"]["tokens"] == 0
    assert "last_refill" in fake_redis.hashes["test:rate_limit"]


def test_token_bucket_async_acquire_waits_until_available(monkeypatch):
    sleeps = []

    class TestBucket(RedisTokenBucket):
        def __init__(self):
            super().__init__(key="test:rate_limit", rate=1, capacity=1)
            self.wait_times = [0.01, 0]

        def _try_acquire(self):
            return self.wait_times.pop(0)

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    asyncio.run(TestBucket().acquire())

    assert sleeps == [0.01]


def test_dedup_marks_and_detects_scraped_listing(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(dedup, "get_redis_client", lambda: fake_redis)

    assert dedup.is_already_scraped(902701) is False

    dedup.mark_as_scraped(902701)

    assert dedup.is_already_scraped(902701) is True
    assert fake_redis.expiry[dedup.REDIS_SET_KEY] == dedup.EXPIRY_SECONDS
