"""Publish a Xarray Dataset through a rest API."""

import importlib.metadata

from .accessor import DataTreeRestAccessor, RestAccessor  # noqa: F401
from .plugins import Dependencies, Plugin, hookimpl, hookspec  # noqa: F401
from .rest import Rest, SingleDatasetRest  # noqa: F401

try:
    __version__ = importlib.metadata.version(__package__)
except importlib.metadata.PackageNotFoundError:  # pragma: no cover
    __version__ = None
