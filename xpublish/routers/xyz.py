import xarray as xr

from fastapi import APIRouter, Depends, Response
from xpublish.dependencies import get_dataset


from datashader import transfer_functions as tf
import pandas as pd
import datashader as ds
import morecantile


MERCANTILE_CRS = {
    3857: "WebMercatorQuad",
    32631: "UTM31WGS84Quad",
    3978: "CanadianNAD83_LCC",
    5482: "LINZAntarticaMapTilegrid",
    4326: "WorldCRS84Quad",
    5041: "UPSAntarcticWGS84Quad",
    3035: "EuropeanETRS89_LAEAQuad",
    3395: "WorldMercatorWGS84Quad",
    2193: "NZTM2000",
    5041: "UPSArcticWGS84Quad",
}


class XYZ_Router(APIRouter):
    def __call__(self, epsg: int, palette, kwargs_datashader={}):
        global tms
        global col
        self.kwargs_datashader = kwargs_datashader
        if epsg not in MERCANTILE_CRS.keys():
            raise NotImplementedError

        col = palette
        tms = morecantile.tms.get(MERCANTILE_CRS[epsg])

        return self


xyz_router = XYZ_Router()


def get_bounds(zoom, x, y):
    try:
        latlon = tms.xy_bounds(morecantile.Tile(int(x), int(y), int(zoom)))
    except:
        tms = morecantile.tms.get("WebMercatorQuad")
        latlon = tms.xy_bounds(morecantile.Tile(int(x), int(y), int(zoom)))

    return latlon


# get tiles
def gettiles(layer, dataset, zoom, x, y, kwargs_datashader):
    """
    default spatial dimensions are x and y
    """

    plot_type = kwargs_datashader["plot_type"]

    latlon = get_bounds(zoom, x, y)

    xleft, xright, yleft, yright = latlon.left, latlon.right, latlon.bottom, latlon.top
    csv = ds.Canvas(
        plot_width=256,
        plot_height=256,
        x_range=(min(xleft, xright), max(xleft, xright)),
        y_range=(min(yleft, yright), max(yleft, yright)),
    )

    if plot_type == "point":

        dataset = dataset[layer].to_dataframe().reset_index()[["x", "y", layer]]

        condition = '(x >= {xleft}) & (x <= {xright}) & (y >= {yleft}) & (y <= {yright})'.format(
            xleft=xleft, yleft=yleft, xright=xright, yright=yright)

        frame = dataset.query(condition)

        frame = frame.dropna(axis=0)

        frame["groups"] = pd.cut(frame[layer], range(0, 100, 5), right=False)

        agg = csv.points(frame, 'x', 'y', agg=ds.count_cat("groups"))

    else:
        frame = dataset[layer].sel(
            x=slice(latlon.left, latlon.right), y=slice(latlon.top, latlon.bottom)
        )


        agg = csv.raster(frame, upsample_method="nearest")

    img = tf.shade(agg, cmap=col, how="log")

    img_io = img.to_bytesio("PNG")

    img_io.seek(0)

    bytes = img_io.read()

    return bytes


class InputDataError(KeyError):
    pass


def validate_dataset(dataset):
    dims = dataset.dims
    if not ("x" in dims or "y" in dims):
        raise InputDataError


@xyz_router.get("/tiles/{layer}/{z}/{x}/{y}")
async def tiles( layer, z, x, y, dataset: xr.Dataset = Depends(get_dataset)):

    validate_dataset(dataset)

    kwargs_datashader = getattr(xyz_router, "kwargs_datashader")

    results = gettiles(layer, dataset, z, x, y, kwargs_datashader)

    return Response(content=results, media_type="image/png")
