"""Helper functions to use a FastAPI dependencies."""

from typing import TYPE_CHECKING, Dict, List

import cachey
import pluggy
import xarray as xr

if TYPE_CHECKING:
    from .plugins import Plugin  # pragma: no cover


def get_dataset_ids() -> List[str]:
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

    This dummy dependency will be overridden when creating the FastAPI
    application.

    Parameters:
        dataset_id:
            Unique path-safe key identifying dataset

    Returns:
        Requested Xarray dataset

    """
    return xr.Dataset()  # pragma: no cover


def get_cache() -> cachey.Cache:
    """FastAPI dependency for accessing the application's cache.

    Use this callable as dependency in any FastAPI path operation
    function where you need access to the cache provided with the
    application.

    This dummy dependency will be overridden when creating the FastAPI
    application.

    """
    return cachey.Cache(available_bytes=1e6)  # pragma: no cover


def get_plugins() -> Dict[str, 'Plugin']:
    """FastAPI dependency that returns the a dictionary of loaded plugins.

    Returns:
        Dictionary of names to initialized plugins.
    """
    return {}  # pragma: no cover


def get_plugin_manager() -> pluggy.PluginManager:
    """Return the active plugin manager."""
