from pkg_resources import DistributionNotFound, get_distribution

from .accessor import RestAccessor  # noqa: F401
from .plugin import Plugin, Router  # noqa: F401
from .rest import Rest  # noqa: F401

try:
    __version__ = get_distribution(__name__).version
except DistributionNotFound:  # noqa: F401; pragma: no cover
    # package is not installed
    pass
