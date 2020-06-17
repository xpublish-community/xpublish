import uvicorn
import xarray as xr
from fastapi import FastAPI

from .cache import RestCacheAccessor  # noqa: F401
from .routers import base_router, common_router, get_dataset, zarr_router


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
        self._app_routers = [common_router, base_router, zarr_router]
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

        # update app kwargs
        if app_kws is not None:
            self._app_kws.update(app_kws)

        # update cache kwargs
        self._obj._rest_cache(cache_kws=cache_kws)

        return self

    @property
    def cache(self):
        """ Cache Property """
        return self._obj._rest_cache.cache

    def _init_app(self):
        """ Initiate FastAPI Application.
        """

        self._app = FastAPI(**self._app_kws)

        for r in self._app_routers:
            self._app.include_router(r, prefix='')

        self._app.dependency_overrides[get_dataset] = lambda: self._obj

        return self._app

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
