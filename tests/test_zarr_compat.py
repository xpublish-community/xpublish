import json

import pytest
import xarray as xr

import xpublish  # noqa: F401

from .utils import TestMapper


@pytest.fixture(scope="module")
def airtemp_ds():
    ds = xr.tutorial.open_dataset("air_temperature")
    return ds.chunk(dict(ds.dims))


def test_zmetadata_identical(airtemp_ds):
    zarr_dict = {}
    airtemp_ds.to_zarr(zarr_dict, consolidated=True)
    mapper = TestMapper(airtemp_ds.rest.app)
    actual = json.loads(mapper[".zmetadata"].decode())
    expected = json.loads(zarr_dict[".zmetadata"].decode())
    assert actual == expected


def test_roundtrip(airtemp_ds):
    mapper = TestMapper(airtemp_ds.rest.app)
    actual = xr.open_zarr(mapper, consolidated=True)

    xr.testing.assert_identical(actual, airtemp_ds)
