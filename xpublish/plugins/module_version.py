"""
Version information router
"""
import importlib
import sys
from dataclasses import dataclass

from ..utils.info import get_sys_info, netcdf_and_hdf5_versions
from .factory import XpublishPluginFactory


@dataclass
class ModuleVersionPlugin(XpublishPluginFactory):
    """Module and system version information"""

    def register_routes(self):
        @self.app_router.get('/versions')
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
