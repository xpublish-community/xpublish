from dataclasses import dataclass, field
from typing import Callable, List

import cachey
import xarray as xr
from fastapi import APIRouter

from ..dependencies import get_cache, get_dataset, get_dataset_ids


@dataclass
class XpublishFactory:
    """Xpublish API router factory."""

    router: APIRouter = field(default_factory=APIRouter)

    dataset_ids_dependency: Callable[..., List[str]] = get_dataset_ids
    dataset_dependency: Callable[..., xr.Dataset] = get_dataset
    cache_dependency: Callable[..., cachey.Cache] = get_cache

    def __post_init__(self):
        self.register_routes()

    def register_routes(self):
        """Register xpublish routes."""
        raise NotImplementedError()
