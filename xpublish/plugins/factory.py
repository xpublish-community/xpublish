from dataclasses import dataclass, field
from typing import Callable, List, Optional

import cachey
import xarray as xr
from fastapi import APIRouter

from ..dependencies import get_cache, get_dataset, get_dataset_ids


@dataclass
class XpublishPluginFactory:
    """Xpublish plugin factory.

    Xpublish plugins are designed to be automatically loaded via the entry point
    group `xpublish.plugin` from any installed package.

    Plugins can define both app (top-level) and dataset based routes, and
    default prefixes and tags for both.

    Parameters
    ----------
    app_router : ApiRouter
        Router for defining top level routes, that is routes
        that are not nested under a dataset.
    app_router_prefix : str
        Default prefix for all app level routes.
    app_router_tags : list
        Default OpenAPI tags for app level routes.
    dataset_router : ApiRouter
        Routes that work with individual datasets.
    dataset_router_prefix : str
        Default prefix for routes under a dataset.
    dataset_router_tags : list
        Default OpenAPI tags for dataset level routes
    dataset_ids_dependency :
        Access the current dataset ids
    dataset_dependency :
        Load the specified dataset in path
    cache_dependency :
        Access the cache
    """

    app_router: APIRouter = field(default_factory=APIRouter)
    app_router_prefix: Optional[str] = None
    app_router_tags: List[str] = field(default_factory=list)

    dataset_router: APIRouter = field(default_factory=APIRouter)
    dataset_router_prefix: Optional[str] = None
    dataset_router_tags: List[str] = field(default_factory=list)

    dataset_ids_dependency: Callable[..., List[str]] = get_dataset_ids
    dataset_dependency: Callable[..., xr.Dataset] = get_dataset
    cache_dependency: Callable[..., cachey.Cache] = get_cache

    def __post_init__(self):
        self.register_routes()

    def register_routes(self):
        """Register xpublish routes."""
        raise NotImplementedError()
