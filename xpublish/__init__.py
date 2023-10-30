try:
    import importlib.metadata as importlib_metadata
except ImportError:
    import importlib_metadata

from .accessor import RestAccessor  # noqa: F401
from .plugins import Dependencies, Plugin, hookimpl, hookspec  # noqa: F401
from .rest import Rest, SingleDatasetRest  # noqa: F401

try:
    __version__ = importlib_metadata.version(__package__)
except importlib_metadata.PackageNotFoundError:
    __version__ = None
