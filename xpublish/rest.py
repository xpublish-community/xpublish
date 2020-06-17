import copy
import importlib
import json
import logging
import sys
import time

import dask
import numpy as np
import uvicorn
import xarray as xr
from cachey import Cache
from fastapi import FastAPI, HTTPException, Request
from numcodecs.compat import ensure_ndarray
from starlette.responses import Response
from xarray.backends.zarr import encode_zarr_variable
from zarr.meta import encode_fill_value
from zarr.storage import array_meta_key, attrs_key, default_compressor, group_meta_key
from zarr.util import normalize_shape

from .info import get_sys_info, netcdf_and_hdf5_versions

try:
    from xarray.backends.zarr import DIMENSION_KEY
    from xarray.backends.zarr import encode_zarr_attr_value
    from xarray.backends.zarr import extract_zarr_variable_encoding
except ImportError:
    # xarray <= 0.16.1
    from xarray.backends.zarr import _DIMENSION_KEY as DIMENSION_KEY
    from xarray.backends.zarr import _encode_zarr_attr_value as encode_zarr_attr_value
    from xarray.backends.zarr import (
        _extract_zarr_variable_encoding as extract_zarr_variable_encoding,
    )

dask_array_type = (dask.array.Array,)
zarr_format = 2
zarr_consolidated_format = 1
zarr_metadata_key = '.zmetadata'

logger = logging.getLogger('api')


@xr.register_dataset_accessor('rest')
class RestAccessor:
    """ REST API Accessor

    Parameters
    ----------
    xarray_obj : Dataset
        Dataset object to be served through the REST API.

    Notes
    -----
    When using this as an accessor on an Xarray.Dataset, options are set via
    the ``RestAccessor.__call__()`` method.
    """

    def __init__(self, xarray_obj):

        self._obj = xarray_obj

        self._app = None
        self._zmetadata = None

        self._attributes = {}
        self._variables = {}
        self._encoding = {}
        self._cache_kws = {'available_bytes': 1e6}
        self._app_kws = {}
        self._cache = None
        self._initialized = False

    def __call__(self, cache_kws=None, app_kws=None):
        """
        Initialize this RestAccessor by setting optional configuration values

        Parameters
        ----------
        cache_kws : dict
            Dictionary of keyword arguments to be passed to ``cachey.Cache()``
        app_kws : dict
            Dictionary of keyword arguments to be passed to
            ``fastapi.FastAPI()``

        Notes
        -----
        This method can only be invoked once.
        """
        if self._initialized:
            raise RuntimeError('This accessor has already been initialized')
        self._initialized = True

        # update kwargs
        if cache_kws is not None:
            self._cache_kws.update(cache_kws)
        if app_kws is not None:
            self._app_kws.update(app_kws)
        return self

    @property
    def cache(self):
        """ Cache Property """
        if self._cache is None:
            self._cache = Cache(**self._cache_kws)
        return self._cache

    def _get_zmetadata(self):
        """ helper method to create consolidated zmetadata dictionary """
        zmeta = {'zarr_consolidated_format': zarr_consolidated_format, 'metadata': {}}
        zmeta['metadata'][group_meta_key] = {'zarr_format': zarr_format}
        zmeta['metadata'][attrs_key] = self._get_zattrs()

        for key, da in self._obj.variables.items():
            # encode variable
            encoded_da = encode_zarr_variable(da)
            self._variables[key] = encoded_da
            self._encoding[key] = extract_zarr_variable_encoding(da)
            zmeta['metadata'][f'{key}/{attrs_key}'] = _extract_zattrs(encoded_da)
            zmeta['metadata'][f'{key}/{array_meta_key}'] = extract_zarray(
                encoded_da, self._encoding[key], encoded_da.dtype
            )

        return zmeta

    def _get_zattrs(self):
        """ helper method to create zattrs dictionary """
        zattrs = {}
        for k, v in self._obj.attrs.items():
            zattrs[k] = encode_zarr_attr_value(v)
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
            compressor = zjson['metadata'][f'{key}/{array_meta_key}']['compressor']
            if compressor is not None:
                compressor_config = zjson['metadata'][f'{key}/{array_meta_key}'][
                    'compressor'
                ].get_config()
                zjson['metadata'][f'{key}/{array_meta_key}']['compressor'] = compressor_config

        return zjson

    def _get_key(self, var, chunk):
        """ Retrieve a zarr chunk

        Note that this method will return cached responses when available
        """
        cache_key = f'{var}/{chunk}'
        logger.debug('var is %s', var)
        logger.debug('chunk is %s', chunk)

        response = self.cache.get(cache_key)

        if response is None:
            with CostTimer() as ct:
                arr_meta = self.zmetadata['metadata'][f'{var}/{array_meta_key}']
                da = self._variables[var].data

                data_chunk = get_data_chunk(da, chunk, out_shape=arr_meta['chunks'])

                echunk = _encode_chunk(
                    data_chunk.tobytes(),
                    filters=arr_meta['filters'],
                    compressor=arr_meta['compressor'],
                )
                response = Response(echunk, media_type='application/octet-stream')
            self.cache.put(cache_key, response, ct.time, len(echunk))

        return response

    def _versions(self):
        versions = dict(get_sys_info() + netcdf_and_hdf5_versions())
        modules = [
            'xarray',
            'zarr',
            'numcodecs',
            'fastapi',
            'starlette',
            'pandas',
            'numpy',
            'dask',
            'distributed',
            'uvicorn',
        ]
        for modname in modules:
            try:
                if modname in sys.modules:
                    mod = sys.modules[modname]
                else:
                    mod = importlib.import_module(modname)
                versions[modname] = getattr(mod, '__version__', None)
            except ImportError:
                pass
        return versions

    def _info(self):
        """
        Return a dictionary representing dataset schema

        Currently close to the NCO-JSON schema
        """
        info = {}
        info['dimensions'] = dict(self._obj.dims.items())
        info['variables'] = {}

        meta = self.zmetadata['metadata']
        for name, var in self._variables.items():
            attrs = meta[f'{name}/{attrs_key}']
            attrs.pop('_ARRAY_DIMENSIONS')
            info['variables'][name] = {
                'type': var.data.dtype.name,
                'dimensions': list(var.dims),
                'attributes': attrs,
            }
        info['global_attributes'] = meta[attrs_key]
        return info

    def _init_app(self):
        """ Initiate FastAPI Application.
        """

        self._app = FastAPI(**self._app_kws)

        @self._app.get(f'/{zarr_metadata_key}')
        def get_zmetadata():
            return Response(
                json.dumps(self.zmetadata_json()).encode('ascii'), media_type='application/json'
            )

        @self._app.get(f'/{group_meta_key}')
        def get_zgroup():
            return self.zmetadata['metadata'][group_meta_key]

        @self._app.get(f'/{attrs_key}')
        def get_zattrs():
            return self.zmetadata['metadata'][attrs_key]

        @self._app.get('/keys')
        def list_keys():
            return list(self._obj.variables)

        @self._app.get('/')
        def repr(request: Request):
            with xr.set_options(display_style='html'):
                return self._obj._repr_html_()

        @self._app.get('/info')
        def info():
            return self._info()

        @self._app.get('/dict')
        def to_dict():
            return self._obj.to_dict(data=False)

        @self._app.get('/{var}/{chunk}')
        def get_key(var: str, chunk: str):
            # First check that this request wasn't for variable metadata
            if array_meta_key in chunk:
                return self.zmetadata['metadata'][f'{var}/{array_meta_key}']
            elif attrs_key in chunk:
                return self.zmetadata['metadata'][f'{var}/{attrs_key}']
            elif group_meta_key in chunk:
                raise HTTPException(status_code=404, detail='No subgroups')
            else:
                return self._get_key(var, chunk)

        @self._app.get('/versions')
        def versions():
            return self._versions()

        return self._app

    @property
    def app(self):
        """ FastAPI app """
        if self._app is None:
            self._app = self._init_app()
        return self._app

    def serve(self, host='0.0.0.0', port=9000, log_level='debug', **kwargs):
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


def _extract_zattrs(da):
    """ helper function to extract zattrs dictionary from DataArray """
    zattrs = {}
    for k, v in da.attrs.items():
        zattrs[k] = encode_zarr_attr_value(v)
    zattrs[DIMENSION_KEY] = list(da.dims)

    # We don't want `_FillValue` in `.zattrs`
    # It should go in `fill_value` section of `.zarray`
    _ = zattrs.pop('_FillValue', None)

    return zattrs


def _extract_fill_value(da, dtype):
    """ helper function to extract fill value from DataArray. """
    fill_value = da.attrs.pop('_FillValue', None)
    return encode_fill_value(fill_value, dtype)


def extract_zarray(da, encoding, dtype):
    """ helper function to extract zarr array metadata. """
    meta = {
        'compressor': encoding.get('compressor', da.encoding.get('compressor', default_compressor)),
        'filters': encoding.get('filters', da.encoding.get('filters', None)),
        'chunks': encoding.get('chunks', None),
        'dtype': dtype.str,
        'fill_value': _extract_fill_value(da, dtype),
        'order': 'C',
        'shape': list(normalize_shape(da.shape)),
        'zarr_format': zarr_format,
    }

    if meta['chunks'] is None:
        meta['chunks'] = da.shape

    # validate chunks
    if isinstance(da.data, dask_array_type):
        var_chunks = tuple([c[0] for c in da.data.chunks])
    else:
        var_chunks = da.shape
    if not var_chunks == tuple(meta['chunks']):
        raise ValueError('Encoding chunks do not match inferred chunks')

    meta['chunks'] = list(meta['chunks'])  # return chunks as a list

    return meta


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
        cdata = compressor.encode(chunk)
    else:
        cdata = chunk

    return cdata


def get_data_chunk(da, chunk_id, out_shape):
    """ Get one chunk of data from this DataArray (da).

    If this is an incomplete edge chunk, pad the returned array to match out_shape.
    """
    ikeys = tuple(map(int, chunk_id.split('.')))
    if isinstance(da, dask_array_type):
        chunk_data = da.blocks[ikeys]
    else:
        if ikeys != ((0,) * da.ndim):
            raise ValueError(
                'Invalid chunk_id for numpy array: %s. Should have been: %s'
                % (chunk_id, ((0,) * da.ndim))
            )
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


class CostTimer:
    """ Context manager to measure wall time """

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args):
        end = time.perf_counter()
        self.time = end - self._start
