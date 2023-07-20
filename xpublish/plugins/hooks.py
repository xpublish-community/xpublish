from typing import Callable, Dict, Iterable, List, Optional

import cachey  # type: ignore
import pluggy  # type: ignore
import xarray as xr
from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..dependencies import get_cache, get_dataset, get_dataset_ids, get_plugin_manager, get_plugins

# Decorator helper to mark functions as Xpublish hook specifications
hookspec = pluggy.HookspecMarker('xpublish')

# Decorator helper to mark functions as Xpublish hook implementations
hookimpl = pluggy.HookimplMarker('xpublish')


class Dependencies(BaseModel):
    """
    A set of dependencies that are passed into plugin routers.

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
        description='Returns a dataset using ``/<dataset_id>/`` in the path.',
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
        """Dependency functions aren't easy to hash"""
        return 0  # pragma: no cover


class Plugin(BaseModel):
    """
    Xpublish plugins provide ways to extend the core of xpublish with
    new routers and other functionality.

    To create a plugin, subclass `Plugin` and add attributes that are
    subclasses of `PluginType` (`Router` for instance).

    The specific attributes correspond to how Xpublish should use
    the plugin.
    """

    name: str = Field(..., description='Fallback name of plugin')

    def __hash__(self):
        """Make sure that the plugin is hashable to load with pluggy"""
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
        """We need to override the dir as pluggy will otherwise try to inspect it,
        and Pydantic has marked it class only

        https://github.com/pydantic/pydantic/pull/1466
        """
        d = list(super().__dir__())

        d.remove('__signature__')

        return d


class PluginSpec(Plugin):
    """Plugin extension points

    Plugins do not need to implement all of the methods defined here,
    instead they implement
    """

    @hookspec
    def app_router(self, deps: Dependencies) -> APIRouter:  # type: ignore
        """Create an app (top-level) router for the plugin

        Implementations should return an APIRouter, and define
        app_router_prefix, and app_router_tags on the class,
        and use those to initialize the router.
        """

    @hookspec
    def dataset_router(self, deps: Dependencies) -> APIRouter:  # type: ignore
        """Create a dataset router for the plugin

        Implementations should return an APIRouter, and define
        dataset_router_prefix, and dataset_router_tags on the class,
        and use those to initialize the router.
        """

    @hookspec
    def get_datasets(self) -> Iterable[str]:  # type: ignore
        """Return an iterable of dataset ids that the plugin can provide"""

    @hookspec(firstresult=True)
    # type: ignore
    def get_dataset(self, dataset_id: str) -> Optional[xr.Dataset]:
        """Return a dataset by requested dataset_id.

        If the plugin does not have the dataset, return None
        """

    @hookspec
    def register_hookspec(self):  # type: ignore
        """Return additional hookspec class to register with the plugin manager"""
