import time

import pytest
import xarray as xr

import xpublish  # noqa: F401
from xpublish.utils.cache import CostTimer


def test_single_dataset_raise(airtemp_ds):
    """A single dataset should throw a TypeError if it's passed to
    xpublish.Rest rather than xpublish.SingleDatasetRest.
    """
    with pytest.raises(TypeError) as excinfo:
        xpublish.Rest(airtemp_ds)
    excinfo.match(
        'xpublish.Rest no longer directly handles single datasets or DataTrees. Please use xpublish.SingleDatasetRest instead'
    )


def test_init_accessor_twice_raises():
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
