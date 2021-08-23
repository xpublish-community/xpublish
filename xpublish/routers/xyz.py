import xarray as xr
import cachey
from fastapi import APIRouter, Depends, Response
from typing import Optional

from xpublish.utils.cache import CostTimer
from xpublish.utils.api import DATASET_ID_ATTR_KEY
from xpublish.dependencies import get_dataset, get_cache
from xpublish.utils.ows import (
    get_image_datashader,
    get_bounds,
    LayerOptionsMixin,
    get_tiles,
)


class XYZRouter(APIRouter, LayerOptionsMixin):
    pass


xyz_router = XYZRouter()



@xyz_router.get("/tiles/{var}/{z}/{x}/{y}")
@xyz_router.get("/tiles/{var}/{z}/{x}/{y}.{format}")
async def tiles(var, 
    z, 
    x, 
    y, 
    format: str = "PNG", 
    time: Optional[str] = None, 
    cache: cachey.Cache = Depends(get_cache), 
    dataset: xr.Dataset = Depends(get_dataset)
):

    # color mapping settings
    datashader_settings = getattr(xyz_router, "datashader_settings")

    TMS = getattr(xyz_router, "TMS")

    xleft, xright, ybottom, ytop = get_bounds(TMS, z, x, y)

    cache_key = dataset.attrs.get(DATASET_ID_ATTR_KEY, '') + '/' + f'/tiles/{var}/{z}/{x}/{y}.{format}?{time}'
    response = cache.get(cache_key) 

    if response is None:
        with CostTimer() as ct:

            tile = get_tiles(var, dataset, time, xleft, xright, ybottom, ytop)

            byte_image = get_image_datashader(tile, datashader_settings, format)

            response = Response(content=byte_image, media_type=f'image/{format}')

        cache.put(cache_key, response, ct.time, len(byte_image))

    return response
