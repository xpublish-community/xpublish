from typing import Dict, Optional

import cachey
import pluggy
import uvicorn
import xarray as xr
from fastapi import APIRouter, FastAPI, HTTPException

from .dependencies import get_cache, get_dataset, get_dataset_ids, get_plugin_manager
from .plugins import Plugin, PluginSpec, get_plugins, load_default_plugins
from .routers import dataset_collection_router
from .utils.api import (
    SingleDatasetOpenAPIOverrider,
    check_route_conflicts,
    normalize_app_routers,
    normalize_datasets,
)


class Rest:
    """Used to publish multiple Xarray Datasets via a REST API (FastAPI application).

    To publish a single dataset via its own FastAPI application, you might
    want to use the :attr:`xarray.Dataset.rest` accessor for more convenience.
    Additionally the :class:`xpublish.SingleDatasetRest` class allows has
    a simplified interface for single dataset access.

    Parameters
    ----------
    datasets : dict
        A mapping of datasets objects to be served. If a mapping is given, keys
        are used as dataset ids and are converted to strings. See also the notes below.
    routers : list, optional
        A list of dataset-specific :class:`fastapi.APIRouter` instances to
        include in the fastAPI application. These routers are in addition
        to any loaded via plugins.
        The items of the list may also be tuples with the following format:
        ``[(router1, {'prefix': '/foo', 'tags': ['foo', 'bar']})]``, where
        the 1st tuple element is a :class:`fastapi.APIRouter` instance and the
        2nd element is a dictionary that is used to pass keyword arguments to
        :meth:`fastapi.FastAPI.include_router`.
    cache_kws : dict, optional
        Dictionary of keyword arguments to be passed to
        :meth:`cachey.Cache.__init__()`.
        By default, the cache size is set to 1MB, but this can be changed with
        ``available_bytes``.
    app_kws : dict, optional
        Dictionary of keyword arguments to be passed to
        :meth:`fastapi.FastAPI.__init__()`.
    plugins : dict, optional
        Optional dictionary of loaded, configured plugins.
        Overrides automatic loading of plugins.
        If no plugins are desired, set to an empty dict.

    Notes
    -----
    The urls of the application's API endpoints differ whether a single dataset
    or a mapping (collection) of datasets is given. In the latter case, all
    dataset-specific endpoint urls have the prefix ``/datasets/{dataset_id}``,
    where ``{dataset_id}`` corresponds to the keys of the mapping (converted to
    strings). Still in the latter case, the endpoint ``/datasets`` is added and returns
    the list of all dataset ids.

    """

    def __init__(
        self,
        datasets: Optional[Dict[str, xr.Dataset]] = None,
        routers: Optional[APIRouter] = None,
        cache_kws=None,
        app_kws=None,
        plugins: Optional[Dict[str, Plugin]] = None,
    ):
        self.setup_datasets(datasets or {})
        self.setup_plugins(plugins)

        routers = normalize_app_routers(routers or [], self._dataset_route_prefix)
        check_route_conflicts(routers)
        self._routers = routers

        self.init_app_kwargs(app_kws)
        self.init_cache_kwargs(cache_kws)

    def setup_datasets(self, datasets: Dict[str, xr.Dataset]):
        """Initialize datasets and getter functions"""
        self._datasets = normalize_datasets(datasets)

        self._get_dataset_func = self.get_dataset_from_plugins
        self._dataset_route_prefix = '/datasets/{dataset_id}'
        return self._dataset_route_prefix

    def get_datasets_from_plugins(self):
        """Get dataset ids from directly loaded datasets and plugins"""
        dataset_ids = list(self._datasets)

        for plugin_dataset_ids in self.pm.hook.get_datasets():
            dataset_ids.extend(plugin_dataset_ids)

        return dataset_ids

    def get_dataset_from_plugins(self, dataset_id: str):
        """Attempt to load dataset from plugins, otherwise load"""
        dataset = self.pm.hook.get_dataset(dataset_id=dataset_id)

        if dataset:
            return dataset

        if dataset_id not in self._datasets:
            raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found")

        return self._datasets[dataset_id]

    def setup_plugins(self, plugins: Optional[Dict[str, Plugin]] = None):
        """Initialize and load plugins from entry_points"""
        if plugins is None:
            plugins = load_default_plugins()

        self.pm = pluggy.PluginManager('xpublish')
        self.pm.add_hookspecs(PluginSpec)

        for name, plugin in plugins.items():
            self.pm.register(plugin, name=name)

        for hookspec in self.pm.hook.register_hookspec():
            self.pm.add_hookspecs(hookspec)

    def register_plugin(self, plugin: Plugin, plugin_name: Optional[str] = None):
        """Register a plugin"""
        existing_plugins = self.pm.get_plugins()
        self.pm.register(plugin, plugin_name or plugin.name)

        for hookspec in self.pm.subset_hook_caller(
            'register_hookspec', remove_plugins=existing_plugins
        )():
            self.pm.add_hookspecs(hookspec)

    def init_cache_kwargs(self, cache_kws):
        """Set up cache kwargs"""
        self._cache = None
        self._cache_kws = {'available_bytes': 1e6}
        if cache_kws is not None:
            self._cache_kws.update(cache_kws)

    def init_app_kwargs(self, app_kws):
        """Set up FastAPI application kwargs"""
        self._app = None
        self._app_kws = {}
        if app_kws is not None:
            self._app_kws.update(app_kws)

    @property
    def cache(self) -> cachey.Cache:
        """Returns the :class:`cachey.Cache` instance used by the FastAPI application."""

        if self._cache is None:
            self._cache = cachey.Cache(**self._cache_kws)
        return self._cache

    @property
    def plugins(self) -> Dict[str, Plugin]:
        """Returns the loaded plugins"""
        return dict(self.pm.list_name_plugin())

    def _init_routers(self, dataset_routers: Optional[APIRouter]):
        """Setup plugin and dataset routers. Needs to run after dataset and plugin setup"""
        app_routers, plugin_dataset_routers = self.plugin_routers()

        if self._dataset_route_prefix:
            app_routers.append((dataset_collection_router, {'tags': ['info']}))

        app_routers.extend(
            normalize_app_routers(
                plugin_dataset_routers + (dataset_routers or []), self._dataset_route_prefix
            )
        )

        check_route_conflicts(app_routers)

        self._app_routers = app_routers

    def plugin_routers(self):
        """Load the app and dataset routers for plugins"""
        app_routers = []
        dataset_routers = []

        for router in self.pm.hook.app_router():
            app_routers.append((router, {'prefix': router.prefix, 'tags': router.tags}))

        for router in self.pm.hook.dataset_router():
            dataset_routers.append((router, {'prefix': router.prefix, 'tags': router.tags}))

        return app_routers, dataset_routers

    def _init_dependencies(self):
        """Initialize dependencies"""
        self._app.dependency_overrides[get_dataset_ids] = self.get_datasets_from_plugins
        self._app.dependency_overrides[get_dataset] = self._get_dataset_func
        self._app.dependency_overrides[get_cache] = lambda: self.cache
        self._app.dependency_overrides[get_plugins] = lambda: self.plugins
        self._app.dependency_overrides[get_plugin_manager] = lambda: self.pm

    def _init_app(self):
        """Initiate the FastAPI application."""

        self._app = FastAPI(**self._app_kws)

        self._init_routers(self._routers)
        for rt, kwargs in self._app_routers:
            self._app.include_router(rt, **kwargs)

        self._init_dependencies()

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


class SingleDatasetRest(Rest):
    """Used to publish a single Xarray dataset via a REST API (FastAPI application).
    Use xpublish.Rest to publish multiple datasets.

    Parameters:
    -----------
    dataset : :class:`xarray.Dataset`
        A single :class:`xarray.Dataset` object to be served.
    """

    def __init__(
        self,
        dataset: xr.Dataset,
        routers=None,
        cache_kws=None,
        app_kws=None,
        plugins: Optional[Dict[str, Plugin]] = None,
    ):
        self._dataset = dataset

        super().__init__({}, routers, cache_kws, app_kws, plugins)

    def setup_datasets(self, datasets):
        self._dataset_route_prefix = ''
        self._datasets = {}

        self._get_dataset_func = lambda: self._dataset

        return self._dataset_route_prefix

    def _init_app(self):
        self._app = super()._init_app()

        self._app.openapi = SingleDatasetOpenAPIOverrider(self._app).openapi

        return self._app
