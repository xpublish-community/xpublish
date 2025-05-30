import json

import numpy as np
import pytest
import xarray as xr
from fastapi.testclient import TestClient
from zarr.core.buffer import default_buffer_prototype
from zarr.storage import MemoryStore

from xpublish import SingleDatasetRest

from .utils import TestStore, create_dataset


@pytest.mark.parametrize(
    'start, end, freq, nlats, nlons, var_const, calendar, use_cftime',
    [
        ('2018-01-01', '2021-01-01', 'MS', 180, 360, True, 'standard', False),
        ('2018-01-01', '2021-01-01', 'D', 180, 360, False, 'noleap', True),
        ('2018-01-01', '2021-01-01', '6h', 180, 360, True, 'gregorian', False),
        ('2018-01-01', '2050-01-01', 'YE', 180, 360, None, '360_day', True),
    ],
)
async def test_zmetadata_identical(start, end, freq, nlats, nlons, var_const, calendar, use_cftime):
    ds = create_dataset(
        start=start,
        end=end,
        freq=freq,
        nlats=nlats,
        nlons=nlons,
        var_const=var_const,
        use_cftime=use_cftime,
        calendar=calendar,
    )

    ds = ds.chunk(ds.dims)
    zarr_dict = {}
    zarr_store = MemoryStore(zarr_dict)
    ds.to_zarr(zarr_store, consolidated=True, zarr_format=2)
    client = TestClient(SingleDatasetRest(ds).app)
    mapper = TestStore(client)

    payload = await mapper.get('.zmetadata', default_buffer_prototype())
    actual_payload = payload.to_bytes().decode()
    actual = json.loads(actual_payload)

    expected_buffer = await zarr_store.get('.zmetadata', default_buffer_prototype())
    expected_payload = expected_buffer.to_bytes().decode()
    expected = json.loads(expected_payload)

    assert actual == expected


@pytest.mark.parametrize(
    'start, end, freq, nlats, nlons, var_const, calendar, use_cftime',
    [
        pytest.param(
            '2018-01-01',
            '2021-01-01',
            'MS',
            15,
            30,
            True,
            'standard',
            False,
            marks=pytest.mark.xfail(
                reason="Xarray's ordering of metadata coords in a string can very"
            ),
        ),
    ],
)
async def test_zmetadata_identical_coords(
    start, end, freq, nlats, nlons, var_const, calendar, use_cftime
):
    ds = create_dataset(
        start=start,
        end=end,
        freq=freq,
        nlats=nlats,
        nlons=nlons,
        var_const=var_const,
        use_cftime=use_cftime,
        calendar=calendar,
        use_xy_dim=True,
    )

    ds = ds.chunk(ds.dims)
    zarr_dict = {}
    zarr_store = MemoryStore(zarr_dict)
    ds.to_zarr(zarr_store, consolidated=True, zarr_format=2)
    client = TestClient(SingleDatasetRest(ds).app)
    mapper = TestStore(client)

    payload = await mapper.get('.zmetadata', default_buffer_prototype())
    actual = json.loads(payload.to_bytes().decode())
    expected = json.loads(zarr_dict['.zmetadata'].to_bytes().decode())
    assert (
        actual == expected
    ), "Zarr metadata did not match, likely because array coordinates aren't sorted by Xarray"


@pytest.mark.parametrize(
    'start, end, freq, nlats, nlons, var_const, calendar, use_cftime',
    [
        (
            '2018-01-01',
            '2021-01-01',
            'MS',
            15,
            30,
            True,
            'standard',
            False,
        ),
    ],
)
async def test_zmetadata_identical_coords_sorted(
    start, end, freq, nlats, nlons, var_const, calendar, use_cftime
):
    """Test that zmetadata passes when coords are explicitly sorted."""
    ds = create_dataset(
        start=start,
        end=end,
        freq=freq,
        nlats=nlats,
        nlons=nlons,
        var_const=var_const,
        use_cftime=use_cftime,
        calendar=calendar,
        use_xy_dim=True,
    )

    ds = ds.chunk(ds.dims)
    zarr_dict = {}
    zarr_store = MemoryStore(zarr_dict)
    ds.to_zarr(zarr_store, consolidated=True, zarr_format=2)
    client = TestClient(SingleDatasetRest(ds).app)
    store = TestStore(client)

    payload = await store.get('.zmetadata', default_buffer_prototype())
    actual = json.loads(payload.to_bytes().decode())
    expected = json.loads(zarr_dict['.zmetadata'].to_bytes().decode())

    for key in ['tmin/.zattrs', 'tmax/.zattrs']:
        coords = expected['metadata'][key]['coordinates']
        expected['metadata'][key]['coordinates'] = ' '.join(sorted(coords.split(' ')))

    assert actual == expected


@pytest.mark.parametrize(
    'start, end, freq, nlats, nlons, var_const, calendar, use_cftime',
    [
        ('2018-01-01', '2021-01-01', 'MS', 180, 360, True, 'standard', False),
        ('2018-01-01', '2021-01-01', 'D', 180, 360, False, 'noleap', True),
        ('2018-01-01', '2021-01-01', '6H', 180, 360, True, 'gregorian', False),
        ('2018-01-01', '2050-01-01', 'A', 180, 360, None, '360_day', True),
    ],
)
def test_roundtrip(start, end, freq, nlats, nlons, var_const, calendar, use_cftime):
    ds = create_dataset(
        start=start,
        end=end,
        freq=freq,
        nlats=nlats,
        nlons=nlons,
        var_const=var_const,
        use_cftime=use_cftime,
        calendar=calendar,
    )
    ds = ds.chunk(ds.dims)
    client = TestClient(SingleDatasetRest(ds).app)
    store = TestStore(client)
    actual = xr.open_zarr(store, consolidated=True, zarr_format=2)

    xr.testing.assert_identical(actual, ds)


xfail_reason = """Currently, xarray casts datetimes arrays to NumPy compatible arrays.
This ends up producing unexpected behavior when calling encode_zarr_varible()
on datasets with variables containing datetime like dtypes.

See: https://github.com/xpublish-community/xpublish/pull/10#discussion_r388028417"""


@pytest.mark.parametrize(
    'start, end, freq, nlats, nlons, var_const, calendar, use_cftime, chunks, decode_times',
    [
        ('2018-01-01', '2021-01-01', 'MS', 180, 360, True, 'standard', False, {'time': 10}, False),
        (
            '2018-01-01',
            '2021-01-01',
            'D',
            300,
            600,
            False,
            'noleap',
            True,
            {'time': 10, 'lat': 300, 'lon': 300},
            False,
        ),
        pytest.param(
            '2018-01-01',
            '2021-01-01',
            'D',
            300,
            600,
            False,
            'noleap',
            True,
            {'time': 10, 'lat': 300, 'lon': 300},
            True,
            marks=pytest.mark.xfail(reason=xfail_reason),
        ),
        (
            '2018-01-01',
            '2021-01-01',
            '12H',
            180,
            360,
            True,
            'gregorian',
            False,
            {'time': 36, 'lat': 10},
            False,
        ),
        (
            '2018-01-01',
            '2038-01-01',
            'A',
            300,
            600,
            None,
            '360_day',
            True,
            {'time': 10, 'lat': 75, 'lon': 120},
            False,
        ),
        pytest.param(
            '2018-01-01',
            '2038-01-01',
            'A',
            300,
            600,
            None,
            '360_day',
            True,
            {'time': 10, 'lat': 75, 'lon': 120},
            True,
            marks=pytest.mark.xfail(reason=xfail_reason),
        ),
    ],
)
def test_roundtrip_custom_chunks(
    start, end, freq, nlats, nlons, var_const, calendar, use_cftime, chunks, decode_times
):
    ds = create_dataset(
        start=start,
        end=end,
        freq=freq,
        nlats=nlats,
        nlons=nlons,
        var_const=var_const,
        use_cftime=use_cftime,
        calendar=calendar,
        decode_times=decode_times,
    )
    ds = ds.chunk(chunks)
    client = TestClient(SingleDatasetRest(ds).app)
    store = TestStore(client)
    actual = xr.open_zarr(store, consolidated=True, zarr_format=2, decode_times=decode_times)

    xr.testing.assert_identical(actual, ds)


def test_scalar_variable():
    ds = xr.Dataset(
        {
            'scalar': xr.DataArray(
                np.float32(0.0),
                dims=(),
                name='scalar',
            )
        }
    )
    client = TestClient(SingleDatasetRest(ds).app)
    store = TestStore(client)
    actual = xr.open_zarr(store, consolidated=True, zarr_format=2)

    xr.testing.assert_identical(actual, ds)
