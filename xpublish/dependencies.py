"""Helper functions to use a FastAPI dependencies."""

from collections.abc import MutableMapping
from typing import TYPE_CHECKING

import pluggy
import xarray as xr
from fastapi import Request

from .utils.cache import CacheProtocol, lru_bytes_cache, lru_bytes_store

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


def get_cache() -> CacheProtocol:
    """FastAPI dependency for accessing the application's cache.

    Use this callable as dependency in any FastAPI path operation
    function where you need access to the cache provided with the
    application. The returned object follows
    :class:`xpublish.CacheProtocol`.

    This dummy dependency will be overridden when creating the FastAPI
    application.

    """
    return lru_bytes_cache(available_bytes=1e6)  # pragma: no cover


def get_cache_store() -> MutableMapping:
    """FastAPI dependency for accessing the store behind the application's cache.

    Use this callable as dependency in any FastAPI path operation function
    where you want to layer your own caching policy over the store that the
    application cache is built on.

    This dummy dependency will be overridden when creating the FastAPI
    application.

    """
    return lru_bytes_store(1e6)  # pragma: no cover


def get_plugins() -> dict[str, 'Plugin']:
    """FastAPI dependency that returns the a dictionary of loaded plugins.

    Returns:
        Dictionary of names to initialized plugins.
    """
    return {}  # pragma: no cover


def get_plugin_manager() -> pluggy.PluginManager:
    """Return the active plugin manager."""
