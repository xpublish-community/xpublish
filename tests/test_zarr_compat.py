import json

import pytest
import xarray as xr

import xpublish  # noqa: F401

from .utils import TestMapper, create_dataset


@pytest.fixture(scope='module')
def airtemp_ds():
    ds = xr.tutorial.open_dataset('air_temperature')
    return ds.chunk(dict(ds.dims))


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
        nlats=nlats,
        nlons=nlons,
        var_const=var_const,
        use_cftime=use_cftime,
        calendar=calendar,
    )

    ds = ds.chunk(ds.dims)
    zarr_dict = {}
    ds.to_zarr(zarr_dict, consolidated=True)
    mapper = TestMapper(ds.rest.app)
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
        nlats=nlats,
        nlons=nlons,
        var_const=var_const,
        use_cftime=use_cftime,
        calendar=calendar,
    )
    ds = ds.chunk(ds.dims)

    mapper = TestMapper(ds.rest.app)
    actual = xr.open_zarr(mapper, consolidated=True)

    xr.testing.assert_identical(actual, ds)


@pytest.mark.parametrize(
    'start, end, freq, nlats, nlons, var_const, calendar, use_cftime, chunks',
    [
        ('2018-01-01', '2021-01-01', 'MS', 180, 360, True, 'standard', False, {'time': 10}),
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
        ),
        (
            '2018-01-01',
            '2050-01-01',
            'A',
            300,
            600,
            None,
            '360_day',
            True,
            {'time': 10, 'lat': 30, 'lon': 30},
        ),
    ],
)
def test_roundtrip_custom_chunks(
    start, end, freq, nlats, nlons, var_const, calendar, use_cftime, chunks
):
    ds = create_dataset(
        start=start,
        end=end,
        nlats=nlats,
        nlons=nlons,
        var_const=var_const,
        use_cftime=use_cftime,
        calendar=calendar,
    )
    ds = ds.chunk(chunks)
    mapper = TestMapper(ds.rest.app)
    actual = xr.open_zarr(mapper, consolidated=True)

    xr.testing.assert_identical(actual, ds)
