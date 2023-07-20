"""
Version information router
"""
import importlib
import sys
from typing import Sequence

from fastapi import APIRouter

from ...utils.info import get_sys_info, netcdf_and_hdf5_versions
from .. import Plugin, hookimpl


class ModuleVersionPlugin(Plugin):
    """Share the currently loaded versions of key libraries"""

    name: str = 'module_version'

    app_router_prefix: str = ''
    app_router_tags: Sequence[str] = ['module_version']

    @hookimpl
    def app_router(self) -> APIRouter:
        router = APIRouter(
            prefix=self.app_router_prefix,
            tags=self.app_router_tags,
        )

        @router.get('/versions')
        def get_versions() -> dict:
            """Currently loaded versions of key libraries"""
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

        return router
