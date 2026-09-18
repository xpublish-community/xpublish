import time
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CacheProtocol(Protocol):
    """The cache contract that xpublish plugins rely on.

    Any object providing these two methods can be used as the application
    cache. The signatures match :class:`cachey.Cache`, which was the
    historical implementation, so cachey caches (and anything else that is
    cachey-compatible) satisfy the protocol.

    Implementations are free to ignore ``cost`` and ``nbytes`` hints, and may
    silently decline to store a value, so callers must always be prepared for
    :meth:`get` to return the default after a :meth:`put`.
    """

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value cached under ``key``, or ``default`` if absent."""
        ...  # pragma: no cover

    def put(self, key: str, value: Any, cost: float, nbytes: int | None = None) -> None:
        """Offer ``value`` to the cache under ``key``.

        Args:
            key: Key to store the value under.
            value: Value to cache.
            cost: How expensive the value was to compute; caches may use it to
                decide whether the value is worth keeping.
            nbytes: Size of the value in bytes, if it is already known.
        """
        ...  # pragma: no cover


class CostTimer:
    """Context manager to measure wall time."""

    def __enter__(self):
        """Start the timer."""
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args):
        """Stop the timer and return elapsed time."""
        end = time.perf_counter()
        self.time = end - self._start
