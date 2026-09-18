import contextlib
import pickle
import sys
import threading
import time
from collections.abc import Callable, Iterator, MutableMapping
from typing import Any, NamedTuple, Protocol, runtime_checkable

import cachetools


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


def nbytes(value: Any) -> int:
    """Estimate the size of ``value`` in bytes.

    A port of cachey's helper of the same name, extended to recurse into
    plain containers. Array and dataframe libraries are duck-typed rather
    than imported, so this stays cheap for installs that don't use them.

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


# Alias so methods with an ``nbytes`` argument can still measure values
_nbytes = nbytes


class CacheEntry(NamedTuple):
    """A cost-aware cache entry, as written by :class:`CacheyCache`.

    Pairing a value with its pre-measured size lets a byte-budgeted store
    such as :func:`lru_bytes_store` account for it without re-measuring (or
    even understanding) the value. It also lets the store tell such
    pre-measured entries apart from raw values written directly by something
    else, for instance a ``cachetools`` decorator or a plain
    ``store[key] = value`` -- see :func:`entry_size`.

    ``CacheEntry`` is a plain tuple, so it pickles through
    :class:`SerializedMapping` like any other value, and it must stay
    importable at module level so it can be unpickled.
    """

    value: Any
    nbytes: int


def entry_size(item: Any) -> int:
    """Measure the size, in bytes, of a value stored in an xpublish cache store.

    Pass this as ``getsizeof=`` when building a ``cachetools`` cache meant to
    back an xpublish store. It returns the pre-measured size for a
    :class:`CacheEntry` (as written by :class:`CacheyCache`), and falls back
    to the module's :func:`nbytes` helper for anything else, so raw values
    written directly to the store -- by a ``cachetools`` decorator or by
    plain ``store[key] = value`` -- are sized correctly too.

    Args:
        item: The entry stored in the cache.

    Returns:
        The entry's size in bytes.
    """
    if isinstance(item, CacheEntry):
        return item.nbytes
    return nbytes(item)


class LockedMapping(MutableMapping):
    """A mutable mapping that serializes access with a lock.

    FastAPI runs sync endpoints in a thread pool, but ``cachetools`` caches
    (and many other mappings) are not thread-safe. Wrapping a store in a
    ``LockedMapping`` makes it safe to share across requests, and across
    anything else that writes to it directly rather than through
    :class:`CacheyCache`.

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
        deadlock (or self-deadlock, with a non-reentrant lock) by mutating
        the mapping from inside a ``for`` loop, so only the snapshot itself
        is protected.
        """
        with self._lock:
            return iter(list(self._mapping))

    def __getattr__(self, name: str) -> Any:
        """Forward attributes such as ``maxsize``, ``currsize`` and ``getsizeof``.

        These are read from the inner mapping without acquiring the lock.
        Names starting with ``_`` raise :class:`AttributeError` instead of
        forwarding, both because they are not meant to be forwarded and to
        avoid infinite recursion when ``_mapping`` itself is not yet set, for
        instance while unpickling.
        """
        if name.startswith('_'):
            raise AttributeError(name)
        return getattr(self._mapping, name)


def lru_bytes_store(available_bytes: float) -> LockedMapping:
    """Build a thread-safe, byte-budgeted LRU mapping.

    Args:
        available_bytes: Maximum total size of the stored values, in bytes.

    Returns:
        A :class:`LockedMapping` wrapping a ``cachetools.LRUCache`` sized with
        :func:`entry_size`, so it accounts for both the :class:`CacheEntry`
        instances :class:`CacheyCache` stores in it and raw values written
        directly, for instance by a ``cachetools`` decorator.
    """
    return LockedMapping(cachetools.LRUCache(maxsize=available_bytes, getsizeof=entry_size))


class CacheyCache:
    """A cachey-compatible :class:`CacheProtocol` façade over any mutable mapping.

    Values are stored in the mapping as :class:`CacheEntry` instances, pairing
    each value with its measured size. That lets a byte-budgeted store such as
    ``cachetools.LRUCache(maxsize=..., getsizeof=entry_size)`` enforce a size
    limit without having to re-measure (or even understand) the cached
    objects, keeps the measured size available for stores that serialize
    their contents, and lets the same store also hold raw values written
    directly by something else -- :func:`entry_size` tells the two apart.

    cachetools caches raise ``ValueError`` for an item that cannot ever fit,
    while cachey drops such values silently; :meth:`put` swallows that error so
    callers only ever observe a subsequent :meth:`get` returning the default.

    cachetools caches are also not thread safe, and FastAPI runs sync endpoints
    in a thread pool, so accesses are serialized through a lock by default.
    When ``mapping`` is a :class:`LockedMapping`, its own lock is reused (an
    ``RLock``, so re-entering it from here is fine) instead of creating a
    second one, so direct writers of the mapping and this cache stay
    consistent with each other.

    Args:
        mapping: The underlying store.
        lock: Context manager used to serialize access. ``None`` (the default)
            creates a :class:`threading.RLock`, or reuses ``mapping.lock`` when
            ``mapping`` is a :class:`LockedMapping`; ``False`` disables locking.
        min_cost: Values cheaper than this are not cached.
        max_nbytes: Values larger than this are not cached.
        hit: Called with the key on each cache hit.
        miss: Called with the key on each cache miss.
    """

    def __init__(
        self,
        mapping: MutableMapping,
        *,
        lock: Any = None,
        min_cost: float = 0.0,
        max_nbytes: int | None = None,
        hit: Callable[[str], Any] | None = None,
        miss: Callable[[str], Any] | None = None,
    ):
        self._mapping = mapping
        if lock is None:
            self._lock: Any = (
                mapping.lock if isinstance(mapping, LockedMapping) else threading.RLock()
            )
        elif lock is False:
            self._lock = contextlib.nullcontext()
        else:
            self._lock = lock
        self._min_cost = min_cost
        self._max_nbytes = max_nbytes
        self._hit = hit
        self._miss = miss

    @property
    def mapping(self) -> MutableMapping:
        """The underlying store, with its raw :class:`CacheEntry` entries."""
        return self._mapping

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value cached under ``key``, or ``default`` if absent.

        The store is accessed by subscript rather than ``.get()``: some mappings
        (for instance CacheToolsUtils' Redis wrappers) raise ``KeyError`` from
        ``.get()`` instead of honouring a default.

        If the stored object is a :class:`CacheEntry`, its ``value`` is
        returned; otherwise the stored object is returned as is, since it was
        a raw value written by something other than :meth:`put`.
        """
        with self._lock:
            try:
                entry = self._mapping[key]
            except KeyError:
                if self._miss is not None:
                    self._miss(key)
                return default

        if self._hit is not None:
            self._hit(key)
        return entry.value if isinstance(entry, CacheEntry) else entry

    def put(self, key: str, value: Any, cost: float, nbytes: int | None = None) -> None:
        """Offer ``value`` to the cache under ``key``.

        Values cheaper than ``min_cost`` or larger than ``max_nbytes`` are
        dropped, as are values the underlying store refuses as too large.

        Args:
            key: Key to store the value under.
            value: Value to cache.
            cost: How expensive the value was to compute.
            nbytes: Size of the value in bytes; measured when not given.
        """
        if cost < self._min_cost:
            return

        if nbytes is None:
            nbytes = _nbytes(value)

        if self._max_nbytes is not None and nbytes > self._max_nbytes:
            return

        with self._lock:
            try:
                self._mapping[key] = CacheEntry(value, nbytes)
            except ValueError:
                # cachetools raises for items that can never fit; cachey drops
                # them silently and consumers rely on that
                pass

    def retire(self, key: str) -> None:
        """Remove ``key`` from the cache, ignoring it if it isn't there."""
        with self._lock:
            with contextlib.suppress(KeyError):
                del self._mapping[key]

    def clear(self) -> None:
        """Remove everything from the cache."""
        with self._lock:
            self._mapping.clear()

    def __contains__(self, key: str) -> bool:
        with self._lock:
            return key in self._mapping

    def __len__(self) -> int:
        with self._lock:
            return len(self._mapping)


class SerializedMapping(MutableMapping):
    """A mapping that (de)serializes values on the way in and out.

    Wrap a raw byte store, such as a Redis client, so it can hold arbitrary
    Python objects.

    Args:
        mapping: The underlying byte store.
        dumps: Callable serializing a value to bytes.
        loads: Callable deserializing bytes back to a value.
    """

    def __init__(
        self,
        mapping: MutableMapping,
        dumps: Callable[[Any], bytes] = pickle.dumps,
        loads: Callable[[bytes], Any] = pickle.loads,
    ):
        self._mapping = mapping
        self._dumps = dumps
        self._loads = loads

    def __getitem__(self, key: Any) -> Any:
        return self._loads(self._mapping[key])

    def __setitem__(self, key: Any, value: Any) -> None:
        self._mapping[key] = self._dumps(value)

    def __delitem__(self, key: Any) -> None:
        del self._mapping[key]

    def __iter__(self) -> Iterator:
        return iter(self._mapping)

    def __len__(self) -> int:
        return len(self._mapping)


def lru_bytes_cache(available_bytes: float, **kws) -> CacheyCache:
    """Build a cachey-compatible LRU cache with a byte budget.

    Args:
        available_bytes: Maximum total size of the cached values, in bytes.
        **kws: Additional keyword arguments for :class:`CacheyCache`.

    Returns:
        A :class:`CacheyCache` backed by a thread-safe ``cachetools.LRUCache``
        (see :func:`lru_bytes_store`).
    """
    return CacheyCache(lru_bytes_store(available_bytes), **kws)
