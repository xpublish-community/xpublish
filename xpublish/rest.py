import copy
import logging

import numpy as np
import uvicorn
import xarray as xr
from fastapi import FastAPI
from numcodecs.compat import ensure_ndarray
from starlette.responses import HTMLResponse, Response
from xarray.backends.zarr import (
    _DIMENSION_KEY,
    _encode_zarr_attr_value,
    _extract_zarr_variable_encoding,
    encode_zarr_variable,
)
from xarray.core.pycompat import dask_array_type
from zarr.meta import encode_fill_value
from zarr.storage import array_meta_key, attrs_key, default_compressor, group_meta_key
from zarr.util import normalize_shape

zarr_format = 2
zarr_consolidated_format = 1
zarr_metadata_key = ".zmetadata"

logger = logging.getLogger("api")


@xr.register_dataset_accessor("rest")
class RestAccessor:
    """ REST API Accessor

    Parameters
    ----------
    xarray_obj : Dataset
        Dataset object to be served through the REST API.
    """

    def __init__(self, xarray_obj):

        self._obj = xarray_obj

        self._app = None
        self._zmetadata = None

        self._attributes = {}
        self._variables = {}
        self._encoding = {}

    def _get_zmetadata(self):
        """ helper method to create consolidated zmetadata dictionary """
        zmeta = {"zarr_consolidated_format": zarr_consolidated_format, "metadata": {}}
        zmeta["metadata"][group_meta_key] = {"zarr_format": zarr_format}
        zmeta["metadata"][attrs_key] = self._get_zattrs()

        for key, da in self._obj.variables.items():
            # encode variable
            encoded_da = encode_zarr_variable(da)
            self._variables[key] = encoded_da
            self._encoding[key] = _extract_zarr_variable_encoding(da)
            zmeta["metadata"][f"{key}/{attrs_key}"] = extract_zattrs(encoded_da)
            zmeta["metadata"][f"{key}/{array_meta_key}"] = extract_zarray(
                encoded_da, self._encoding.get(key, {}), da.encoding["dtype"]
            )

        return zmeta

    def _get_zattrs(self):
        """ helper method to create zattrs dictionary """
        zattrs = {}
        for k, v in self._obj.attrs.items():
            zattrs[k] = _encode_zarr_attr_value(v)
        return zattrs

    @property
    def zmetadata(self):
        """ Consolidated zmetadata dictionary (`dict`, read-only)."""
        if self._zmetadata is None:
            self._zmetadata = self._get_zmetadata()
        return self._zmetadata

    def zmetadata_json(self):
        """ JSON version of self.zmetadata """
        zjson = copy.deepcopy(self.zmetadata)
        for key in list(self._obj.variables):
            # convert compressor to dict
            compressor_config = zjson["metadata"][f"{key}/{array_meta_key}"][
                "compressor"
            ].get_config()
            zjson["metadata"][f"{key}/{array_meta_key}"]["compressor"] = compressor_config

        return zjson

    async def get_key(self, var, chunk):
        logger.debug("var is %s", var)
        logger.debug("chunk is %s", chunk)

        da = self._variables[var].data
        arr_meta = self.zmetadata["metadata"][f"{var}/{array_meta_key}"]

        data_chunk = get_data_chunk(da, chunk, out_shape=arr_meta["chunks"])

        echunk = _encode_chunk(
            data_chunk.tobytes(), filters=arr_meta["filters"], compressor=arr_meta["compressor"],
        )
        return Response(echunk, media_type="application/octet-stream")

    def init_app(
        self,
        debug=False,
        title='FastAPI',
        description='',
        version='0.1.0',
        openapi_url='/openapi.json',
        docs_url='/docs',
        openapi_prefix='',
        **kwargs,
    ):
        """ Initiate FastAPI Application.

        Parameters
        ----------
        debug : bool
            Boolean indicating if debug tracebacks for
            FastAPI application should be returned on errors.
        title : str
            API's title/name, in OpenAPI and the automatic API docs UIs.
        description : str
            API's description text, in OpenAPI and the automatic API docs UIs.
        version : str
            API's version, e.g. v2 or 2.5.0.
        openapi_url: str
            Set OpenAPI schema json url. Default at /openapi.json.
        docs_url : str
            Set Swagger UI API documentation URL. Set to ``None`` to disable.
        openapi_prefix : str
            Set root url of where application will be hosted.
        kwargs :
            Additional arguments to be passed to ``FastAPI``.
            See https://tinyurl.com/fastapi for complete list.
        """

        self._app = FastAPI(
            debug=debug,
            title=title,
            description=description,
            version=version,
            openapi_url=openapi_url,
            docs_url=docs_url,
            openapi_prefix=openapi_prefix,
            **kwargs,
        )

        @self._app.get(f"/{zarr_metadata_key}")
        def get_zmetadata():
            return self.zmetadata_json()

        @self._app.get("/keys")
        def list_keys():
            return list(self._obj.variables)

        @self._app.get("/")
        def repr():
            with xr.set_options(display_style="html"):
                return HTMLResponse(self._obj._repr_html_())

        @self._app.get("/info")
        def info():
            import io

            with io.StringIO() as buffer:
                self._obj.info(buf=buffer)
                info = buffer.getvalue()
            return info

        @self._app.get("/dict")
        def to_dict(data: bool = False):
            return self._obj.to_dict(data=data)

        @self._app.get("/{var}/{chunk}")
        async def get_key(var, chunk):
            result = await self.get_key(var, chunk)
            return result

        @self._app.get("/versions")
        def versions():
            import io

            with io.StringIO() as f:
                xr.show_versions(f)
                versions = f.getvalue()
            return versions

        return self._app

    @property
    def app(self):
        """ FastAPI app """
        if self._app is None:
            self.init_app()
        return self._app

    def serve(self, host="0.0.0.0", port=9000, log_level="debug", **kwargs):
        """ Serve this app via ``uvicorn.run``.

        Parameters
        ----------
        host : str
            Bind socket to this host.
        port : int
            Bind socket to this port.
        log_level : str
            App logging level, valid options are
            {'critical', 'error', 'warning', 'info', 'debug', 'trace'}.
        kwargs :
            Additional arguments to be passed to ``uvicorn.run``.

        Notes
        -----
        This method is blocking and does not return.
        """
        uvicorn.run(self.app, host=host, port=port, log_level=log_level, **kwargs)


def extract_zattrs(da):
    """ helper function to extract zattrs dictionary from DataArray """
    zattrs = {}
    for k, v in da.attrs.items():
        zattrs[k] = _encode_zarr_attr_value(v)
    zattrs[_DIMENSION_KEY] = list(da.dims)

    # We don't want `_FillValue` in `.zattrs`
    # It should go in `fill_value` section of `.zarray`
    _ = zattrs.pop("_FillValue", None)

    return zattrs


def _extract_fill_value(da, dtype):
    """ helper function to extract fill value from DataArray. """
    fill_value = da.attrs.pop("_FillValue", None)
    return encode_fill_value(fill_value, dtype)


def extract_zarray(da, encoding, dtype):
    """ helper function to extract zarr array metadata. """
    meta = {
        "compressor": encoding.get("compressor", da.encoding.get("compressor", default_compressor)),
        "filters": encoding.get("filters", da.encoding.get("filters", None)),
        "chunks": encoding.get("chunks", None),
        "dtype": dtype.str,
        "fill_value": _extract_fill_value(da, dtype),
        "order": "C",
        "shape": list(normalize_shape(da.shape)),
        "zarr_format": zarr_format,
    }
    if meta["chunks"] is None:
        if da.chunks is not None:
            meta["chunks"] = list([c[0] for c in da.chunks])
        else:
            meta["chunks"] = list(da.shape)

    return meta


def _encode_chunk(chunk, filters=None, compressor=None):
    """helper function largely copied from zarr.Array"""
    # apply filters
    if filters:
        for f in filters:
            chunk = f.encode(chunk)

    # check object encoding
    if ensure_ndarray(chunk).dtype == object:
        raise RuntimeError("cannot write object array without object codec")

    # compress
    if compressor:
        logger.debug(compressor)
        cdata = compressor.encode(chunk)
    else:
        cdata = chunk

    return cdata


def get_data_chunk(da, chunk_id, out_shape):
    """ Get one chunk of data from this DataArray (da).

    If this is an incomplete edge chunk, pad the returned array to match out_shape.
    """
    ikeys = tuple(map(int, chunk_id.split(".")))
    try:
        chunk_data = da.blocks[ikeys]
    except:
        chunk_data = np.asarray(da)

    logger.debug("checking chunk output size, %s == %s" % (chunk_data.shape, out_shape))

    if isinstance(chunk_data, dask_array_type):
        chunk_data = chunk_data.compute()

    # zarr expects full edge chunks, contents out of bounds for the array are undefined
    if chunk_data.shape != tuple(out_shape):
        new_chunk = np.empty_like(chunk_data, shape=out_shape)
        write_slice = tuple([slice(0, s) for s in chunk_data.shape])
        new_chunk[write_slice] = chunk_data
        return new_chunk
    else:
        return chunk_data
