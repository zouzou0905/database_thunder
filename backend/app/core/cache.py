"""Lightweight in-memory response cache for sync FastAPI endpoints.

No external dependencies — a simple dict with TTL-based expiry.
Suitable for single-process deployments with <100 concurrent users.
"""

from __future__ import annotations

import functools
import hashlib
import json
import threading
import time
from collections.abc import Callable
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

_cache: dict[str, tuple[float, Any]] = {}
_lock = threading.Lock()

# Namespaces that can be bulk-invalidated.
_namespaces: dict[str, set[str]] = {}


def _key(marker: str, args: tuple, kwargs: dict, exclude: frozenset[str] | None = None) -> str:
    """Build a stable cache key from a marker string and call arguments.

    *exclude* names keyword arguments (e.g. ``conn``) that vary per request
    and should not be part of the cache key.
    """
    filtered_kwargs = {k: v for k, v in kwargs.items() if exclude is None or k not in exclude}
    raw = json.dumps({"m": marker, "a": args, "k": filtered_kwargs}, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def cached(
    ttl_seconds: int = 300,
    namespace: str | None = None,
    exclude: tuple[str, ...] = (),
) -> Callable[[F], F]:
    """Decorator: cache the return value of a sync function for *ttl_seconds*.

    *exclude* argument names that should not be part of the cache key
    (e.g. the database connection ``conn``).

    Usage::

        @cached(ttl_seconds=300, namespace="meta", exclude=("conn",))
        def get_months(conn, ...):
            return data
    """

    _exclude = frozenset(exclude)

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            cache_key = _key(func.__qualname__, args, kwargs, exclude=_exclude)
            now = time.monotonic()

            with _lock:
                entry = _cache.get(cache_key)
                if entry is not None:
                    expires_at, value = entry
                    if now < expires_at:
                        return value

            # Cache miss — call the real function.
            result = func(*args, **kwargs)

            with _lock:
                _cache[cache_key] = (now + ttl_seconds, result)
                if namespace is not None:
                    _namespaces.setdefault(namespace, set()).add(cache_key)

            return result

        return wrapper  # type: ignore[return-value]

    return decorator


def invalidate(namespace: str) -> int:
    """Remove all cached entries in *namespace*.  Returns count of evicted keys."""
    with _lock:
        keys = _namespaces.pop(namespace, set())
        for k in keys:
            _cache.pop(k, None)
        return len(keys)


def clear() -> int:
    """Remove ALL cached entries.  Returns count of evicted keys."""
    with _lock:
        count = len(_cache)
        _cache.clear()
        _namespaces.clear()
        return count
