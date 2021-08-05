import xarray as xr
from fastapi import APIRouter, Depends, Response

from xpublish.dependencies import get_dataset
from xpublish.utils.ows import (
    get_image_datashader,
    get_bounds,
    LayerOptionsMixin,
    get_tiles,
)


class XYZRouter(APIRouter, LayerOptionsMixin):
    pass


xyz_router = XYZRouter()


@xyz_router.get("/tiles/{layer}/{time}/{z}/{x}/{y}")
@xyz_router.get("/tiles/{layer}/{z}/{x}/{y}")
async def tiles(layer, z, x, y, time=None, dataset: xr.Dataset = Depends(get_dataset)):

    # color mapping settings
    datashader_settings = getattr(xyz_router, "datashader_settings")
    TMS = getattr(xyz_router, "TMS")

    xleft, xright, ybottom, ytop = get_bounds(TMS, z, x, y)

    tile = get_tiles(layer, dataset, time, xleft, xright, ybottom, ytop)

    image = get_image_datashader(tile, datashader_settings)

    return Response(content=image, media_type="image/png")
