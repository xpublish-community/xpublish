import cachey
import uvicorn
import xarray as xr
from fastapi import FastAPI, HTTPException

from .dependencies import get_cache, get_dataset, get_dataset_ids
from .routers import base_router, common_router, dataset_collection_router, zarr_router
from .utils.api import check_route_conflicts, normalize_app_routers, normalize_datasets


def _dataset_from_collection_getter(datasets):
    """Used to override the get_dataset FastAPI dependency in case where
    a collection of datasets is being served.

    """

    def get_dataset(dataset_id: str):
        if dataset_id not in datasets:
            raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found")

        return datasets[dataset_id]

    return get_dataset


def _dataset_unique_getter(dataset):
    """Used to override the get_dataset FastAPI dependency in case where
    only one dataset is being served, e.g., via the 'rest' accessor.

    """

    def get_dataset():
        return dataset

    return get_dataset


def _set_app_routers(dataset_routers, unique=False):

    app_routers = []

    # top-level api endpoints
    app_routers.append((common_router, {}))

    if not unique:
        app_routers.append((dataset_collection_router, {'tags': ['info']}))

    # dataset-specifc api endpoints
    if dataset_routers is None:
        dataset_routers = [
            (base_router, {'tags': ['info']}),
            (zarr_router, {'tags': ['zarr']}),
        ]

    if unique:
        dataset_route_prefix = ''
    else:
        dataset_route_prefix = '/datasets/{dataset_id}'

    app_routers += normalize_app_routers(dataset_routers, dataset_route_prefix)

    check_route_conflicts(app_routers)

    return app_routers


class Rest:
    """Used to publish a collection of xarray Datasets via a REST API (FastAPI application).

    Parameters
    ----------
    datasets : dict
        A collection of datasets to be served. Keys are dataset ids (will be converted to
        strings) and values must be :class:`xarray.Dataset` objects.
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
    unique : bool, optional
        If True, the FastAPI application is configured to serve only one dataset,
        i.e., dataset ids are ignored and are not present as parameters in the
        API urls (default: False).
        For more convienence, use the :attr:`xarray.Dataset.rest` accessor instead
        to publish one dataset.

    """

    def __init__(self, datasets, routers=None, cache_kws=None, app_kws=None, unique=False):

        self._datasets = normalize_datasets(datasets)

        if unique:
            if len(datasets) != 1:
                raise ValueError(
                    'the given collection of datasets must cointain one item when `unique` '
                    f'is set to True, found {len(datasets)} item(s)'
                )
            self._get_dataset_func = _dataset_unique_getter(self._datasets[''])
        else:
            self._get_dataset_func = _dataset_from_collection_getter(self._datasets)

        self._app = None
        self._app_kws = {}
        if app_kws is not None:
            self._app_kws.update(app_kws)

        self._app_routers = _set_app_routers(routers, unique=unique)

        self._cache = None
        self._cache_kws = {'available_bytes': 1e6}
        if cache_kws is not None:
            self._cache_kws.update(cache_kws)

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

        self._app.dependency_overrides[get_dataset_ids] = lambda: list(self._datasets)
        self._app.dependency_overrides[get_dataset] = self._get_dataset_func
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
        **kwargs :
            Additional arguments to be passed to :func:`uvicorn.run`.

        Notes
        -----
        This method is blocking and does not return.

        """
        uvicorn.run(self.app, host=host, port=port, log_level=log_level, **kwargs)


@xr.register_dataset_accessor('rest')
class RestAccessor:
    """REST API Accessor for serving one dataset in its
    dedicated FastAPI application.

    """

    def __init__(self, xarray_obj):

        self._obj = xarray_obj
        self._datasets = {'': xarray_obj}
        self._rest = None

        self._initialized = False

    def _get_rest_obj(self):
        if self._rest is None:
            self._rest = Rest(self._datasets, unique=True)

        return self._rest

    def __call__(self, **kwargs):
        """Initialize this accessor by setting optional configuration values.

        Parameters
        ----------
        **kwargs
            Arguments passed to :func:`xpublish.Rest.__init__`.

        Notes
        -----
        This method can only be invoked once.

        """
        if self._initialized:
            raise RuntimeError('This accessor has already been initialized')
        self._initialized = True

        # force serving one unique dataset
        kwargs['unique'] = True

        self._rest = Rest(self._datasets, **kwargs)

        return self

    @property
    def cache(self) -> cachey.Cache:
        """Returns the :class:`cachey.Cache` instance used by the FastAPI application."""

        return self._get_rest_obj().cache

    @property
    def app(self) -> FastAPI:
        """Returns the :class:`fastapi.FastAPI` application instance."""

        return self._get_rest_obj().app

    def serve(self, **kwargs):
        """Serve this FastAPI application via :func:`uvicorn.run`.

        Parameters
        ----------
        **kwargs :
            Arguments passed to :func:`xpublish.Rest.serve`.

        Notes
        -----
        This method is blocking and does not return.

        """
        self._get_rest_obj().serve(**kwargs)
