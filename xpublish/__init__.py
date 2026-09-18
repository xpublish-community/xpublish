"""Publish a Xarray Dataset through a rest API."""

import importlib.metadata

from .accessor import DataTreeRestAccessor, RestAccessor  # noqa: F401
from .plugins import Dependencies, Plugin, hookimpl, hookspec  # noqa: F401
from .rest import Rest, SingleDatasetRest  # noqa: F401
from .utils.cache import (  # noqa: F401
    CacheEntry,
    CacheProtocol,
    CacheyCache,
    LockedMapping,
    SerializedMapping,
    entry_size,
    lru_bytes_cache,
    lru_bytes_store,
)

try:
    __version__ = importlib.metadata.version(__package__)
except importlib.metadata.PackageNotFoundError:  # pragma: no cover
    __version__ = None
