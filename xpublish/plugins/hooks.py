from typing import Callable, Dict, Iterable, List, Optional

import cachey  # type: ignore
import pluggy  # type: ignore
import xarray as xr
from fastapi import APIRouter
from pydantic import BaseModel

from ..dependencies import get_cache, get_dataset, get_dataset_ids, get_plugin_manager, get_plugins

hookspec = pluggy.HookspecMarker('xpublish')
hookimpl = pluggy.HookimplMarker('xpublish')


class Dependencies(BaseModel):
    dataset_ids: Callable[..., List[str]] = get_dataset_ids
    dataset: Callable[..., xr.Dataset] = get_dataset
    cache: Callable[..., cachey.Cache] = get_cache
    plugins: Callable[..., Dict[str, 'Plugin']] = get_plugins
    plugin_manager: Callable[..., pluggy.PluginManager] = get_plugin_manager

    def __hash__(self):
        """Dependency functions aren't easy to hash"""
        return 0


class Plugin(BaseModel):
    """
    Xpublish plugins provide ways to extend the core of xpublish with
    new routers and other functionality.

    To create a plugin, subclass ``Plugin` and add attributes that are
    subclasses of `PluginType` (`Router` for instance).

    The specific attributes correspond to how Xpublish should use
    the plugin.
    """

    name: str

    def __hash__(self):
        """Make sure that the plugin is hashable to load with pluggy"""
        things_to_hash = []

        for e in self.dict():
            if isinstance(e, list):
                things_to_hash.append(tuple(e))
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
    """Plugin extension points"""

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
    def get_dataset(self, dataset_id: str) -> Optional[xr.Dataset]:  # type: ignore
        """Return a dataset by requested dataset_id.

        If the plugin does not have the dataset, return None
        """

    @hookspec
    def register_hookspec(self):  # type: ignore
        """Return additional hookspec classes to register with the plugin manager"""
