from .base import base_router
from .common import common_router, dataset_collection_router
from .zarr import zarr_router

try:
    from .xyz import xyz_router
except ImportError:
    pass