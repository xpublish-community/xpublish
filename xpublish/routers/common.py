"""
Dataset-independent API routes.

"""
import importlib
import sys

from fastapi import APIRouter, Depends

from ..dependencies import get_dataset_ids
from ..utils.info import get_sys_info, netcdf_and_hdf5_versions

common_router = APIRouter()


@common_router.get('/versions')
def get_versions():
    versions = dict(get_sys_info() + netcdf_and_hdf5_versions())
    modules = [
        'xarray',
        'zarr',
        'numcodecs',
        'fastapi',
        'starlette',
        'pandas',
        'numpy',
        'dask',
        'distributed',
        'uvicorn',
    ]
    for modname in modules:
        try:
            if modname in sys.modules:
                mod = sys.modules[modname]
            else:  # pragma: no cover
                mod = importlib.import_module(modname)
            versions[modname] = getattr(mod, '__version__', None)
        except ImportError:  # pragma: no cover
            pass
    return versions


dataset_collection_router = APIRouter()


@dataset_collection_router.get('/datasets')
def get_dataset_collection_keys(ids: list = Depends(get_dataset_ids)):
    return ids
