"""TTL (Time-To-Live) cache decorator for caching function results."""

import functools
import inspect
import time
from typing import Any, Callable, TypeVar

T = TypeVar("T")


def ttl_cache(ttl_seconds: int):
    """Decorator that caches function results with time-based expiration.

    Args:
        ttl_seconds: Time-to-live in seconds for cached values

    Returns:
        Decorator function
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        cache = {}
        cache_time = {}

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            # Create cache key from function name and arguments
            key = (func.__name__, args, tuple(sorted(kwargs.items())))

            # Check if cached value exists and is still valid
            if key in cache and key in cache_time:
                elapsed = time.time() - cache_time[key]
                if elapsed < ttl_seconds:
                    return cache[key]

            # Call function and cache result
            result = await func(*args, **kwargs)
            cache[key] = result
            cache_time[key] = time.time()

            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            # Create cache key from function name and arguments
            key = (func.__name__, args, tuple(sorted(kwargs.items())))

            # Check if cached value exists and is still valid
            if key in cache and key in cache_time:
                elapsed = time.time() - cache_time[key]
                if elapsed < ttl_seconds:
                    return cache[key]

            # Call function and cache result
            result = func(*args, **kwargs)
            cache[key] = result
            cache_time[key] = time.time()

            return result

        # Return appropriate wrapper based on whether function is async
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
