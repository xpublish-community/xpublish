from collections.abc import Callable, Iterable, MutableMapping
from typing import Any

import pluggy  # type: ignore
import xarray as xr
from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..dependencies import (
    get_cache,
    get_dataset,
    get_dataset_ids,
    get_datatree,
    get_lru_cache,
    get_plugin_manager,
    get_plugins,
    get_ttl_cache,
)
from ..utils.cache import LegacyCache

# Decorator helper to mark functions as Xpublish hook specifications
hookspec = pluggy.HookspecMarker('xpublish')

# Decorator helper to mark functions as Xpublish hook implementations
hookimpl = pluggy.HookimplMarker('xpublish')

# Deprecated or otherwise inaccessible Pydantic fields that pluggy should ignore when inspecting plugins
PYDANTIC_INACCESSIBLE_FIELDS = {
    '__fields__',  # 2.0
    '__fields_set__',  # 2.0
    'model_computed_fields',  # 2.1
    'model_fields',  # 2.1
    '__signature__',  # Class only
}


class Plugin(BaseModel):
    """Xpublish plugins provide ways to extend the core of xpublish with new routers and other functionality.

    To create a plugin, subclass `Plugin` and add attributes that are
    subclasses of `PluginType` (`Router` for instance).

    The specific attributes correspond to how Xpublish should use
    the plugin.
    """

    name: str = Field(..., description='Fallback name of plugin')

    def __hash__(self):
        """Make sure that the plugin is hashable to load with pluggy."""
        things_to_hash = []
        model_dict = self.model_dump()

        for e in model_dict:
            if isinstance(e, list):
                things_to_hash.append(tuple(e))  # pragma: no cover
            else:
                things_to_hash.append(e)

        return hash(tuple(things_to_hash))

    def __dir__(self) -> Iterable[str]:
        """Overrides the dir.

        We need to override the dir as pluggy will otherwise try to inspect it,
        and Pydantic has marked it class only

        https://github.com/pydantic/pydantic/pull/1466
        """
        d = set(super().__dir__())

        d = d.difference(PYDANTIC_INACCESSIBLE_FIELDS)

        return d


class Dependencies(BaseModel):
    """A set of dependencies that are passed into plugin routers.

    Some routers may be 'borrowed' by other routers to expose different
    geometries of data, thus the default dependencies may need to be overridden.
    By depending on the passed in version of this class, the dependencies
    can be overridden predictably.
    """

    dataset_ids: Callable[..., list[str]] = Field(
        get_dataset_ids,
        description='Returns a list of all valid dataset ids',
    )
    dataset: Callable[[str], xr.Dataset] = Field(
        get_dataset,
        description=(
            'Returns the :py:class:`xarray.Dataset` at ``/<dataset_id>/`` in the path. '
            'If the route includes a ``{group_path:path}`` parameter, returns the dataset '
            'at that node of the underlying DataTree; otherwise returns the root dataset.'
        ),
    )
    datatree: Callable[[str], xr.DataTree] = Field(
        get_datatree,
        description=(
            'Returns the :py:class:`xarray.DataTree` rooted at ``/<dataset_id>/`` (or at '
            '``{group_path:path}`` if present in the route).'
        ),
    )
    cache: Callable[..., LegacyCache] = Field(
        get_cache,
        description='Deprecated: cachey-style ``get``/``put`` cache. Use ``get_lru_cache`` or ``get_ttl_cache``.',
    )
    get_lru_cache: Callable[..., MutableMapping] = Field(
        get_lru_cache,
        description=(
            'Call ``deps.get_lru_cache(namespace, maxsize=128, *, getsizeof=None)`` to get a '
            'mutable mapping with LRU eviction. Not a ``Depends`` target.'
        ),
    )
    get_ttl_cache: Callable[..., MutableMapping] = Field(
        get_ttl_cache,
        description=(
            'Call ``deps.get_ttl_cache(namespace, maxsize=128, ttl=600, *, getsizeof=None)`` to get '
            'a mutable mapping whose entries expire. Not a ``Depends`` target.'
        ),
    )
    plugins: Callable[..., dict[str, Plugin]] = Field(
        get_plugins,
        description='A dictionary of plugins allowing direct access',
    )
    plugin_manager: Callable[..., pluggy.PluginManager] = Field(
        get_plugin_manager,
        description='The plugin manager itself, allowing for maximum creativity',
    )

    def __hash__(self):
        """Dependency functions aren't easy to hash."""
        return 0  # pragma: no cover


class PluginSpec(Plugin):
    """Plugin extension points.

    Plugins do not need to implement all of the methods defined here,
    instead they implement
    """

    @hookspec
    def app_router(self, deps: Dependencies) -> APIRouter:  # type: ignore
        """Create an app (top-level) router for the plugin.

        Implementations should return an APIRouter, and define
        app_router_prefix, and app_router_tags on the class,
        and use those to initialize the router.
        """

    @hookspec
    def dataset_router(self, deps: Dependencies) -> APIRouter:  # type: ignore
        """Create a dataset router for the plugin.

        Implementations should return an APIRouter, and define
        dataset_router_prefix, and dataset_router_tags on the class,
        and use those to initialize the router.
        """

    @hookspec
    def get_datasets(self, deps: Dependencies) -> Iterable[str]:  # type: ignore
        """Return an iterable of dataset ids that the plugin can provide.

        ``deps`` is optional: declare it in your implementation to reach
        :meth:`Dependencies.get_lru_cache` and :meth:`Dependencies.get_ttl_cache`,
        and omit it otherwise (pluggy only passes the arguments you declare).
        Declare it as a positional parameter. Do not call ``deps.dataset``,
        ``deps.datatree`` or ``deps.dataset_ids`` from inside this hook: they
        resolve through the provider hooks and would recurse.

        Example, caching the listing for a minute::

            @hookimpl
            def get_datasets(self, deps):
                cache = deps.get_ttl_cache(self.name, maxsize=1, ttl=60)
                if "ids" not in cache:
                    cache["ids"] = list(self._list_remote_ids())
                return cache["ids"]
        """

    @hookspec(firstresult=True)
    # type: ignore
    def get_datatree(
        self,
        dataset_id: str,
        group: str,
        deps: Dependencies,
    ) -> xr.DataTree | None:
        """Return a :py:class:`xarray.DataTree` for ``dataset_id`` rooted at ``group``.

        Implementations should declare ``group`` as a positional parameter
        (pluggy will not forward keyword-only parameters). An empty ``group``
        string means "the root".

        Providers decide how to be smart about this. Providers that only ever serve
        flat datasets can return ``xr.DataTree(dataset=ds)`` (a single-node tree) and
        ``None`` for any non-empty ``group``. Providers that have hierarchical data
        can return either the full tree (and index into it with ``group``) or, for
        lazy backends, open only the requested ``group`` and wrap it in a single-node
        tree.

        The returned tree's root corresponds to the requested ``group``.

        If the plugin does not have the dataset, return ``None``.

        ``deps`` is optional: declare it in your implementation to reach
        :meth:`Dependencies.get_lru_cache` and :meth:`Dependencies.get_ttl_cache`,
        and omit it otherwise (pluggy only passes the arguments you declare).
        Declare it as a positional parameter. Do not call ``deps.dataset``,
        ``deps.datatree`` or ``deps.dataset_ids`` from inside this hook: they
        resolve through the provider hooks and would recurse.

        Example, caching opened trees::

            @hookimpl
            def get_datatree(self, dataset_id, group, deps):
                cache = deps.get_lru_cache(self.name, maxsize=2**28, getsizeof=nbytes)
                key = f"{dataset_id}/{group}"
                if key not in cache:
                    cache[key] = self._open(dataset_id, group)
                return cache[key]
        """

    @hookspec(firstresult=True)
    # type: ignore
    def get_dataset(self, dataset_id: str, deps: Dependencies) -> xr.Dataset | None:
        """Return a :py:class:`xarray.Dataset` for ``dataset_id``.

        Use this hook when your provider only serves flat datasets — Xpublish
        wraps the returned Dataset in a single-node :py:class:`xarray.DataTree`
        internally. For hierarchical providers, implement :meth:`get_datatree`
        instead, which also receives the requested ``group`` path.

        Both hooks are first-class and may coexist; :meth:`get_datatree` is
        consulted first.

        If the plugin does not have the dataset, return ``None``.

        ``deps`` is optional: declare it in your implementation to reach
        :meth:`Dependencies.get_lru_cache` and :meth:`Dependencies.get_ttl_cache`,
        and omit it otherwise (pluggy only passes the arguments you declare).
        Declare it as a positional parameter. Do not call ``deps.dataset``,
        ``deps.datatree`` or ``deps.dataset_ids`` from inside this hook: they
        resolve through the provider hooks and would recurse.
        """

    @hookspec
    def register_hookspec(self):  # type: ignore
        """Return additional hookspec class to register with the plugin manager."""

    @hookspec(firstresult=True)
    def get_lru_cache(  # type: ignore
        self,
        namespace: str,
        maxsize: int,
        getsizeof: Callable[[Any], float] | None,
    ) -> MutableMapping | None:
        """Provide an LRU cache for ``namespace``, or ``None`` to decline.

        Implementations return a :py:class:`collections.abc.MutableMapping`.
        The same namespace should yield the same cache.
        ``maxsize`` and ``getsizeof`` are hints a provider may ignore, and
        providers may serialize values. Returning ``None`` falls back to
        the next provider and finally to xpublish's built-in local cache.
        """

    @hookspec(firstresult=True)
    def get_ttl_cache(  # type: ignore
        self,
        namespace: str,
        maxsize: int,
        ttl: float,
        getsizeof: Callable[[Any], float] | None,
    ) -> MutableMapping | None:
        """Provide a time-expiring cache for ``namespace``, or ``None`` to decline.

        Same contract as :meth:`get_lru_cache`, with entries expiring ``ttl``
        seconds after they were written.
        """
