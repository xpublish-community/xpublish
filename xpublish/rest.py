import cachey
import uvicorn
import xarray as xr
from fastapi import FastAPI

from .dependencies import get_cache, get_dataset
from .routers import base_router, common_router, zarr_router
from .utils.api import check_route_conflicts, normalize_app_routers


@xr.register_dataset_accessor('rest')
class RestAccessor:
    """REST API Accessor

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
        self._app_kws = {}
        self._app_routers = [
            (common_router, {}),
            (base_router, {'tags': ['info']}),
            (zarr_router, {'tags': ['zarr']}),
        ]

        self._cache = None
        self._cache_kws = {'available_bytes': 1e6}

        self._initialized = False

    def __call__(self, routers=None, cache_kws=None, app_kws=None):
        """Initialize this accessor by setting optional configuration values.

        Parameters
        ----------
        routers : list, optional
            A list of :class:`fastapi.APIRouter` instances to include in the
            fastAPI application. If None, the default routers will be included.
            The items of the list may also be tuples with the following format:
            ``[(router1, {'prefix': '/foo', 'tags': ['foo', 'bar']})]``.
            The 1st tuple element is a :class:`fastapi.APIRouter` instance and the
            2nd element is a dictionary that is used to pass keyword arguments to
            :meth:`fastapi.FastAPI.include_router`.
        cache_kws : dict, optional
            Dictionary of keyword arguments to be passed to
            :meth:`cachey.Cache.__init__()`.
        app_kws : dict, optional
            Dictionary of keyword arguments to be passed to
            :meth:`fastapi.FastAPI.__init__()`.

        Notes
        -----
        This method can only be invoked once.

        """
        if self._initialized:
            raise RuntimeError('This accessor has already been initialized')
        self._initialized = True

        if routers is not None:
            self._app_routers = normalize_app_routers(routers)
            check_route_conflicts(self._app_routers)
        if app_kws is not None:
            self._app_kws.update(app_kws)
        if cache_kws is not None:
            self._cache_kws.update(cache_kws)

        return self

    @property
    def cache(self) -> cachey.Cache:
        """Returns the :class:`cachey.Cache` instance used by the FastAPI application."""

        if self._cache is None:
            self._cache = cachey.Cache(**self._cache_kws)
        return self._cache

    def _init_app(self):
        """Initiate the FastAPI application."""

        self._app = FastAPI(**self._app_kws)

        for rt, kwargs in self._app_routers:
            self._app.include_router(rt, **kwargs)

        self._app.dependency_overrides[get_dataset] = lambda: self._obj
        self._app.dependency_overrides[get_cache] = lambda: self.cache

        return self._app

    @property
    def app(self) -> FastAPI:
        """Returns the :class:`fastapi.FastAPI` application instance."""
        if self._app is None:
            self._app = self._init_app()
        return self._app

    def serve(self, host='0.0.0.0', port=9000, log_level='debug', **kwargs):
        """Serve this FastAPI application via :func:`uvicorn.run`.

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
            Additional arguments to be passed to :func:`uvicorn.run`.

        Notes
        -----
        This method is blocking and does not return.

        """
        uvicorn.run(self.app, host=host, port=port, log_level=log_level, **kwargs)
