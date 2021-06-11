import json

import pytest
import xarray as xr

from xpublish import Rest

from .utils import TestMapper, create_dataset


@pytest.mark.parametrize(
    'start, end, freq, nlats, nlons, var_const, calendar, use_cftime',
    [
        ('2018-01-01', '2021-01-01', 'MS', 180, 360, True, 'standard', False),
        ('2018-01-01', '2021-01-01', 'D', 180, 360, False, 'noleap', True),
        ('2018-01-01', '2021-01-01', '6H', 180, 360, True, 'gregorian', False),
        ('2018-01-01', '2050-01-01', 'A', 180, 360, None, '360_day', True),
    ],
)
def test_zmetadata_identical(start, end, freq, nlats, nlons, var_const, calendar, use_cftime):
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
    ds.to_zarr(zarr_dict, consolidated=True)
    mapper = TestMapper(Rest(ds).app)
    actual = json.loads(mapper['.zmetadata'].decode())
    expected = json.loads(zarr_dict['.zmetadata'].decode())
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

    mapper = TestMapper(Rest(ds).app)
    actual = xr.open_zarr(mapper, consolidated=True)

    xr.testing.assert_identical(actual, ds)


xfail_reason = """Currently, xarray casts datetimes arrays to NumPy compatible arrays.
This ends up producing unexpected behavior when calling encode_zarr_varible()
on datasets with variables containing datetime like dtypes.

See: https://github.com/xarray-contrib/xpublish/pull/10#discussion_r388028417"""


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
    mapper = TestMapper(Rest(ds).app)
    actual = xr.open_zarr(mapper, consolidated=True, decode_times=decode_times)

    xr.testing.assert_identical(actual, ds)
