import xarray as xr
import cachey
from fastapi import APIRouter, Depends, Response, Query, Path
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


def query_builder(time, xleft, xright, ybottom, ytop, xlab, ylab):
    query = {}
    query.update({xlab: slice(xleft, xright), ylab: slice(ytop, ybottom)})
    if time:
        query["time"] = time
    return query


@xyz_router.get("/tiles/{var}/{z}/{x}/{y}")
@xyz_router.get("/tiles/{var}/{z}/{x}/{y}.{format}")
async def tiles(
    var: str = Path(
        ..., description="Dataset's variable. It defines the map's data layer"
    ),
    z: int = Path(..., description="Tiles' zoom level"),
    x: int = Path(..., description="Tiles' column"),
    y: int = Path(..., description="Tiles' row"),
    format: str = Query("PNG", description="Image format. Default to PNG"),
    time: str = Query(
        None,
        description="Filter by time in time-varying datasets. String time format should match dataset's time format",
    ),
    xlab: str = Query("x", description="Dataset x coordinate label"),
    ylab: str = Query("y", description="Dataset y coordinate label"),
    cache: cachey.Cache = Depends(get_cache),
    dataset: xr.Dataset = Depends(get_dataset),
):

    # color mapping settings
    datashader_settings = getattr(xyz_router, "datashader_settings")

    TMS = getattr(xyz_router, "TMS")

    xleft, xright, ybottom, ytop = get_bounds(TMS, z, x, y)

    query = query_builder(time, xleft, xright, ybottom, ytop, xlab, ylab)

    cache_key = (
        dataset.attrs.get(DATASET_ID_ATTR_KEY, "")
        + "/"
        + f"/tiles/{var}/{z}/{x}/{y}.{format}?{time}"
    )
    response = cache.get(cache_key)

    if response is None:
        with CostTimer() as ct:

            tile = get_tiles(var, dataset, query)

            byte_image = get_image_datashader(tile, datashader_settings, format)

            response = Response(content=byte_image, media_type=f"image/{format}")

        cache.put(cache_key, response, ct.time, len(byte_image))

    return response
