import copy
import logging
from typing import (
    Any,
    Dict,
    Optional,
)

import dask.array
import numpy as np
import numpy.typing as npt
import xarray as xr
from numcodecs.abc import Codec
from numcodecs.compat import ensure_ndarray
from xarray.backends.zarr import (
    DIMENSION_KEY,
    encode_zarr_attr_value,
    encode_zarr_variable,
    extract_zarr_variable_encoding,
)
from zarr.meta import encode_fill_value
from zarr.storage import (
    array_meta_key,
    attrs_key,
    default_compressor,
    group_meta_key,
)
from zarr.util import normalize_shape

from .api import DATASET_ID_ATTR_KEY

DaskArrayType = (dask.array.Array,)
ZARR_FORMAT = 2
ZARR_CONSOLIDATED_FORMAT = 1
ZARR_METADATA_KEY = '.zmetadata'

logger = logging.getLogger('api')


def _extract_dataset_zattrs(dataset: xr.Dataset) -> dict:
    """Helper function to create zattrs dictionary from Dataset global attrs.

    Args:
        dataset: The Dataset to extract zattrs from.

    Returns:
        A dictionary of zattrs.
    """
    zattrs = {}
    for k, v in dataset.attrs.items():
        zattrs[k] = encode_zarr_attr_value(v)

    # remove xpublish internal attribute
    zattrs.pop(DATASET_ID_ATTR_KEY, None)

    return zattrs


def _extract_dataarray_zattrs(da: xr.DataArray) -> dict:
    """Helper function to extract zattrs dictionary from DataArray.

    Args:
        da: The DataArray to extract zattrs from.

    Returns:
        A dictionary of zattrs.
    """
    zattrs = {}
    for k, v in da.attrs.items():
        zattrs[k] = encode_zarr_attr_value(v)
    zattrs[DIMENSION_KEY] = list(da.dims)

    # We don't want `_FillValue` in `.zattrs`
    # It should go in `fill_value` section of `.zarray`
    _ = zattrs.pop('_FillValue', None)

    return zattrs


def _extract_dataarray_coords(
    da: xr.DataArray,
    zattrs: dict,
) -> dict:
    """Helper function to extract coords from DataArray into a directionary.

    Args:
        da: The DataArray to extract coords from.
        zattrs: The zattrs dictionary to add coords to.

    Returns:
        A dictionary of zattrs with coords added.
    """
    if da.coords:
        # Coordinates are only encoded if there are non-dimension coordinates
        nondim_coords = set(da.coords) - set(da.dims)

        if len(nondim_coords) > 0 and da.name not in nondim_coords:
            coords = ' '.join(sorted(nondim_coords))
            zattrs['coordinates'] = encode_zarr_attr_value(coords)
    return zattrs


def _extract_fill_value(
    da: xr.DataArray,
    dtype: np.dtype,
) -> Any:
    """Helper function to extract fill value from DataArray.

    Args:
        da: The DataArray to extract fill value from.
        dtype: The numpy dtype of the DataArray.

    Returns:
        The fill value of the DataArray.
    """
    fill_value = da.attrs.pop('_FillValue', None)
    return encode_fill_value(fill_value, dtype)


def _extract_zarray(
    da: xr.DataArray,
    encoding: dict,
    dtype: np.dtype,
) -> dict:
    """Helper function to extract zarr array metadata.

    Args:
        da: The DataArray to extract zarr array metadata from.
        encoding: The encoding dictionary of the DataArray.
        dtype: The numpy dtype of the DataArray.

    Returns:
        A dictionary of zarr array metadata.
    """
    meta = {
        'compressor': encoding.get('compressor', da.encoding.get('compressor', default_compressor)),
        'filters': encoding.get('filters', da.encoding.get('filters', None)),
        'chunks': encoding.get('chunks', None),
        'dtype': dtype.str,
        'fill_value': _extract_fill_value(da, dtype),
        'order': 'C',
        'shape': list(normalize_shape(da.shape)),
        'zarr_format': ZARR_FORMAT,
    }

    if meta['chunks'] is None:
        meta['chunks'] = da.shape

    # validate chunks
    if isinstance(da.data, DaskArrayType):
        var_chunks = tuple([c[0] for c in da.data.chunks])
    else:
        var_chunks = da.shape
    if not var_chunks == tuple(meta['chunks']):
        raise ValueError('Encoding chunks do not match inferred chunks')

    meta['chunks'] = list(meta['chunks'])  # return chunks as a list

    return meta


def create_zvariables(dataset: xr.Dataset) -> Dict[str, xr.Variable]:
    """Helper function to create a dictionary of zarr encoded variables.

    Args:
        dataset: The Dataset to encode variables from.

    Returns:
        A dictionary of zarr encoded xarray variables.
    """
    zvariables = {}

    for key, da in dataset.variables.items():
        encoded_da: xr.Variable = encode_zarr_variable(da, name=key)
        zvariables[key] = encoded_da

    return zvariables


def create_zmetadata(dataset: xr.Dataset) -> dict:
    """Helper function to create a consolidated zmetadata dictionary.

    Args:
        dataset: The Dataset to create zmetadata from.

    Returns:
        A consolidated zmetadata dictionary.
    """

    zmeta = {
        'zarr_consolidated_format': ZARR_CONSOLIDATED_FORMAT,
        'metadata': {},
    }
    zmeta['metadata'][group_meta_key] = {'zarr_format': ZARR_FORMAT}
    zmeta['metadata'][attrs_key] = _extract_dataset_zattrs(dataset)

    for key, dvar in dataset.variables.items():
        da = dataset[key]
        encoded_da = encode_zarr_variable(dvar, name=key)
        encoding = extract_zarr_variable_encoding(dvar)
        zattrs = _extract_dataarray_zattrs(encoded_da)
        zattrs = _extract_dataarray_coords(da, zattrs)
        zmeta['metadata'][f'{key}/{attrs_key}'] = zattrs
        zmeta['metadata'][f'{key}/{array_meta_key}'] = _extract_zarray(
            encoded_da,
            encoding,
            encoded_da.dtype,
        )

    return zmeta


def jsonify_zmetadata(
    dataset: xr.Dataset,
    zmetadata: dict,
) -> dict:
    """Helper function to convert zmetadata dict to a json compatible dict.

    Args:
        dataset: The Dataset to convert zmetadata from.
        zmetadata: The zmetadata dict to convert.

    Returns:
        A json compatible zmetadata dict.
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


def encode_chunk(
    chunk: npt.ArrayLike,
    filters: Optional[list[Codec]] = None,
    compressor: Optional[Codec] = None,
) -> npt.ArrayLike:
    """Helper function largely copied from zarr.Array.

    Args:
        chunk: The chunk to encode.
        filters: The filters to apply to the chunk.
        compressor: The compressor to apply to the chunk.

    Returns:
        The encoded chunk.

    Raises:
        RuntimeError: If the chunk's dtype is not an object.
    """
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


def get_data_chunk(
    da: xr.DataArray,
    chunk_id: str,
    out_shape: tuple,
) -> npt.ArrayLike:
    """Get one chunk of data from this DataArray (da).

    If this is an incomplete edge chunk, pad the returned array to match out_shape.

    Args:
        da: DataArray to get chunk from.
        chunk_id: Chunk id to get.
        out_shape: Shape of the output chunk.

    Returns:
        Chunk of data from this DataArray (da).
    """
    ikeys = tuple(map(int, chunk_id.split('.')))
    if isinstance(da, DaskArrayType):
        chunk_data = da.blocks[ikeys]
    else:
        if da.ndim > 0 and ikeys != ((0,) * da.ndim):
            raise ValueError(
                'Invalid chunk_id for numpy array: %s. Should have been: %s'
                % (chunk_id, ((0,) * da.ndim))
            )
        chunk_data = np.asarray(da)

    logger.debug('checking chunk output size, %s == %s' % (chunk_data.shape, out_shape))

    if isinstance(chunk_data, DaskArrayType):
        chunk_data = chunk_data.compute()

    # zarr expects full edge chunks, contents out of bounds for the array are undefined
    if chunk_data.shape != tuple(out_shape):
        new_chunk = np.empty_like(chunk_data, shape=out_shape)
        write_slice = tuple([slice(0, s) for s in chunk_data.shape])
        new_chunk[write_slice] = chunk_data
        return new_chunk
    else:
        return chunk_data
