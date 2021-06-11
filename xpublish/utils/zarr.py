import copy
import logging

import dask
import numpy as np
import xarray as xr
from numcodecs.compat import ensure_ndarray
from xarray.backends.zarr import (
    DIMENSION_KEY,
    encode_zarr_attr_value,
    encode_zarr_variable,
    extract_zarr_variable_encoding,
)
from zarr.meta import encode_fill_value
from zarr.storage import array_meta_key, attrs_key, default_compressor, group_meta_key
from zarr.util import normalize_shape

from .api import DATASET_ID_ATTR_KEY

dask_array_type = (dask.array.Array,)
zarr_format = 2
zarr_consolidated_format = 1
zarr_metadata_key = '.zmetadata'

logger = logging.getLogger('api')


def _extract_dataset_zattrs(dataset: xr.Dataset):
    """helper function to create zattrs dictionary from Dataset global attrs"""
    zattrs = {}
    for k, v in dataset.attrs.items():
        zattrs[k] = encode_zarr_attr_value(v)

    # remove xpublish internal attribute
    zattrs.pop(DATASET_ID_ATTR_KEY, None)

    return zattrs


def _extract_dataarray_zattrs(da):
    """helper function to extract zattrs dictionary from DataArray"""
    zattrs = {}
    for k, v in da.attrs.items():
        zattrs[k] = encode_zarr_attr_value(v)
    zattrs[DIMENSION_KEY] = list(da.dims)

    # We don't want `_FillValue` in `.zattrs`
    # It should go in `fill_value` section of `.zarray`
    _ = zattrs.pop('_FillValue', None)

    return zattrs


def _extract_fill_value(da, dtype):
    """helper function to extract fill value from DataArray."""
    fill_value = da.attrs.pop('_FillValue', None)
    return encode_fill_value(fill_value, dtype)


def _extract_zarray(da, encoding, dtype):
    """helper function to extract zarr array metadata."""
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


def create_zvariables(dataset):
    """Helper function to create a dictionary of zarr encoded variables."""
    zvariables = {}

    for key, da in dataset.variables.items():
        encoded_da = encode_zarr_variable(da, name=key)
        zvariables[key] = encoded_da

    return zvariables


def create_zmetadata(dataset):
    """Helper function to create a consolidated zmetadata dictionary."""

    zmeta = {'zarr_consolidated_format': zarr_consolidated_format, 'metadata': {}}
    zmeta['metadata'][group_meta_key] = {'zarr_format': zarr_format}
    zmeta['metadata'][attrs_key] = _extract_dataset_zattrs(dataset)

    for key, da in dataset.variables.items():
        encoded_da = encode_zarr_variable(da, name=key)
        encoding = extract_zarr_variable_encoding(da)
        zmeta['metadata'][f'{key}/{attrs_key}'] = _extract_dataarray_zattrs(encoded_da)
        zmeta['metadata'][f'{key}/{array_meta_key}'] = _extract_zarray(
            encoded_da, encoding, encoded_da.dtype
        )

    return zmeta


def jsonify_zmetadata(dataset: xr.Dataset, zmetadata: dict) -> dict:
    """Helper function to convert zmetadata dictionary to a json
    compatible dictionary.

    """
    zjson = copy.deepcopy(zmetadata)

    for key in list(dataset.variables):
        # convert compressor to dict
        compressor = zjson['metadata'][f'{key}/{array_meta_key}']['compressor']
        if compressor is not None:
            compressor_config = zjson['metadata'][f'{key}/{array_meta_key}'][
                'compressor'
            ].get_config()
            zjson['metadata'][f'{key}/{array_meta_key}']['compressor'] = compressor_config

    return zjson


def encode_chunk(chunk, filters=None, compressor=None):
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
    """Get one chunk of data from this DataArray (da).

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
