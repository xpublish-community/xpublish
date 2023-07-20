from typing import Dict, List, Optional, Tuple

import cachey
import pluggy
import uvicorn
import xarray as xr
from fastapi import APIRouter, FastAPI, HTTPException, Path

from .dependencies import get_cache, get_dataset, get_dataset_ids, get_plugin_manager
from .plugins import Dependencies, Plugin, PluginSpec, get_plugins, load_default_plugins
from .routers import dataset_collection_router
from .utils.api import (
    SingleDatasetOpenAPIOverrider,
    check_route_conflicts,
    normalize_app_routers,
    normalize_datasets,
)

RouterKwargs = Dict
RouterAndKwargs = Tuple[APIRouter, RouterKwargs]


class Rest:
    """Used to publish multiple Xarray Datasets via a REST API (FastAPI application).

    To publish a single dataset via its own FastAPI application, you might
    want to use the :attr:`xarray.Dataset.rest` accessor for more convenience.
    Additionally the :class:`xpublish.SingleDatasetRest` class allows has
    a simplified interface for single dataset access.

    Parameters
    ----------
    datasets :
        A mapping of datasets objects to be served. If a mapping is given, keys
        are used as dataset ids and are converted to strings. See also the notes below.
    routers :
        A list of dataset-specific :class:`fastapi.APIRouter` instances to
        include in the fastAPI application. These routers are in addition
        to any loaded via plugins.
        The items of the list may also be tuples with the following format:
        ``[(router1, {'prefix': '/foo', 'tags': ['foo', 'bar']})]``, where
        the 1st tuple element is a :class:`fastapi.APIRouter` instance and the
        2nd element is a dictionary that is used to pass keyword arguments to
        :meth:`fastapi.FastAPI.include_router`.
    cache_kws :
        Dictionary of keyword arguments to be passed to
        :meth:`cachey.Cache.__init__()`.
        By default, the cache size is set to 1MB, but this can be changed with
        ``available_bytes``.
    app_kws :
        Dictionary of keyword arguments to be passed to
        :meth:`fastapi.FastAPI.__init__()`.
    plugins :
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
        cache_kws: Optional[Dict] = None,
        app_kws: Optional[Dict] = None,
        plugins: Optional[Dict[str, Plugin]] = None,
    ):
        if isinstance(datasets, xr.Dataset):
            raise TypeError(
                'xpublish.Rest no longer directly handles single datasets. Please use xpublish.SingleDatasetRest instead'
            )

        self.setup_datasets(datasets or {})
        self.setup_plugins(plugins)

        routers = normalize_app_routers(
            routers or [],
            self._dataset_route_prefix,
        )
        check_route_conflicts(routers)
        self._routers = routers

        self.init_app_kwargs(app_kws)
        self.init_cache_kwargs(cache_kws)

    def setup_datasets(self, datasets: Dict[str, xr.Dataset]) -> str:
        """Initialize datasets and dataset accessor function

        Returns:
            Prefix for dataset routers
        """
        self._datasets = normalize_datasets(datasets)

        self._get_dataset_func = self.get_dataset_from_plugins
        self._dataset_route_prefix = '/datasets/{dataset_id}'
        return self._dataset_route_prefix

    def get_datasets_from_plugins(self) -> List[str]:
        """Return dataset ids from directly loaded datasets and plugins

        Used as a FastAPI dependency in dataset router plugins
        via :meth:`Rest.dependencies`.

        Returns:
            Dataset IDs from plugins and datasets loaded into
            :class:`xpublish.Rest` at initialization.
        """
        dataset_ids = list(self._datasets)

        for plugin_dataset_ids in self.pm.hook.get_datasets():
            dataset_ids.extend(plugin_dataset_ids)

        return dataset_ids

    def get_dataset_from_plugins(
        self,
        dataset_id: str = Path(description='Unique ID of dataset'),
    ) -> xr.Dataset:
        """Attempt to load dataset from plugins, otherwise return dataset from passed in dictionary of datasets

        Parameters:
            dataset_id:
                Unique key of dataset to attempt to load from plugins or
                those provided to :class:`xpublish.Rest` at initialization.

        Returns:
            Dataset for selected ``dataset_id``

        Raises:
            FastAPI.HTTPException: When a dataset is not found a 404 error is returned.
        """
        dataset = self.pm.hook.get_dataset(dataset_id=dataset_id)

        if dataset:
            return dataset

        if dataset_id not in self._datasets:
            raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found")

        return self._datasets[dataset_id]

    def setup_plugins(
        self,
        plugins: Optional[Dict[str, Plugin]] = None,
    ) -> None:
        """Initialize and load plugins from entry_points unless explicitly provided

        Parameters:
            plugins:
                If a dictionary of initialized plugins is provided,
                then the automatic loading of plugins is disabled.

                Providing an empty dictionary will also disable
                automatic loading of plugins.
        """
        if plugins is None:
            plugins = load_default_plugins()

        self.pm = pluggy.PluginManager('xpublish')
        self.pm.add_hookspecs(PluginSpec)

        for name, plugin in plugins.items():
            self.pm.register(plugin, name=name)

        for hookspec in self.pm.hook.register_hookspec():
            self.pm.add_hookspecs(hookspec)

    def register_plugin(
        self,
        plugin: Plugin,
        plugin_name: Optional[str] = None,
        overwrite: bool = False,
    ) -> None:
        """
        Register a plugin with the xpublish system

        Args:
            plugin: Instantiated Plugin object
            plugin_name: Plugin name
            overwrite: If a plugin of the same name exist,
                setting this to True will remove the existing plugin before
                registering the new plugin. Defaults to False.

        Raises:
            AttributeError: Plugin can not be registered
            ValueError: Plugin already registered, try setting overwrite to True
        """
        plugin_name = plugin_name or plugin.name

        if overwrite is True and plugin_name in dict(self.pm.list_name_plugin()):
            # If a plugin exist with the same name, unregister it.
            # If configured using entry_points, the name of the
            # entry_point should be the same as the plugin.name.
            self.pm.unregister(name=plugin_name)

        # Get existing plugins again
        existing_plugins = self.pm.get_plugins()
        try:
            self.pm.register(plugin, plugin_name)
        except AttributeError as e:
            raise AttributeError(
                f'Plugin {plugin} is likely not initialized before registration'
            ) from e

        for hookspec in self.pm.subset_hook_caller(
            'register_hookspec', remove_plugins=existing_plugins
        )():
            self.pm.add_hookspecs(hookspec)

    def init_cache_kwargs(self, cache_kws: dict) -> None:
        """Set up cache kwargs"""
        self._cache = None
        self._cache_kws = {'available_bytes': 1e6}
        if cache_kws is not None:
            self._cache_kws.update(cache_kws)

    def init_app_kwargs(self, app_kws: dict) -> None:
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

    def _init_routers(self, dataset_routers: Optional[APIRouter]) -> None:
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

    def plugin_routers(self) -> Tuple[List[RouterAndKwargs], List[RouterAndKwargs]]:
        """Load the app and dataset routers for plugins

        Returns:
            A tuple containing a list of top-level routers from plugins
            and a list of per-dataset routers from plugins
        """
        app_routers = []
        dataset_routers = []

        deps = self.dependencies()

        for router in self.pm.hook.app_router(deps=deps):
            app_routers.append((router, {}))

        for router in self.pm.hook.dataset_router(deps=deps):
            dataset_routers.append((router, {}))

        return app_routers, dataset_routers

    def dependencies(self) -> Dependencies:
        """FastAPI dependencies to pass to plugin router methods"""
        deps = Dependencies(
            dataset_ids=self.get_datasets_from_plugins,
            dataset=self._get_dataset_func,
            cache=lambda: self.cache,
            plugins=lambda: self.plugins,
            plugin_manager=lambda: self.pm,
        )

        return deps

    def _init_dependencies(self) -> None:
        """Initialize dependencies"""
        deps = self.dependencies()

        self._app.dependency_overrides[get_dataset_ids] = deps.dataset_ids
        self._app.dependency_overrides[get_dataset] = deps.dataset
        self._app.dependency_overrides[get_cache] = deps.cache
        self._app.dependency_overrides[get_plugins] = deps.plugins
        self._app.dependency_overrides[get_plugin_manager] = deps.plugin_manager

    def _init_app(self) -> FastAPI:
        """Initiate the FastAPI application."""

        self._app = FastAPI(**self._app_kws)

        self._init_routers(self._routers)
        for rt, kwargs in self._app_routers:
            self._app.include_router(rt, **kwargs)

        self._init_dependencies()

        return self._app

    @property
    def app(self) -> FastAPI:
        """Returns the :class:`fastapi.FastAPI` application instance.

        Notes
        -----
        Plugins registered with :meth:`xpublish.Rest.register_plugin` after :meth:`xpublish.Rest.app`
        is accessed or :meth:`xpublish.Rest.serve` is called once may not take effect.
        """
        if self._app is None:
            self._app = self._init_app()
        return self._app

    def serve(
        self,
        host: str = '0.0.0.0',
        port: int = 9000,
        log_level: str = 'debug',
        **kwargs,
    ) -> None:
        """Serve this FastAPI application via :func:`uvicorn.run`.

        Parameters
        ----------
        host :
            Bind socket to this host.
        port :
            Bind socket to this port.
        log_level :
            App logging level, valid options are
            {'critical', 'error', 'warning', 'info', 'debug', 'trace'}.
        **kwargs :
            Additional arguments to be passed to :func:`uvicorn.run`.

        Notes
        -----
        This method is blocking and does not return.

        """
        uvicorn.run(
            self.app,
            host=host,
            port=port,
            log_level=log_level,
            **kwargs,
        )


class SingleDatasetRest(Rest):
    """Used to publish a single Xarray dataset via a REST API (FastAPI application).
    Use :class:`xpublish.Rest` to publish multiple datasets.

    Parameters:
    -----------
    dataset :
        A single :class:`xarray.Dataset` object to be served.
    """

    def __init__(
        self,
        dataset: xr.Dataset,
        routers: Optional[APIRouter] = None,
        cache_kws: Optional[Dict] = None,
        app_kws: Optional[Dict] = None,
        plugins: Optional[Dict[str, Plugin]] = None,
    ):
        self._dataset = dataset

        super().__init__({}, routers, cache_kws, app_kws, plugins)

    def setup_datasets(self, datasets) -> str:
        """Modifies the dataset loading to instead connect to the
        single dataset"""
        self._dataset_route_prefix = ''
        self._datasets = {}

        self._get_dataset_func = lambda: self._dataset

        return self._dataset_route_prefix

    def _init_app(self) -> FastAPI:
        self._app = super()._init_app()

        self._app.openapi = SingleDatasetOpenAPIOverrider(self._app).openapi

        return self._app
