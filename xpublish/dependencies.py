"""
Helper functions to use a FastAPI dependencies.
"""
import cachey
import xarray as xr
from fastapi import Depends

from .utils.api import DATASET_ID_ATTR_KEY
from .utils.zarr import create_zmetadata, create_zvariables, zarr_metadata_key


def get_dataset_ids():
    """FastAPI dependency for getting the list of ids (string keys)
    of the collection of datasets being served.

    Use this callable as dependency in any FastAPI path operation
    function where you need access to those ids.

    This dummy dependency will be overridden when creating the FastAPI
    application.

    """
    return []  # pragma: no cover


def get_dataset(dataset_id: str):
    """FastAPI dependency for accessing the published xarray dataset object.

    Use this callable as dependency in any FastAPI path operation
    function where you need access to the xarray Dataset being served.

    This dummy dependency will be overridden when creating the FastAPI
    application.

    """
    return None  # pragma: no cover


def get_cache():
    """FastAPI dependency for accessing the application's cache.

    Use this callable as dependency in any FastAPI path operation
    function where you need access to the cache provided with the
    application.

    This dummy dependency will be overridden when creating the FastAPI
    application.

    """
    return None  # pragma: no cover


def get_zvariables(
    dataset: xr.Dataset = Depends(get_dataset), cache: cachey.Cache = Depends(get_cache)
):
    """FastAPI dependency that returns a dictionary of zarr encoded variables."""

    cache_key = dataset.attrs.get(DATASET_ID_ATTR_KEY, '') + '/' + 'zvariables'
    zvariables = cache.get(cache_key)

    if zvariables is None:
        zvariables = create_zvariables(dataset)

        # we want to permanently cache this: set high cost value
        cache.put(cache_key, zvariables, 99999)

    return zvariables


def get_zmetadata(
    dataset: xr.Dataset = Depends(get_dataset),
    cache: cachey.Cache = Depends(get_cache),
    zvariables: dict = Depends(get_zvariables),
):
    """FastAPI dependency that returns a consolidated zmetadata dictionary."""

    cache_key = dataset.attrs.get(DATASET_ID_ATTR_KEY, '') + '/' + zarr_metadata_key
    zmeta = cache.get(cache_key)

    if zmeta is None:
        zmeta = create_zmetadata(dataset)

        # we want to permanently cache this: set high cost value
        cache.put(cache_key, zmeta, 99999)

    return zmeta
