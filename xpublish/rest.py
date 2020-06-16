import importlib
import json
import logging
import sys
from typing import Callable, Dict, Union

import uvicorn
import xarray as xr
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from starlette.responses import HTMLResponse, Response
from xarray.util.print_versions import get_sys_info, netcdf_and_hdf5_versions
from zarr.storage import array_meta_key, attrs_key, group_meta_key

from .utils import DatasetAccessor

zarr_format = 2
zarr_consolidated_format = 1
zarr_metadata_key = '.zmetadata'

logger = logging.getLogger('api')

DatasetOrCollection = Union[xr.Dataset, Dict[str, xr.Dataset]]


def _get_dataset_dependency(obj: DatasetOrCollection) -> Callable:
    """Returns a xarray Dataset getter to be used as fastAPI dependency."""

    def get_obj():
        return obj

    def get_from_mapping(dataset_id: str):
        if dataset_id not in obj:
            raise HTTPException(status_code=404, detail="Dataset not found")
        return obj[dataset_id]

    if isinstance(obj, DatasetAccessor):
        return get_obj
    else:
        return get_from_mapping


class APIRouterWrapper:
    """Wraps :class:`fastapi.APIRouter` so that it can be included
    in an application serving either a single xarray Dataset or a
    collection of Datasets.

    """

    def __init__(self, obj: DatasetOrCollection, cache_kws: Dict):

        self._router = None
        self._dataset = None

        self._init_ds(obj, cache_kws)

    def _init_ds(self, obj, cache_kws):
        if isinstance(obj, xr.Dataset):
            self._obj = DatasetAccessor(obj, cache_kws)
        else:
            self._obj = {k: DatasetAccessor(v, cache_kws) for k, v in obj.items()}

    @property
    def dataset(self) -> Callable:
        if self._dataset is None:
            self._dataset = _get_dataset_dependency(self._obj)
        return self._dataset

    def init_router(self):
        self._router = APIRouter()

    @property
    def router(self) -> APIRouter:
        if self._router is None:
            self.init_router()
        return self._router


class DatasetRouter(APIRouterWrapper):
    """ Class to create routes for dataset(s). """

    def init_router(self):
        super().init_router()

        @self._router.get("/dims")
        def get_dims(dsa: DatasetAccessor = Depends(self.dataset)):
            logger.info(dsa.dataset)
            return dsa.dataset.dims

        @self._router.get(f'/{zarr_metadata_key}')
        def get_zmetadata(dsa: DatasetAccessor = Depends(self.dataset)):
            return Response(
                json.dumps(dsa.zmetadata_json()).encode('ascii'), media_type='application/json'
            )

        @self._router.get(f'/{group_meta_key}')
        def get_zgroup(dsa: DatasetAccessor = Depends(self.dataset)):
            return dsa.zmetadata['metadata'][group_meta_key]

        @self._router.get(f'/{attrs_key}')
        def get_zattrs(dsa: DatasetAccessor = Depends(self.dataset)):
            return dsa.zmetadata['metadata'][attrs_key]

        @self._router.get('/keys')
        def list_keys(dsa: DatasetAccessor = Depends(self.dataset)):
            return list(dsa.dataset.variables)

        @self._router.get('/')
        def repr(dsa: DatasetAccessor = Depends(self.dataset)):
            with xr.set_options(display_style='html'):
                return HTMLResponse(dsa.dataset._repr_html_())

        @self._router.get('/info')
        def info(dsa: DatasetAccessor = Depends(self.dataset)):
            return dsa._info()

        @self._router.get('/dict')
        def to_dict(dsa: DatasetAccessor = Depends(self.dataset)):
            return dsa._obj.to_dict(data=False)

        @self._router.get('/{var}/{chunk}')
        def get_key(var: str, chunk: str, dsa: DatasetAccessor = Depends(self.dataset)):
            # First check that this request wasn't for variable metadata
            if array_meta_key in chunk:
                return dsa.zmetadata['metadata'][f'{var}/{array_meta_key}']
            elif attrs_key in chunk:
                return dsa.zmetadata['metadata'][f'{var}/{attrs_key}']
            elif group_meta_key in chunk:
                raise HTTPException(status_code=404, detail='No subgroups')
            else:
                return dsa._get_key(var, chunk)


@xr.register_dataset_accessor('rest')
class RestAccessor:
    """ REST API Accessor

    Parameters
    ----------
    xarray_obj : Dataset
        Dataset object to be served through the REST API.

    Notes
    -----
    When using this as an accessor on an Xarray.Dataset, options are set via
    the ``RestAccessor.__call__()`` method.
    """

    def __init__(self, xarray_obj):

        self._obj = xarray_obj

        self._app = None
        self._cache_kws = {'available_bytes': 1e6}
        self._app_kws = {}
        self._initialized = False

    def __call__(self, cache_kws=None, app_kws=None):
        """
        Initialize this RestAccessor by setting optional configuration values

        Parameters
        ----------
        cache_kws : dict
            Dictionary of keyword arguments to be passed to ``cachey.Cache()``
        app_kws : dict
            Dictionary of keyword arguments to be passed to
            ``fastapi.FastAPI()``

        Notes
        -----
        This method can only be invoked once.
        """
        if self._initialized:
            raise RuntimeError('This accessor has already been initialized')
        self._initialized = True

        # update kwargs
        if cache_kws is not None:
            self._cache_kws.update(cache_kws)
        if app_kws is not None:
            self._app_kws.update(app_kws)
        return self

    def _init_app(self):
        """ Initiate FastAPI Application.
        """

        self._app = FastAPI(**self._app_kws)

        @self._app.get('/versions')
        def versions():
            return self._versions()

        ds_router = DatasetRouter(self._obj, self._cache_kws)

        if isinstance(self._obj, xr.Dataset):
            prefix = ''
        else:

            @self._app.get('/datasets')
            def dataset_list():
                return [{'dataset_id': k, 'url_path': f'/datasets/{k}'} for k in self._obj.keys()]

            prefix = '/datasets/{dataset_id}'

        self._app.include_router(ds_router.router, prefix=prefix)

        return self._app

    def _versions(self):
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
                else:
                    mod = importlib.import_module(modname)
                versions[modname] = getattr(mod, '__version__', None)
            except ImportError:
                pass
        return versions

    @property
    def app(self):
        """ FastAPI app """
        if self._app is None:
            self._app = self._init_app()
        return self._app

    def serve(self, host='0.0.0.0', port=9000, log_level='debug', **kwargs):
        """ Serve this app via ``uvicorn.run``.

        Parameters
        ----------
        host : str
            Bind socket to this host.
        port : int
            Bind socket to this port.
        log_level : str
            App logging level, valid options are
            {'critical', 'error', 'warning', 'info', 'debug', 'trace'}.
        kwargs :
            Additional arguments to be passed to ``uvicorn.run``.

        Notes
        -----
        This method is blocking and does not return.
        """
        uvicorn.run(self.app, host=host, port=port, log_level=log_level, **kwargs)
