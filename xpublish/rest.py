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
from zarr.storage import array_meta_key, attrs_key, default_compressor, group_meta_key
from zarr.util import normalize_shape

zarr_format = 2
zarr_consolidated_format = 1
zarr_metadata_key = '.zmetadata'

logger = logging.getLogger('api')


@xr.register_dataset_accessor('rest')
class RestAccessor:
    def __init__(self, xarray_obj, name=None):
        self._obj = xarray_obj

        self._name = name if name is not None else '<Dataset rest app>'

        self._app = None
        self._zmetadata = None

        self._attributes = {}
        self._variables = {}
        self._encoding = {}

    def _get_zmetadata(self):
        zmeta = {'zarr_consolidated_format': zarr_consolidated_format, 'metadata': {}}
        zmeta['metadata'][group_meta_key] = {'zarr_format': zarr_format}
        zmeta['metadata'][attrs_key] = self.get_zattrs()

        for key, da in self._obj.variables.items():
            # encode variable
            self._variables[key] = encode_zarr_variable(da)
            self._encoding[key] = _extract_zarr_variable_encoding(da)

            zmeta['metadata'][f'{key}/{attrs_key}'] = extract_zattrs(da)
            zmeta['metadata'][f'{key}/{array_meta_key}'] = extract_zarray(
                da, self._encoding.get(key, {})
            )
        return zmeta

    def get_zattrs(self):
        zattrs = {}
        for k, v in self._obj.attrs.items():
            zattrs[k] = _encode_zarr_attr_value(v)
        return zattrs

    @property
    def zmetadata(self):
        if self._zmetadata is None:
            self._zmetadata = self._get_zmetadata()
        return self._zmetadata

    def zmetadata_json(self):
        zjson = self.zmetadata.copy()
        for key in list(self._obj.variables):
            # convert compressor to dict
            zjson['metadata'][f'{key}/{array_meta_key}']['compressor'] = zjson['metadata'][
                f'{key}/{array_meta_key}'
            ]['compressor'].get_config()
        return zjson

    @property
    def app(self):
        if self._app is None:

            self._app = FastAPI()

            @self._app.get(f'/{zarr_metadata_key}')
            def get_zmetadata():
                return self.zmetadata_json()

            @self._app.get('/keys')
            def list_keys():
                return list(self._obj.variables)

            @self._app.get('/')
            def repr():
                with xr.set_options(display_style='html'):
                    return HTMLResponse(self._obj._repr_html_())

            @self._app.get('/info')
            def info():
                import io

                with io.StringIO() as buffer:
                    self._obj.info(buf=buffer)
                    info = buffer.getvalue()
                return info

            @self._app.get('/dict')
            def to_dict(data: bool = False):
                return self._obj.to_dict(data=data)

            @self._app.get('/{var}/{chunk}')
            def get_key(var, chunk):
                logger.debug('var is %s', var)
                logger.debug('chunk is %s', chunk)

                da = self._variables[var].data
                arr_meta = self.zmetadata['metadata'][f'{var}/{array_meta_key}']

                data_chunk = get_data_chunk(da, chunk, out_shape=arr_meta['chunks'])

                echunk = _encode_chunk(
                    data_chunk.tobytes(),
                    filters=arr_meta['filters'],
                    compressor=arr_meta['compressor'],
                )
                return Response(echunk, media_type='application/octet-stream')

        return self._app

    def serve(self, host='0.0.0.0', port=9000, log_level='debug', **kwargs):
        uvicorn.run(self.app, host=host, port=port, log_level=log_level, **kwargs)


def extract_zattrs(da):
    zattrs = {}
    for k, v in da.attrs.items():
        zattrs[k] = _encode_zarr_attr_value(v)
    zattrs[_DIMENSION_KEY] = list(da.dims)

    return zattrs


def extract_zarray(da, encoding):
    # TODO: do a better job of validating some of these
    meta = {
        'compressor': encoding.get('compressor', da.encoding.get('compressor', default_compressor)),
        'filters': encoding.get('filters', da.encoding.get('filters', None)),
        'chunks': encoding.get('chunks', None),
        'dtype': da.dtype.str,
        'fill_value': None,  # TODO: figure out how to handle NaNs
        'order': 'C',
        'shape': list(normalize_shape(da.shape)),
        'zarr_format': zarr_format,
    }
    if meta['chunks'] is None:
        if da.chunks is not None:
            meta['chunks'] = list([c[0] for c in da.chunks],)
        else:
            meta['chunks'] = list(da.shape)

    return meta


def slice_axis(key, chunk_size):
    return slice(key * chunk_size, (key + 1) * chunk_size)


def get_indexers(key, chunks):
    ikeys = key.split('.')
    return tuple(slice_axis(int(i), c) for i, c in zip(ikeys, chunks))


def _encode_chunk(chunk, filters=None, compressor=None):
    """helper function largely copied from zarr.Array"""
    # apply filters
    if filters:
        for f in filters:
            chunk = f.encode(chunk)

    # check object encoding
    if ensure_ndarray(chunk).dtype == object:
        raise RuntimeError('cannot write object array without object codec')

    # compress
    if compressor:
        logger.debug(compressor)
        cdata = compressor.encode(chunk)
    else:
        cdata = chunk

    return cdata


def get_data_chunk(da, chunk_id, out_shape):
    ikeys = tuple(map(int, chunk_id.split('.')))
    try:
        chunk_data = da.blocks[ikeys]
    except:
        chunk_data = np.asarray(da)

    logger.debug('checking chunk output size, %s == %s' % (chunk_data.shape, out_shape))

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
