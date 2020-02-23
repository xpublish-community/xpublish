import json

import pytest
import xarray as xr

import xpublish  # noqa: F401

from .utils import TestMapper


@pytest.fixture(scope="module")
def airtemp_ds():
    ds = xr.tutorial.open_dataset("air_temperature")
    return ds


def test_get_zmetadata_key(airtemp_ds):
    mapper = TestMapper(airtemp_ds.rest.app)
    actual = json.loads(mapper[".zmetadata"].decode())
    assert actual == airtemp_ds.rest.zmetadata_json()


def test_missing_key_raises_keyerror(airtemp_ds):
    mapper = TestMapper(airtemp_ds.rest.app)
    with pytest.raises(KeyError):
        _ = mapper["notakey"]
