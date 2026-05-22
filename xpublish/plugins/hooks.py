from typing import Callable, Dict, Iterable, List, Optional

import cachey  # type: ignore
import pluggy  # type: ignore
import xarray as xr
from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..dependencies import (
    get_cache,
    get_dataset,
    get_dataset_ids,
    get_datatree,
    get_plugin_manager,
    get_plugins,
)

# Decorator helper to mark functions as Xpublish hook specifications
hookspec = pluggy.HookspecMarker('xpublish')

# Decorator helper to mark functions as Xpublish hook implementations
hookimpl = pluggy.HookimplMarker('xpublish')


class Dependencies(BaseModel):
    """A set of dependencies that are passed into plugin routers.

    Some routers may be 'borrowed' by other routers to expose different
    geometries of data, thus the default dependencies may need to be overridden.
    By depending on the passed in version of this class, the dependencies
    can be overridden predictably.
    """

    dataset_ids: Callable[..., List[str]] = Field(
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
    cache: Callable[..., cachey.Cache] = Field(
        get_cache,
        description='Provide access to :py:class:`cachey.Cache`',
    )
    plugins: Callable[..., Dict[str, 'Plugin']] = Field(
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

        # try/except is for pydantic backwards compatibility
        try:
            model_dict = self.model_dump()
        except AttributeError:
            model_dict = self.dict()

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
        d = list(super().__dir__())

        d.remove('__signature__')

        return d


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
    def get_datasets(self) -> Iterable[str]:  # type: ignore
        """Return an iterable of dataset ids that the plugin can provide."""

    @hookspec(firstresult=True)
    # type: ignore
    def get_datatree(self, dataset_id: str, group: str) -> Optional[xr.DataTree]:
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
        """

    @hookspec(firstresult=True)
    # type: ignore
    def get_dataset(self, dataset_id: str) -> Optional[xr.Dataset]:
        """Return a :py:class:`xarray.Dataset` for ``dataset_id``.

        Use this hook when your provider only serves flat datasets — Xpublish
        wraps the returned Dataset in a single-node :py:class:`xarray.DataTree`
        internally. For hierarchical providers, implement :meth:`get_datatree`
        instead, which also receives the requested ``group`` path.

        Both hooks are first-class and may coexist; :meth:`get_datatree` is
        consulted first.

        If the plugin does not have the dataset, return ``None``.
        """

    @hookspec
    def register_hookspec(self):  # type: ignore
        """Return additional hookspec class to register with the plugin manager."""
