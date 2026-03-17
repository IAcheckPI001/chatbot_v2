import json
import logging
import os
import hashlib
import time
from threading import Lock
from typing import Optional

try:
    import redis
except ImportError:
    redis = None


logger = logging.getLogger(__name__)


class CacheBackend:
    def get(self, namespace: str, key):
        raise NotImplementedError

    def set(self, namespace: str, key, value, ttl_seconds: int, max_items: Optional[int] = None):
        raise NotImplementedError

    def delete(self, namespace: str, key):
        raise NotImplementedError

    @property
    def backend_name(self) -> str:
        raise NotImplementedError

    def health(self) -> dict:
        raise NotImplementedError


class LocalTTLCacheBackend(CacheBackend):
    def __init__(self, preferred_backend: str = "local", redis_url: Optional[str] = None):
        self._lock = Lock()
        self._store = {}
        self._preferred_backend = preferred_backend
        self._redis_url = redis_url

    def _ns(self, namespace: str):
        return self._store.setdefault(namespace, {})

    def get(self, namespace: str, key):
        now = time.time()
        with self._lock:
            cache = self._ns(namespace)
            item = cache.get(key)
            if not item:
                return None

            expire_at, value = item
            if expire_at < now:
                cache.pop(key, None)
                return None
            return value

    def set(self, namespace: str, key, value, ttl_seconds: int, max_items: Optional[int] = None):
        now = time.time()
        expire_at = now + ttl_seconds
        with self._lock:
            cache = self._ns(namespace)
            expired = [k for k, (exp, _) in cache.items() if exp < now]
            for expired_key in expired:
                cache.pop(expired_key, None)

            if max_items and len(cache) >= max_items:
                oldest_key = min(cache, key=lambda item_key: cache[item_key][0])
                cache.pop(oldest_key, None)

            cache[key] = (expire_at, value)

    def delete(self, namespace: str, key):
        with self._lock:
            self._ns(namespace).pop(key, None)

    @property
    def backend_name(self) -> str:
        return "local"

    def health(self) -> dict:
        return {
            "backend": self.backend_name,
            "configured_backend": self._preferred_backend,
            "redis_url": _mask_redis_url(self._redis_url),
            "connected": False,
        }


class RedisCacheBackend(CacheBackend):
    def __init__(self, client, key_prefix: str, preferred_backend: str, redis_url: str):
        self._client = client
        self._key_prefix = key_prefix.rstrip(":")
        self._preferred_backend = preferred_backend
        self._redis_url = redis_url


    def _build_key(self, namespace: str, key) -> str:
        normalized = json.dumps(key, sort_keys=True, ensure_ascii=False, default=str)
        digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()
        return f"{self._key_prefix}:{namespace}:{digest}"

    def get(self, namespace: str, key):
        try:
            payload = self._client.get(self._build_key(namespace, key))
            if payload is None:
                return None
            return json.loads(payload)
        except Exception as exc:
            logger.warning("Redis GET failed: %s", exc)
            return None

    def set(self, namespace: str, key, value, ttl_seconds: int, max_items: Optional[int] = None):
        try:
            del max_items
            payload = json.dumps(value, ensure_ascii=False, default=str)
            self._client.set(self._build_key(namespace, key), payload, ex=max(1, int(ttl_seconds)))
        except Exception as exc:
            logger.warning("Redis SET failed: %s", exc)
            
    def delete(self, namespace: str, key):
        try:
            self._client.delete(self._build_key(namespace, key))
        except Exception as exc:
            logger.warning("Redis DELETE failed: %s", exc)

    @property
    def backend_name(self) -> str:
        return "redis"

    def health(self) -> dict:
        connected = True
        error = None
        try:
            self._client.ping()
        except Exception as exc:
            connected = False
            error = str(exc)

        payload = {
            "backend": self.backend_name,
            "configured_backend": self._preferred_backend,
            "redis_url": _mask_redis_url(self._redis_url),
            "connected": connected,
        }
        if error:
            payload["error"] = error
        return payload


def _mask_redis_url(redis_url: Optional[str]) -> Optional[str]:
    if not redis_url:
        return redis_url

    if "@" not in redis_url:
        return redis_url

    scheme, remainder = redis_url.split("://", 1)
    credentials, host = remainder.split("@", 1)
    if ":" in credentials:
        username, _password = credentials.split(":", 1)
        return f"{scheme}://{username}:***@{host}"
    return f"{scheme}://***@{host}"


def create_cache_backend() -> CacheBackend:
    preferred_backend = (os.getenv("CACHE_BACKEND") or "auto").strip().lower()
    redis_url = (os.getenv("REDIS_URL") or "redis://localhost:6379/0").strip()
    key_prefix = (os.getenv("REDIS_KEY_PREFIX") or "chatbot_v1").strip()

    if preferred_backend == "local":
        logger.info("Cache backend set to local via CACHE_BACKEND=local")
        return LocalTTLCacheBackend(preferred_backend=preferred_backend, redis_url=redis_url)

    if redis is None:
        if preferred_backend == "redis":
            logger.warning("Redis client not installed; falling back to local cache")
        return LocalTTLCacheBackend(preferred_backend=preferred_backend, redis_url=redis_url)

    try:
        client = redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
            health_check_interval=30,
        )
        client.ping()
        logger.info("Using Redis cache backend at %s", redis_url)
        return RedisCacheBackend(client, key_prefix, preferred_backend=preferred_backend, redis_url=redis_url)
    except Exception as exc:
        if preferred_backend == "redis":
            logger.warning("Redis unavailable (%s); falling back to local cache", exc)
        elif preferred_backend == "auto":
            logger.info("Redis unavailable (%s); using local cache", exc)
        return LocalTTLCacheBackend(preferred_backend=preferred_backend, redis_url=redis_url)