import sys
import threading
import time
from collections.abc import Callable, Iterator, MutableMapping
from typing import Any, Literal

import cachetools


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


def nbytes(value: Any) -> int:
    """Estimate the size of ``value`` in bytes.

    A port of cachey's helper of the same name, extended to recurse into
    plain containers. Array and dataframe libraries are duck-typed rather
    than imported, so this stays cheap for installs that don't use them.
    Suitable as ``getsizeof=`` for a byte-budgeted cache.

    Args:
        value: Object to size.

    Returns:
        Estimated size of ``value`` in bytes.
    """
    if isinstance(value, (bytes, bytearray, memoryview)):
        return len(value)

    if isinstance(value, str):
        return len(value.encode())

    # pandas objects under-report ``nbytes`` for object dtypes
    memory_usage = getattr(value, 'memory_usage', None)
    if callable(memory_usage):
        try:
            usage = memory_usage(deep=True)
        except TypeError:  # pragma: no cover - non-pandas lookalikes
            usage = memory_usage()
        total = getattr(usage, 'sum', None)
        return int(total()) if callable(total) else int(usage)

    value_nbytes = getattr(value, 'nbytes', None)
    if isinstance(value_nbytes, int):
        return value_nbytes

    if isinstance(value, dict):
        return sys.getsizeof(value) + sum(nbytes(key) + nbytes(item) for key, item in value.items())

    if isinstance(value, (list, tuple, set, frozenset)):
        return sys.getsizeof(value) + sum(nbytes(item) for item in value)

    return sys.getsizeof(value)


class LockedMapping(MutableMapping):
    """A mutable mapping that serializes access with a lock.

    FastAPI runs sync endpoints in a thread pool, but ``cachetools`` caches
    (and many other mappings) are not thread-safe. Wrapping a store in a
    ``LockedMapping`` makes it safe to share across requests.

    Args:
        mapping: The underlying store.
        lock: Context manager used to serialize access. ``None`` (the
            default) creates a :class:`threading.RLock`.
    """

    def __init__(self, mapping: MutableMapping, lock: Any = None):
        self._mapping = mapping
        self._lock: Any = threading.RLock() if lock is None else lock

    @property
    def lock(self) -> Any:
        """The lock serializing access to the mapping."""
        return self._lock

    @property
    def mapping(self) -> MutableMapping:
        """The underlying store."""
        return self._mapping

    def __getitem__(self, key: Any) -> Any:
        with self._lock:
            return self._mapping[key]

    def __setitem__(self, key: Any, value: Any) -> None:
        with self._lock:
            self._mapping[key] = value

    def __delitem__(self, key: Any) -> None:
        with self._lock:
            del self._mapping[key]

    def __len__(self) -> int:
        with self._lock:
            return len(self._mapping)

    def __contains__(self, key: Any) -> bool:
        with self._lock:
            return key in self._mapping

    def __iter__(self) -> Iterator:
        """Iterate over a snapshot of the keys, taken under the lock.

        Holding the lock for the whole iteration would make it easy to
        deadlock by mutating the mapping from inside a ``for`` loop, so only
        the snapshot itself is protected.
        """
        with self._lock:
            return iter(list(self._mapping))

    def __getattr__(self, name: str) -> Any:
        """Forward attributes such as ``maxsize``, ``currsize`` and ``getsizeof``.

        These are read from the inner mapping without acquiring the lock.
        Names starting with ``_`` raise :class:`AttributeError` instead of
        forwarding, to avoid infinite recursion when ``_mapping`` itself is
        not yet set, for instance while unpickling.
        """
        if name.startswith('_'):
            raise AttributeError(name)
        return getattr(self._mapping, name)


def _now() -> float:
    """Clock for TTL caches; looked up at call time so tests can patch ``time.monotonic``."""
    return time.monotonic()


def build_cache(
    kind: Literal['lru', 'ttl'],
    maxsize: float = 128,
    ttl: float = 600,
    getsizeof: Callable[[Any], float] | None = None,
) -> cachetools.Cache:
    """Build an unlocked cachetools LRU or TTL cache.

    Args:
        kind: ``'lru'`` or ``'ttl'``.
        maxsize: Maximum total size of the cache (items, or the units of ``getsizeof``).
        ttl: Time to live in seconds; only used by ``'ttl'`` caches.
        getsizeof: Optional callable measuring the size of a value.

    Returns:
        A :class:`cachetools.LRUCache` or :class:`cachetools.TTLCache`.
    """
    if kind == 'lru':
        return cachetools.LRUCache(maxsize=maxsize, getsizeof=getsizeof)
    if kind == 'ttl':
        return cachetools.TTLCache(maxsize=maxsize, ttl=ttl, timer=_now, getsizeof=getsizeof)
    raise ValueError(f'Unknown cache kind {kind!r}')  # pragma: no cover
