import xarray as xr

from fastapi import APIRouter, Depends, Response
from xpublish.dependencies import get_dataset

from datashader import transfer_functions as tf
import datashader as ds
import morecantile


# From Morecantile, morecantile.tms.list()
WEB_CRS = {
    3857: "WebMercatorQuad",
    32631: "UTM31WGS84Quad",
    3978: "CanadianNAD83_LCC",
    5482: "LINZAntarticaMapTilegrid",
    4326: "WorldCRS84Quad",
    5041: "UPSAntarcticWGS84Quad",
    3035: "EuropeanETRS89_LAEAQuad",
    3395: "WorldMercatorWGS84Quad",
    2193: "NZTM2000",
}

# default
TMS = morecantile.tms.get("WebMercatorQuad")


class DataValidationError(KeyError):
    pass


class XYZRouter(APIRouter):
    def map_options(self, crs_epsg: int, datashader_settings: dict = {}) -> None:
        global TMS

        self.datashader_settings = datashader_settings

        if crs_epsg not in WEB_CRS.keys():
            raise DataValidationError(f"User input {crs_epsg} not supported")

        TMS = morecantile.tms.get(WEB_CRS[crs_epsg])


xyz_router = XYZRouter()


def _get_bounds(zoom, x, y):

    bbx = TMS.xy_bounds(morecantile.Tile(int(x), int(y), int(zoom)))

    return bbx.left, bbx.right, bbx.bottom, bbx.top


def _get_tiles(layer, dataset, zoom, x, y, datashader_settings):

    raster_param = datashader_settings.get("raster", {})
    shade_param = datashader_settings.get("shade", {"cmap": ["blue", "red"]})

    xleft, xright, ybottom, ytop = _get_bounds(zoom, x, y)

    frame = dataset[layer].sel(x=slice(xleft, xright), y=slice(ytop, ybottom))

    csv = ds.Canvas(plot_width=256, plot_height=256)

    agg = csv.raster(frame, **raster_param)

    img = tf.shade(agg, **shade_param)

    img_io = img.to_bytesio("PNG")

    img_io.seek(0)

    bytes = img_io.read()

    return bytes


def _validate_dataset(dataset):
    dims = dataset.dims
    if "x" not in dims or "y" not in dims:
        raise DataValidationError(
            f" Expected spatial dimension names 'x' and 'y', found: {dims}"
        )


@xyz_router.get("/tiles/{layer}/{z}/{x}/{y}")
async def tiles(layer, z, x, y, dataset: xr.Dataset = Depends(get_dataset)):

    _validate_dataset(dataset)

    datashader_settings = getattr(xyz_router, "datashader_settings")

    results = _get_tiles(layer, dataset, z, x, y, datashader_settings)

    return Response(content=results, media_type="image/png")
