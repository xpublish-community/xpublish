import time

import dask
import numpy as np
import pytest
import xarray as xr

import xpublish  # noqa: F401
from xpublish.utils import CostTimer, get_data_chunk


def test_dask_chunks_become_zarr_chunks():
    expected = [4, 5, 1]
    data1 = dask.array.zeros((10, 20, 30), chunks=expected)
    data2 = np.zeros((10, 20, 30))
    ds = xr.Dataset({'foo': (['x', 'y', 'z'], data1), 'bar': (['x', 'y', 'z'], data2)})
    assert ds.rest.zmetadata['metadata']['foo/.zarray']['chunks'] == expected
    assert ds.rest.zmetadata['metadata']['bar/.zarray']['chunks'] == list(data2.shape)


def test_invalid_dask_chunks_raise():
    data1 = dask.array.zeros((10, 20, 30), chunks=(4, 10, 1))
    data2 = dask.array.zeros((10, 20, 30), chunks=(4, 5, 1))
    data = dask.array.concatenate([data1, data2])
    ds = xr.Dataset({'foo': (['x', 'y', 'z'], data)})

    with pytest.raises(ValueError) as excinfo:
        _ = ds.rest.zmetadata
    excinfo.match(r'Zarr requires uniform chunk sizes .*')


def test_invalid_encoding_chunks_with_dask_raise():
    expected = [4, 5, 1]
    data = dask.array.zeros((10, 20, 30), chunks=expected)
    ds = xr.Dataset({'foo': (['x', 'y', 'z'], data)})
    ds['foo'].encoding['chunks'] = [8, 5, 1]
    with pytest.raises(NotImplementedError) as excinfo:
        _ = ds.rest.zmetadata
    excinfo.match(r'Specified zarr chunks .*')


def test_invalid_encoding_chunks_with_numpy_raise():
    data = np.zeros((10, 20, 30))
    ds = xr.Dataset({'foo': (['x', 'y', 'z'], data)})
    ds['foo'].encoding['chunks'] = [8, 5, 1]
    with pytest.raises(ValueError) as excinfo:
        _ = ds.rest.zmetadata
    excinfo.match(r'Encoding chunks do not match inferred.*')


def test_get_data_chunk_numpy():
    shape = (2, 5)
    data = np.arange(10).reshape(shape)
    actual = get_data_chunk(data, '0.0', shape)
    np.testing.assert_equal(data, actual)

    with pytest.raises(ValueError) as excinfo:
        _ = get_data_chunk(data, '1.0', shape)
    excinfo.match(r'Invalid chunk_id for numpy array*')


def test_get_data_chunk_numpy_edge_chunk():
    # 1d case
    out_shape = (12,)
    data = np.arange(10)
    actual = get_data_chunk(data, '0', out_shape)
    assert actual.shape == out_shape
    np.testing.assert_equal(data, actual[:10])

    # 2d case
    out_shape = (3, 5)
    data = np.arange(10).reshape((2, 5))
    actual = get_data_chunk(data, '0.0', out_shape)
    np.testing.assert_equal(data, actual[:2, :])


def test_init_twice_raises():
    ds = xr.Dataset({'foo': (['x'], [1, 2, 3])})
    ds.rest(app_kws={'foo': 'bar'})
    with pytest.raises(RuntimeError) as excinfo:
        ds.rest(app_kws={'bar': 'foo'})
    excinfo.match(r'This accessor has already been initialized')


def test_cache_timer():
    with CostTimer() as ct:
        time.sleep(1)

    assert ct.time >= 1
    assert ct.time < 1.1
