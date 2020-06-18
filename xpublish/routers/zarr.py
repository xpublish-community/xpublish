import copy
import json
import logging

import cachey
import dask
import numpy as np
import xarray as xr
from fastapi import APIRouter, Depends, HTTPException
from numcodecs.compat import ensure_ndarray
from starlette.responses import Response
from xarray.backends.zarr import encode_zarr_variable
from zarr.meta import encode_fill_value
from zarr.storage import array_meta_key, attrs_key, default_compressor, group_meta_key
from zarr.util import normalize_shape

from ..utils import CostTimer
from .base import get_cache, get_dataset

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


def _extract_dataset_zattrs(dataset: xr.Dataset):
    """ helper function to create zattrs dictionary from Dataset global attrs """
    zattrs = {}
    for k, v in dataset.attrs.items():
        zattrs[k] = encode_zarr_attr_value(v)
    return zattrs


def _extract_dataarray_zattrs(da):
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


def _extract_zarray(da, encoding, dtype):
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


def _get_data_chunk(da, chunk_id, out_shape):
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


def _get_zvariables(
    dataset: xr.Dataset = Depends(get_dataset), cache: cachey.Cache = Depends(get_cache)
):
    """Helper function to create (or get from cache) a dictionary of zarr encoded
    variables.

    """
    cache_key = "zvariables"
    zvariables = cache.get(cache_key)

    if zvariables is None:
        zvariables = {}

        for key, da in dataset.variables.items():
            encoded_da = encode_zarr_variable(da)
            zvariables[key] = encoded_da

        # we want to permanently cache this: set high cost value
        cache.put(cache_key, zvariables, 99999)

    return zvariables


def _get_zmetadata(
    dataset: xr.Dataset = Depends(get_dataset),
    cache: cachey.Cache = Depends(get_cache),
    zvariables: dict = Depends(_get_zvariables),
):
    """Helper function to create (or get from cache) a consolidated zmetadata
    dictionary.

    """
    zmeta = cache.get(zarr_metadata_key)

    if zmeta is None:
        zmeta = {'zarr_consolidated_format': zarr_consolidated_format, 'metadata': {}}
        zmeta['metadata'][group_meta_key] = {'zarr_format': zarr_format}
        zmeta['metadata'][attrs_key] = _extract_dataset_zattrs(dataset)

        for key, da in dataset.variables.items():
            encoded_da = zvariables[key]
            encoding = extract_zarr_variable_encoding(da)
            zmeta['metadata'][f'{key}/{attrs_key}'] = _extract_dataarray_zattrs(encoded_da)
            zmeta['metadata'][f'{key}/{array_meta_key}'] = _extract_zarray(
                encoded_da, encoding, encoded_da.dtype
            )

        # we want to permanently cache this: set high cost value
        cache.put(zarr_metadata_key, zmeta, 99999)

    return zmeta


zarr_router = APIRouter()


@zarr_router.get(f'/{zarr_metadata_key}')
def get_zmetadata(
    dataset: xr.Dataset = Depends(get_dataset), zmetadata: dict = Depends(_get_zmetadata)
):
    # JSON version of zmetadata
    zjson = copy.deepcopy(zmetadata)
    for key in list(dataset.variables):
        # convert compressor to dict
        compressor = zjson['metadata'][f'{key}/{array_meta_key}']['compressor']
        if compressor is not None:
            compressor_config = zjson['metadata'][f'{key}/{array_meta_key}'][
                'compressor'
            ].get_config()
            zjson['metadata'][f'{key}/{array_meta_key}']['compressor'] = compressor_config

    return Response(json.dumps(zjson).encode('ascii'), media_type='application/json')


@zarr_router.get(f'/{group_meta_key}')
def get_zgroup(zmetadata: dict = Depends(_get_zmetadata)):

    return zmetadata['metadata'][group_meta_key]


@zarr_router.get(f'/{attrs_key}')
def get_zattrs(zmetadata: dict = Depends(_get_zmetadata)):

    return zmetadata['metadata'][attrs_key]


@zarr_router.get('/info')
def info(
    dataset: xr.Dataset = Depends(get_dataset),
    zvariables: dict = Depends(_get_zvariables),
    zmetadata: dict = Depends(_get_zmetadata),
):
    """Dataset schema (close to the NCO-JSON schema)."""

    info = {}
    info['dimensions'] = dict(dataset.dims.items())
    info['variables'] = {}

    meta = zmetadata['metadata']

    for name, var in zvariables.items():
        attrs = meta[f'{name}/{attrs_key}']
        attrs.pop('_ARRAY_DIMENSIONS')
        info['variables'][name] = {
            'type': var.data.dtype.name,
            'dimensions': list(var.dims),
            'attributes': attrs,
        }

    info['global_attributes'] = meta[attrs_key]

    return info


@zarr_router.get('/{var}/{chunk}')
def get_variable_chunk(
    var: str,
    chunk: str,
    cache: cachey.Cache = Depends(get_cache),
    zvariables: dict = Depends(_get_zvariables),
    zmetadata: dict = Depends(_get_zmetadata),
):
    """Get a zarr array chunk.

    This will return cached responses when available.

    """
    # First check that this request wasn't for variable metadata
    if array_meta_key in chunk:
        return zmetadata['metadata'][f'{var}/{array_meta_key}']
    elif attrs_key in chunk:
        return zmetadata['metadata'][f'{var}/{attrs_key}']
    elif group_meta_key in chunk:
        raise HTTPException(status_code=404, detail='No subgroups')
    else:
        logger.debug('var is %s', var)
        logger.debug('chunk is %s', chunk)

        cache_key = f'{var}/{chunk}'
        response = cache.get(cache_key)

        if response is None:
            with CostTimer() as ct:
                arr_meta = zmetadata['metadata'][f'{var}/{array_meta_key}']
                da = zvariables[var].data

                data_chunk = _get_data_chunk(da, chunk, out_shape=arr_meta['chunks'])

                echunk = _encode_chunk(
                    data_chunk.tobytes(),
                    filters=arr_meta['filters'],
                    compressor=arr_meta['compressor'],
                )

                response = Response(echunk, media_type='application/octet-stream')

            cache.put(cache_key, response, ct.time, len(echunk))

        return response
