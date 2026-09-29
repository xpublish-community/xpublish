import logging
import os
from collections.abc import MutableMapping
from typing import (
    Annotated,
    Literal,
)

import pluggy
import uvicorn
import xarray as xr
from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    HTTPException,
    Path,
)

from .dependencies import (
    get_cache,
    get_cache_store,
    get_dataset,
    get_dataset_ids,
    get_datatree,
    get_group_path,
    get_plugin_manager,
)
from .plugins import (
    Dependencies,
    Plugin,
    PluginSpec,
    get_plugins,
    load_default_plugins,
)
from .routers import dataset_collection_router
from .utils.api import (
    DATASET_ID_ATTR_KEY,
    SingleDatasetOpenAPIOverrider,
    check_route_conflicts,
    normalize_app_routers,
    normalize_datasets,
)
from .utils.cache import (
    CACHE_BYTES_ENV,
    CacheyCache,
    lru_bytes_store,
)

RouterKwargs = dict
RouterAndKwargs = tuple[APIRouter, RouterKwargs]
LogLevels = Literal['critical', 'error', 'warning', 'info', 'debug', 'trace']

logger = logging.getLogger(__name__)


class Rest:
    """Used to publish multiple Xarray Datasets / DataTrees via a REST API (FastAPI application).

    Internally everything is stored as a :py:class:`xarray.DataTree`; a bare
    :py:class:`xarray.Dataset` is wrapped in a single-node tree.

    To publish a single dataset via its own FastAPI application, you might
    want to use the :attr:`xarray.Dataset.rest` accessor for more convenience.
    Additionally the :class:`xpublish.SingleDatasetRest` class allows has
    a simplified interface for single dataset access.

    NOTE: The urls of the application's API endpoints differ whether a single
    dataset or a mapping (collection) of datasets is given. In the latter case,
    all dataset-specific endpoint urls have the prefix ``/datasets/{dataset_id}``,
    where ``{dataset_id}`` corresponds to the keys of the mapping (converted to
    strings). Still in the latter case, the endpoint ``/datasets`` is added and
    returns the list of all dataset ids.

    Routes can additionally use a ``{group_path:path}`` path parameter to
    navigate into a node of the underlying DataTree; the built-in
    ``deps.dataset`` and ``deps.datatree`` dependencies read it automatically.
    """

    def __init__(
        self,
        datasets: dict[str, xr.Dataset | xr.DataTree] | None = None,
        routers: list[APIRouter] | None = None,
        cache_kws: dict | None = None,
        app_kws: dict | None = None,
        plugins: dict[str, Plugin] | None = None,
        cache: MutableMapping | None = None,
    ):
        """Initialize a REST object for publishing Xarray Datasets / DataTrees.

        Args:
            datasets: A mapping of dataset or DataTree objects to be served. Keys
                are used as dataset ids (converted to strings). Bare Datasets are
                wrapped in a single-node DataTree internally. See also the notes
                below.
            routers: A list of dataset-specific :class:`fastapi.APIRouter`
                instances to include in the fastAPI application. These routers are
                in addition to any loaded via plugins. The items of the list may
                also be tuples with the following format:
                ``[(router1, {'prefix': '/foo', 'tags': ['foo', 'bar']})]``, where
                the 1st tuple element is a :class:`fastapi.APIRouter` instance and
                the 2nd element is a dictionary that is used to pass keyword
                arguments to :meth:`fastapi.FastAPI.include_router`.
            cache_kws: Dictionary of cache keyword arguments. The cache is a
                least-recently-used cache with a byte budget, which defaults to
                1MB and can be changed with ``available_bytes``. The
                ``XPUBLISH_CACHE_BYTES`` environment variable overrides both.
            app_kws: Dictionary of keyword arguments to be passed to
                :meth:`fastapi.FastAPI.__init__()`.
            plugins: Optional dictionary of loaded, configured plugins. Overrides
                automatic loading of plugins. If no plugins are desired, set to an
                empty dict.
            cache: An explicit mutable mapping to store cached values in (a
                ``cachetools`` cache, a plain dict, a shared store, ...),
                instead of the one xpublish builds. Mutually exclusive with
                ``cache_kws``.
        """
        if isinstance(datasets, (xr.Dataset, xr.DataTree)):
            raise TypeError(
                'xpublish.Rest no longer directly handles single datasets or DataTrees. '
                'Please use xpublish.SingleDatasetRest instead'
            )

        self.setup_datasets(datasets or {})
        self.setup_plugins(plugins)

        normalized_routers: list[tuple[APIRouter, dict]] = normalize_app_routers(
            routers or [],
            self._dataset_route_prefix,
        )
        check_route_conflicts(normalized_routers)
        self._routers = normalized_routers

        self.init_app_kwargs(app_kws)
        self.init_cache(cache, cache_kws)

    def setup_datasets(
        self,
        datasets: dict[str, xr.Dataset | xr.DataTree],
    ) -> str:
        """Initialize datasets and dataset accessor functions.

        Bare :py:class:`xarray.Dataset` values are wrapped in a single-node
        :py:class:`xarray.DataTree` so the internal storage is uniform.

        Args:
            datasets: Dictionary of datasets/DataTrees to serve with their
                names as keys.

        Returns:
            Prefix for dataset routers
        """
        self._datasets = normalize_datasets(datasets)

        self._get_dataset_func = self.get_dataset_from_plugins
        self._get_datatree_func = self.get_datatree_from_plugins
        self._dataset_route_prefix = '/datasets/{dataset_id}'
        return self._dataset_route_prefix

    def get_datasets_from_plugins(self) -> list[str]:
        """Return dataset ids from directly loaded datasets and plugins.

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

    def _resolve_datatree(self, dataset_id: str, group: str) -> xr.DataTree:
        """Resolve a (dataset_id, group) pair to an :py:class:`xarray.DataTree`.

        Tries ``get_datatree`` plugin hooks first, then the flat ``get_dataset``
        hook (whose Dataset is wrapped in a single-node tree), then the directly
        registered datasets.

        Raises:
            FastAPI.HTTPException: 404 if the dataset_id is unknown, or if the
                group does not exist within the resolved tree.
        """
        try:
            tree: xr.DataTree | None = self.pm.hook.get_datatree(
                dataset_id=dataset_id,
                group=group,
            )
        except KeyError as err:
            raise HTTPException(
                status_code=404,
                detail=f"Group '{group}' not found in dataset '{dataset_id}'",
            ) from err

        if tree is None:
            legacy_ds: xr.Dataset | None = self.pm.hook.get_dataset(dataset_id=dataset_id)
            if legacy_ds is not None:
                if group:
                    raise HTTPException(
                        status_code=404,
                        detail=(
                            f"Group '{group}' not found in dataset '{dataset_id}' "
                            '(provider only implements the flat get_dataset hook)'
                        ),
                    )
                tree = xr.DataTree(dataset=legacy_ds)

        if tree is None:
            if dataset_id not in self._datasets:
                raise HTTPException(
                    status_code=404,
                    detail=f"Dataset '{dataset_id}' not found",
                )
            full_tree = self._datasets[dataset_id]
            try:
                tree = full_tree[group] if group else full_tree
            except KeyError as err:
                raise HTTPException(
                    status_code=404,
                    detail=f"Group '{group}' not found in dataset '{dataset_id}'",
                ) from err

        # The id identifies the node, not only the root dataset.
        #
        # A group's id is built from the id on its tree's root, so a provider that
        # versions that id (a refreshed dataset, say) moves every node under it
        # and the caches keyed on them fall out of date together.
        root_node = tree.root
        base_id = root_node.dataset.attrs.get(DATASET_ID_ATTR_KEY) or dataset_id
        node_id = base_id if root_node is tree else f'{base_id}/{group}'

        root_ds = tree.dataset
        if root_ds.attrs.get(DATASET_ID_ATTR_KEY) != node_id:
            tree.dataset = root_ds.assign_attrs({DATASET_ID_ATTR_KEY: node_id})

        return tree

    def get_datatree_from_plugins(
        self,
        dataset_id: Annotated[str, Path(description='Unique ID of dataset')],
        group: Annotated[str, Depends(get_group_path)] = '',
    ) -> xr.DataTree:
        """Resolve a DataTree by ``dataset_id`` (and optional ``group``).

        When used as a FastAPI dependency, ``group`` is auto-extracted from the
        route's ``{group_path:path}`` segment via :func:`get_group_path`. When
        called directly, ``group`` defaults to the empty string (returning the
        root tree) and may be passed explicitly to navigate into the tree.
        """
        return self._resolve_datatree(dataset_id, group)

    def get_dataset_from_plugins(
        self,
        dataset_id: Annotated[str, Path(description='Unique ID of dataset')],
        group: Annotated[str, Depends(get_group_path)] = '',
    ) -> xr.Dataset:
        """Resolve a Dataset by ``dataset_id`` (and optional ``group``).

        When used as a FastAPI dependency, ``group`` is auto-extracted from the
        route's ``{group_path:path}`` segment via :func:`get_group_path`. When
        called directly, ``group`` defaults to the empty string (returning the
        root dataset) and may be passed explicitly to navigate into the tree.

        Returns:
            Dataset for the selected ``dataset_id`` (at the selected group node).

        Raises:
            FastAPI.HTTPException: When the dataset or group is not found.
        """
        return self._resolve_datatree(dataset_id, group).dataset

    def setup_plugins(
        self,
        plugins: dict[str, Plugin] | None = None,
    ) -> None:
        """Initialize and load plugins from entry_points unless explicitly provided.

        Args:
            plugins: A dictionary of initialized plugins. If provided,
                then the automatic loading of plugins is disabled. Providing an
                empty dictionary will also disable automatic loading of plugins.
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
        plugin_name: str | None = None,
        overwrite: bool = False,
    ) -> None:
        """Register a plugin with the xpublish system.

        Args:
            plugin: Instantiated Plugin object.
            plugin_name: Plugin name.
            overwrite: If a plugin of the same name exist,
                setting this to True will remove the existing plugin before
                registering the new plugin. Defaults to False.

        Raises:
            AttributeError: Plugin can not be registered.
            ValueError: Plugin already registered, try setting overwrite to True.
        """
        try:
            plugin_name = plugin_name or plugin.name

            if overwrite is True and plugin_name in dict(self.pm.list_name_plugin()):
                # If a plugin exist with the same name, unregister it.
                # If configured using entry_points, the name of the
                # entry_point should be the same as the plugin.name.
                self.pm.unregister(name=plugin_name)

            # Get existing plugins again
            existing_plugins = self.pm.get_plugins()
            self.pm.register(plugin, plugin_name)

        except AttributeError as e:
            raise AttributeError(
                f'Plugin {plugin} is likely not initialized before registration'
            ) from e

        for hookspec in self.pm.subset_hook_caller(
            'register_hookspec', remove_plugins=existing_plugins
        )():
            self.pm.add_hookspecs(hookspec)

    def init_cache(
        self,
        cache: MutableMapping | None,
        cache_kws: dict | None,
    ) -> None:
        """Set up the application cache.

        Either an explicit cache mapping or a dictionary of cache options may
        be given, not both. Without an explicit cache, the size can be
        overridden at runtime with the ``XPUBLISH_CACHE_BYTES`` environment
        variable.

        Args:
            cache: An explicit mutable mapping to store cached values in.
            cache_kws: Dictionary of cache keyword arguments. The only
                supported key is ``available_bytes``.

        Raises:
            TypeError: ``cache`` was given and is not a
                :class:`collections.abc.MutableMapping`, or an unsupported
                cache keyword argument was passed.
            ValueError: Both ``cache`` and ``cache_kws`` were given, or
                ``XPUBLISH_CACHE_BYTES`` is not a number.
        """
        if cache is not None and cache_kws is not None:
            raise ValueError(
                'Pass either cache or cache_kws, not both. cache_kws only '
                'configures the cache that xpublish builds for itself.'
            )

        if cache is not None and not isinstance(cache, MutableMapping):
            raise TypeError(
                f'{type(cache).__name__} is not a MutableMapping. Pass a '
                'mutable mapping such as xpublish.lru_bytes_store(n) or a '
                'LockedMapping(...).'
            )

        self._cache = None
        self._cache_instance = cache
        self._cache_kws = {'available_bytes': 1e6}
        if cache_kws is not None:
            for key in cache_kws:
                if key != 'available_bytes':
                    raise TypeError(
                        f'Unsupported cache keyword argument {key!r}. '
                        'cachey-specific cache options have been removed; '
                        'pass a custom cache instead.'
                    )
            self._cache_kws.update(cache_kws)

        env_bytes = os.environ.get(CACHE_BYTES_ENV)
        if env_bytes is None:
            return

        if cache is not None:
            # An explicit mapping was supplied, so the env var is irrelevant;
            # it isn't even parsed, so a malformed value can't fail startup.
            logger.warning(
                '%s is ignored because a cache instance was supplied',
                CACHE_BYTES_ENV,
            )
            return

        try:
            available_bytes = float(env_bytes)
        except ValueError as err:
            raise ValueError(f'{CACHE_BYTES_ENV} must be a number, got {env_bytes!r}') from err

        self._cache_kws['available_bytes'] = available_bytes
        logger.info(
            '%s overrode the cache size, which is now %s bytes',
            CACHE_BYTES_ENV,
            available_bytes,
        )

    def init_cache_kwargs(self, cache_kws: dict | None) -> None:
        """Set up cache kwargs, without an explicit cache instance.

        Args:
            cache_kws: Dictionary of cache keyword arguments, as described on
                :meth:`Rest.init_cache`.
        """
        self.init_cache(None, cache_kws)

    def init_app_kwargs(self, app_kws: dict | None) -> None:
        """Set up FastAPI application kwargs.

        Args:
            app_kws: Dictionary of FastAPI application keyword arguments.
        """
        self._app = None
        self._app_kws = {}
        if app_kws is not None:
            self._app_kws.update(app_kws)

    def _build_cache(self) -> CacheyCache:
        """Build the cache.

        An explicit ``cache=`` wins, then any store offered by a plugin's
        ``get_cache`` hook, and otherwise xpublish builds its own byte-budgeted
        LRU store. Whichever store is chosen is always wrapped in
        :class:`xpublish.CacheyCache`.
        """
        store = self._cache_instance

        if store is None:
            store = self.pm.hook.get_cache(cache_kws=dict(self._cache_kws))
            if store is not None:
                providers = ', '.join(
                    impl.plugin_name for impl in self.pm.hook.get_cache.get_hookimpls()
                )
                logger.info(
                    'Using the %s cache store provided by plugin(s) %s',
                    type(store).__name__,
                    providers,
                )

        if store is None:
            store = lru_bytes_store(self._cache_kws['available_bytes'])

        return CacheyCache(store)

    @property
    def cache(self) -> CacheyCache:
        """Returns the cache used by the FastAPI application."""
        if self._cache is None:
            self._cache = self._build_cache()
        return self._cache

    @property
    def cache_store(self) -> MutableMapping:
        """Returns the raw mapping behind the application cache.

        Plugins that want to layer their own policy over the shared store can
        use this instead of :attr:`Rest.cache`. The store is always present
        and is always the mapping backing :attr:`Rest.cache`.
        """
        return self.cache.mapping

    @property
    def plugins(self) -> dict[str, Plugin]:
        """Returns the loaded plugins."""
        return dict(self.pm.list_name_plugin())

    def _init_routers(self, dataset_routers: APIRouter | None) -> None:
        """Setup plugin and dataset routers. Needs to run after dataset and plugin setup."""
        app_routers, plugin_dataset_routers = self.plugin_routers()

        if self._dataset_route_prefix:
            app_routers.append((dataset_collection_router, {'tags': ['info']}))

        app_routers.extend(
            normalize_app_routers(
                plugin_dataset_routers + (dataset_routers or []),
                self._dataset_route_prefix,
            )
        )

        check_route_conflicts(app_routers)

        self._app_routers = app_routers

    def plugin_routers(self) -> tuple[list[RouterAndKwargs], list[RouterAndKwargs]]:
        """Load the app and dataset routers for plugins.

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
        """FastAPI dependencies to pass to plugin router methods.

        Returns:
            initialized :class:xpublish.plugins.Dependencies object.
        """
        deps = Dependencies(
            dataset_ids=self.get_datasets_from_plugins,
            dataset=self._get_dataset_func,
            datatree=self._get_datatree_func,
            cache=lambda: self.cache,
            cache_store=lambda: self.cache_store,
            plugins=lambda: self.plugins,
            plugin_manager=lambda: self.pm,
        )

        return deps

    def _init_dependencies(self) -> None:
        """Initialize dependencies."""
        deps = self.dependencies()

        self._app.dependency_overrides[get_dataset_ids] = deps.dataset_ids
        self._app.dependency_overrides[get_dataset] = deps.dataset
        self._app.dependency_overrides[get_datatree] = deps.datatree
        self._app.dependency_overrides[get_cache] = deps.cache
        self._app.dependency_overrides[get_cache_store] = deps.cache_store
        self._app.dependency_overrides[get_plugins] = deps.plugins
        self._app.dependency_overrides[get_plugin_manager] = deps.plugin_manager

    def _init_app(self) -> FastAPI:
        """Initiate the FastAPI application.

        Returns:
            FastAPI application instance.
        """
        self._app = FastAPI(**self._app_kws)

        self._init_routers(self._routers)
        for rt, kwargs in self._app_routers:
            self._app.include_router(rt, **kwargs)

        self._init_dependencies()

        return self._app

    @property
    def app(self) -> FastAPI:
        """Returns the :class:`fastapi.FastAPI` application instance.

        NOTE: Plugins registered with :meth:`xpublish.Rest.register_plugin`
        after :meth:`xpublish.Rest.app` is accessed or :meth:`xpublish.Rest.serve`
        is called once may not take effect.
        """
        if self._app is None:
            self._app = self._init_app()
        return self._app

    def serve(
        self,
        host: str | None = '0.0.0.0',
        port: int | None = 9000,
        log_level: LogLevels | None = 'debug',
        **kwargs,
    ) -> None:
        """Serve this FastAPI application via :func:`uvicorn.run`.

        NOTE: This method is blocking and does not return.

        Args:
            host: Bind socket to this host.
            port: Bind socket to this port.
            log_level: App logging level, valid options are
                {'critical', 'error', 'warning', 'info', 'debug', 'trace'}.
            **kwargs: Additional arguments to be passed to :func:`uvicorn.run`.
        """
        uvicorn.run(
            self.app,
            host=host,
            port=port,
            log_level=log_level,
            **kwargs,
        )


class SingleDatasetRest(Rest):
    """Used to publish a single Xarray Dataset or DataTree via a REST API (FastAPI application).

    Use :class:`xpublish.Rest` to publish multiple datasets.
    """

    def __init__(
        self,
        dataset: xr.Dataset | xr.DataTree,
        routers: list[APIRouter] | None = None,
        cache_kws: dict | None = None,
        app_kws: dict | None = None,
        plugins: dict[str, Plugin] | None = None,
        cache: MutableMapping | None = None,
    ):
        """Initialize the SingleDatasetRest object.

        Args:
            dataset: A single :class:`xarray.Dataset` or :class:`xarray.DataTree`
                object to be served. A Dataset is wrapped in a single-node
                DataTree internally.
            routers: A list of dataset-specific :class:`fastapi.APIRouter`
                instances to include in the fastAPI application. These routers are
                in addition to any loaded via plugins. The items of the list may
                also be tuples with the following format:
                ``[(router1, {'prefix': '/foo', 'tags': ['foo', 'bar']})]``, where
                the 1st tuple element is a :class:`fastapi.APIRouter` instance and
                the 2nd element is a dictionary that is used to pass keyword
                arguments to :meth:`fastapi.FastAPI.include_router`.
            cache_kws: Dictionary of cache keyword arguments. The cache is a
                least-recently-used cache with a byte budget, which defaults to
                1MB and can be changed with ``available_bytes``. The
                ``XPUBLISH_CACHE_BYTES`` environment variable overrides both.
            app_kws: Dictionary of keyword arguments to be passed to
                :meth:`fastapi.FastAPI.__init__()`.
            plugins: Optional dictionary of loaded, configured plugins. Overrides
                automatic loading of plugins. If no plugins are desired, set to an
                empty dict.
            cache: An explicit mutable mapping to store cached values in (a
                ``cachetools`` cache, a plain dict, a shared store, ...),
                instead of the one xpublish builds. Mutually exclusive with
                ``cache_kws``.
        """
        if isinstance(dataset, xr.DataTree):
            self._tree = dataset
        else:
            self._tree = xr.DataTree(dataset=dataset)

        super().__init__(
            datasets={},
            routers=routers,
            cache_kws=cache_kws,
            app_kws=app_kws,
            plugins=plugins,
            cache=cache,
        )

    def setup_datasets(self, datasets) -> str:
        """Modifies dataset loading to instead connect to the single dataset/DataTree."""
        self._dataset_route_prefix = ''
        self._datasets = {}

        def _single_datatree(
            group: Annotated[str, Depends(get_group_path)] = '',
        ) -> xr.DataTree:
            if not group:
                return self._tree
            try:
                return self._tree[group]
            except KeyError as err:
                raise HTTPException(
                    status_code=404,
                    detail=f"Group '{group}' not found",
                ) from err

        def _single_dataset(
            group: Annotated[str, Depends(get_group_path)] = '',
        ) -> xr.Dataset:
            return _single_datatree(group).dataset

        self._get_dataset_func = _single_dataset
        self._get_datatree_func = _single_datatree

        return self._dataset_route_prefix

    def _init_app(self) -> FastAPI:
        self._app = super()._init_app()

        self._app.openapi = SingleDatasetOpenAPIOverrider(self._app).openapi

        return self._app
