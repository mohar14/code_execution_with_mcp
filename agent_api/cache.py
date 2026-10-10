import functools
import inspect
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def ttl_cache(ttl_seconds: int):
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        cache = {}
        cache_time = {}

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            key = (func.__name__, args, tuple(sorted(kwargs.items())))

            if key in cache and key in cache_time:
                elapsed = time.time() - cache_time[key]
                if elapsed < ttl_seconds:
                    return cache[key]

            result = await func(*args, **kwargs)
            cache[key] = result
            cache_time[key] = time.time()

            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            key = (func.__name__, args, tuple(sorted(kwargs.items())))

            if key in cache and key in cache_time:
                elapsed = time.time() - cache_time[key]
                if elapsed < ttl_seconds:
                    return cache[key]

            result = func(*args, **kwargs)
            cache[key] = result
            cache_time[key] = time.time()

            return result

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
