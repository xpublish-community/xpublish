"""Helper functions to use a FastAPI dependencies."""

from collections.abc import Callable, MutableMapping
from typing import TYPE_CHECKING, Any

import pluggy
import xarray as xr
from fastapi import Request

from .utils.cache import LegacyCache, LockedMapping, build_cache, nbytes

if TYPE_CHECKING:
    from .plugins import Plugin  # pragma: no cover


def get_group_path(request: Request) -> str:
    """FastAPI dependency that reads the ``{group_path:path}`` route param.

    Returns an empty string when the route does not declare ``group_path``,
    so it can be used as a default ``Depends(...)`` on the built-in
    ``deps.dataset`` and ``deps.datatree`` dependencies without forcing
    every route to declare the segment.

    Leading and trailing slashes are stripped so the returned value is
    suitable for :py:meth:`xarray.DataTree.__getitem__`.
    """
    return (request.path_params.get('group_path') or '').strip('/')


def get_dataset_ids() -> list[str]:
    """FastAPI dependency for getting the list of ids (string keys) of the collection of datasets being served.

    Use this callable as dependency in any FastAPI path operation
    function where you need access to those ids.

    This dummy dependency will be overridden when creating the FastAPI
    application.

    Returns:
        A list of unique keys for datasets

    """
    return []  # pragma: no cover


def get_dataset(dataset_id: str) -> xr.Dataset:
    """FastAPI dependency for accessing the published xarray dataset object.

    Use this callable as dependency in any FastAPI path operation
    function where you need access to the xarray Dataset being served.

    When the route includes a ``{group_path:path}`` path parameter,
    the dataset at that node of the underlying DataTree is returned.
    Otherwise the dataset at the root node is returned.

    This dummy dependency will be overridden when creating the FastAPI
    application.

    Parameters:
        dataset_id:
            Unique path-safe key identifying dataset

    Returns:
        Requested Xarray dataset

    """
    return xr.Dataset()  # pragma: no cover


def get_datatree(dataset_id: str) -> xr.DataTree:
    """FastAPI dependency for accessing the published xarray DataTree object.

    Use this callable as dependency in any FastAPI path operation function
    where you need access to the xarray DataTree being served.

    When the route includes a ``{group_path:path}`` path parameter, the
    DataTree returned is rooted at that group. Otherwise the full tree
    associated with the dataset_id is returned.

    This dummy dependency will be overridden when creating the FastAPI
    application.

    Parameters:
        dataset_id:
            Unique path-safe key identifying dataset

    Returns:
        Requested Xarray DataTree

    """
    return xr.DataTree()  # pragma: no cover


def get_cache() -> LegacyCache:
    """Deprecated FastAPI dependency for accessing the application's cache.

    Use ``deps.get_lru_cache`` / ``deps.get_ttl_cache`` instead.

    Use this callable as dependency in any FastAPI path operation
    function where you need access to the cache provided with the
    application.

    This dummy dependency will be overridden when creating the FastAPI
    application.

    """
    return LegacyCache(build_cache('lru', 1e6, getsizeof=nbytes))  # pragma: no cover


def get_lru_cache(
    namespace: str,
    maxsize: int = 128,
    *,
    getsizeof: Callable[[Any], float] | None = None,
) -> MutableMapping:
    """Return an LRU cache for ``namespace``.

    This is a plain callable, not a FastAPI dependency: call it from a
    plugin's router hooks as ``deps.get_lru_cache(...)``. When running in
    :class:`xpublish.Rest` the real implementation memoizes one cache per
    namespace and may be backed by a provider plugin; this default returns a
    fresh, unshared cache.

    Args:
        namespace: Name of the cache. Plugins normally pass their own name;
            plugins passing the same name share the cache.
        maxsize: Maximum size of the cache, in items or in units of ``getsizeof``.
        getsizeof: Optional callable measuring the size of a value, such as
            :func:`xpublish.nbytes`. Providers may ignore it.

    Returns:
        A mutable mapping. Providers may serialize values, so cache picklable values.
    """
    return LockedMapping(build_cache('lru', maxsize, getsizeof=getsizeof))


def get_ttl_cache(
    namespace: str,
    maxsize: int = 128,
    ttl: float = 600,
    *,
    getsizeof: Callable[[Any], float] | None = None,
) -> MutableMapping:
    """Return a cache whose entries expire ``ttl`` seconds after being written.

    See :func:`get_lru_cache` for the contract.

    Args:
        namespace: Name of the cache.
        maxsize: Maximum size of the cache, in items or in units of ``getsizeof``.
        ttl: Seconds an entry lives.
        getsizeof: Optional callable measuring the size of a value.

    Returns:
        A mutable mapping.
    """
    return LockedMapping(build_cache('ttl', maxsize, ttl, getsizeof=getsizeof))


def get_plugins() -> dict[str, 'Plugin']:
    """FastAPI dependency that returns the a dictionary of loaded plugins.

    Returns:
        Dictionary of names to initialized plugins.
    """
    return {}  # pragma: no cover


def get_plugin_manager() -> pluggy.PluginManager:
    """Return the active plugin manager."""
