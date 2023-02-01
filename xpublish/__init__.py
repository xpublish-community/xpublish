from pkg_resources import DistributionNotFound, get_distribution

from .accessor import RestAccessor  # noqa: F401
from .plugins import Dependencies, Plugin, hookimpl, hookspec  # noqa: F401
from .rest import Rest, SingleDatasetRest  # noqa: F401

try:
    __version__ = get_distribution(__name__).version
except DistributionNotFound:  # noqa: F401; pragma: no cover
    # package is not installed
    pass
