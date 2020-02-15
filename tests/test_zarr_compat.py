import pytest
import xarray as xr
import zarr
from fsspec.implementations.http import HTTPFileSystem

import xpublish

import json

from .utils import TestMapper


@pytest.fixture(scope="module")
def airtemp_ds():
    ds = xr.tutorial.open_dataset("air_temperature")
    return ds


@pytest.mark.xfail(reason="We are not populating the default compressors/filters yet.")
def test_zmetadata_identical(airtemp_ds):
    zarr_dict = {}
    airtemp_ds.to_zarr(zarr_dict, consolidated=True)
    mapper = TestMapper(airtemp_ds.rest.app)
    actual = json.loads(mapper[".zmetadata"].decode())
    expected = json.loads(zarr_dict[".zmetadata"].decode())
    assert actual == expected


@pytest.mark.xfail(reason="We are not populating the default compressors/filters yet.")
def test_roundtrip(airtemp_ds):
    mapper = TestMapper(airtemp_ds.rest.app)
    actual = xr.open_zarr(mapper, consolidated=True)

    xr.testing.assert_identical(actual, airtemp_ds)
