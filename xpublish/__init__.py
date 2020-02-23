from pkg_resources import DistributionNotFound, get_distribution

from .rest import RestAccessor  # noqa: F401

try:
    __version__ = get_distribution(__name__).version
except DistributionNotFound:  # noqa: F401
    # package is not installed
    pass
