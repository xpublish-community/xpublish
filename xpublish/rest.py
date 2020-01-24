import dask
import numpy as np
import xarray as xr
from flask import Flask, jsonify
from numcodecs.compat import ensure_ndarray
from xarray.backends.zarr import _DIMENSION_KEY, _encode_zarr_attr_value
from xarray.core.pycompat import dask_array_type
from zarr.storage import array_meta_key, attrs_key, group_meta_key
from zarr.util import json_dumps, normalize_shape

zarr_format = 2
zarr_consolidated_format = 1
zarr_metadata_key = ".zmetadata"


@xr.register_dataset_accessor("rest")
class RestAccessor:
    def __init__(self, xarray_obj, name=None, encoding=None):
        self._obj = xarray_obj

        self._name = name if name is not None else "<Dataset rest app>"
        self._encoding = encoding if encoding is not None else {}

        self._metadata = self.get_zmetadata()
        self.make_app()

    def get_zmetadata(self):
        zmeta = {"zarr_consolidated_format": zarr_consolidated_format, "metadata": {}}

        zmeta["metadata"][attrs_key] = self.get_zattrs()
        zmeta["metadata"][group_meta_key] = self.get_zgroup()

        for key, da in self._obj.variables.items():
            zmeta["metadata"][f"{key}/{attrs_key}"] = extract_zattrs(da)
            zmeta["metadata"][f"{key}/{array_meta_key}"] = extract_zarray(
                da, self._encoding.get(key, {})
            )
        return zmeta

    def get_zgroup(self):
        return {"zarr_format": zarr_format}

    def get_zattrs(self):
        zattrs = {}
        for k, v in self._obj.attrs.items():
            zattrs[k] = _encode_zarr_attr_value(v)
        return zattrs

    def make_app(self):

        self._app = Flask(self._name)

        @self._app.route(f"/{group_meta_key}", methods=["GET"])
        def get_zgroup():
            return json_dumps(self.get_zgroup())

        @self._app.route(f"/{attrs_key}", methods=["GET"])
        def get_zattrs():
            return json_dumps(self.get_zattrs())

        @self._app.route(f"/{zarr_metadata_key}", methods=["GET"])
        def get_zmetadata():
            return json_dumps(self._metadata)

        @self._app.route("/keys", methods=["GET"])
        def list_keys():
            return json_dumps(list(self._obj.variables))

        @self._app.route("/<var>/<chunk>", methods=["GET"])
        def get_key(var, chunk):
            da = self._obj[var]
            arr_meta = self._metadata["metadata"][f"{var}/{array_meta_key}"]

            index = get_indexers(chunk, arr_meta["chunks"])

            data_chunk = da.data[index]

            if isinstance(data_chunk, dask_array_type):
                data_chunk = data_chunk.compute()

            # Things we need to test here:
            # 1. Using filters/compressors
            # 2. Unpacking filters/compressors from dict metadata
            # 3. Handling edge chunks (is that done here on read or by the reader client)
            # 4. Is tobytes on the numpy array the right thing to do?
            echunk = _encode_chunk(
                data_chunk.tobytes(),
                filters=arr_meta["filters"],
                compressor=arr_meta["compressor"],
            )
            return echunk

    def serve(self):
        # app.run(debug=True)
        from werkzeug.serving import run_simple

        run_simple("localhost", 9000, self._app)


def extract_zattrs(da):
    zattrs = {}
    for k, v in da.attrs.items():
        zattrs[k] = _encode_zarr_attr_value(v)
    zattrs[_DIMENSION_KEY] = list(da.dims)
    return zattrs


def extract_zarray(da, encoding):
    # TODO: do a better job of validating some of these
    meta = {
        "compressor": encoding.get("compressor", da.encoding.get("compressor", None)),
        "filters": encoding.get("filters", da.encoding.get("filters", None)),
        "chunks": encoding.get("chunks", None),
        "dtype": da.dtype.str,
        "fill_value": None,  # TODO: figure out how to handle NaNs
        "order": "C",
        "shape": normalize_shape(da.shape),
        "zarr_format": zarr_format,
    }
    if meta["chunks"] is None:
        if da.chunks is not None:
            meta["chunks"] = list([c[0] for c in da.chunks],)
        else:
            meta["chunks"] = list(da.shape)

    return meta


def slice_axis(key, chunk_size):
    return slice(key * chunk_size, (key + 1) * chunk_size)


def get_indexers(key, chunks):
    ikeys = key.split(".")
    return tuple(slice_axis(int(i), c) for i, c in zip(ikeys, chunks))


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
        cdata = compressor.encode(chunk)
    else:
        cdata = chunk

    return cdata
