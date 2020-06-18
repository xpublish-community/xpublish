import json

import pytest
import xarray as xr

import xpublish  # noqa: F401
from xpublish.routers.zarr import get_zmetadata

from .utils import get_zmeta, TestMapper


@pytest.fixture(scope='module')
def airtemp_ds():
    ds = xr.tutorial.open_dataset('air_temperature')
    return ds


def test_get_zmetadata_key(airtemp_ds):
    mapper = TestMapper(airtemp_ds.rest.app)
    actual = json.loads(mapper['.zmetadata'].decode())
    expected = json.loads(get_zmetadata(airtemp_ds, get_zmeta(airtemp_ds)).body)
    assert actual == expected


def test_missing_key_raises_keyerror(airtemp_ds):
    mapper = TestMapper(airtemp_ds.rest.app)
    with pytest.raises(KeyError):
        _ = mapper['notakey']
