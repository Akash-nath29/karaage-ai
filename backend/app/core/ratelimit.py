"""Fixed-window rate limits in Redis (PRD §10.4). Fails open if Redis is down: auth must keep working."""

import logging

import redis

from app.config import settings
from app.core.exceptions import AppError

log = logging.getLogger(__name__)
_redis = redis.Redis.from_url(settings.redis_url, socket_timeout=1, socket_connect_timeout=1)


def limit(key: str, max_hits: int, window_seconds: int) -> None:
    """Raise 429 once `key` has been hit more than `max_hits` times in the current window."""
    if not settings.rate_limit_enabled:
        return
    name = f"rl:{key}"
    try:
        with _redis.pipeline() as pipe:
            hits, _ = pipe.incr(name).expire(name, window_seconds, nx=True).execute()
    except redis.RedisError:
        log.warning("rate limiter unavailable; allowing %s", key)
        return
    if hits > max_hits:
        raise AppError(429, "Too many attempts. Wait a few minutes and try again.")
