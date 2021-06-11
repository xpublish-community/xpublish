import numpy as np
import pytest
import xarray as xr


@pytest.fixture(scope='module')
def airtemp_ds():
    ds = xr.tutorial.open_dataset('air_temperature')
    ds['air'].encoding['_FillValue'] = -9999
    return ds


@pytest.fixture(autouse=True)
def setup():
    np.random.seed(0)
