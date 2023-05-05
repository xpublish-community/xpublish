from functools import reduce
from operator import mul

import numpy as np
import pandas as pd
import xarray as xr
from starlette.testclient import TestClient
from zarr.storage import BaseStore

rs = np.random.RandomState(np.random.MT19937(np.random.SeedSequence(123456789)))


class TestMapper(TestClient, BaseStore):
    """
    A simple subclass to support getitem syntax on Starlette TestClient Objects
    """

    def __getitem__(self, key):
        zarr_key = f'/zarr/{key}'
        response = self.get(zarr_key)
        if response.status_code != 200:
            raise KeyError('{} not found. status_code = {}'.format(zarr_key, response.status_code))
        return response.content

    def __delitem__(self, key):
        return NotImplemented

    def __iter__(self):
        return NotImplemented

    def __len__(self):
        return NotImplemented

    def __setitem__(self, key, value):
        return NotImplemented


def create_dataset(
    start='2018-01',
    end='2020-12',
    freq='MS',
    calendar='standard',
    units='days since 1980-01-01',
    use_cftime=True,
    decode_times=True,
    nlats=1,
    nlons=1,
    var_const=None,
    use_xy_dim=False,
):
    """Utility function for creating test data"""

    if use_cftime:
        end = xr.coding.cftime_offsets.to_cftime_datetime(end, calendar=calendar)
        dates = xr.cftime_range(start=start, end=end, freq=freq, calendar=calendar)

    else:
        dates = pd.date_range(start=pd.to_datetime(start), end=pd.to_datetime(end), freq=freq)

    decoded_time_bounds = np.vstack((dates[:-1], dates[1:])).T

    encoded_time_bounds = xr.coding.times.encode_cf_datetime(
        decoded_time_bounds, units=units, calendar=calendar
    )[0]

    encoded_times = xr.DataArray(
        encoded_time_bounds.mean(axis=1),
        dims=('time'),
        name='time',
        attrs={'units': units, 'calendar': calendar},
    )

    decoded_times = xr.DataArray(
        xr.coding.times.decode_cf_datetime(
            encoded_times, units=units, calendar=calendar, use_cftime=use_cftime
        ),
        dims=['time'],
    )
    decoded_time_bounds = xr.DataArray(
        decoded_time_bounds, name='time_bounds', dims=('time', 'd2'), coords={'time': decoded_times}
    )

    if decode_times:
        times = decoded_times
        time_bounds = decoded_time_bounds

    else:
        times = encoded_times
        time_bounds = xr.DataArray(
            encoded_time_bounds, name='time_bounds', dims=('time', 'd2'), coords={'time': times}
        )

    lats = np.linspace(start=-90, stop=90, num=nlats, dtype='float32')
    lons = np.linspace(start=-180, stop=180, num=nlons, dtype='float32')

    if use_xy_dim:
        lats, lons = np.meshgrid(lats, lons)
        shape = (times.size, *lats.shape)
    else:
        shape = (times.size, lats.size, lons.size)

    num = reduce(mul, shape)

    if var_const is None:
        annual_cycle = np.sin(2 * np.pi * (decoded_times.dt.dayofyear.values / 365.25 - 0.28))
        base = 10 + 15 * annual_cycle.reshape(-1, 1)
        tmin_values = base + 3 * np.random.randn(annual_cycle.size, nlats * nlons)
        tmax_values = base + 10 + 3 * np.random.randn(annual_cycle.size, nlats * nlons)
        tmin_values = tmin_values.reshape(shape)
        tmax_values = tmax_values.reshape(shape)

    elif var_const:
        tmin_values = np.ones(shape=shape)
        tmax_values = np.ones(shape=shape) + 2

    else:
        tmin_values = np.arange(1, num + 1).reshape(shape)
        tmax_values = np.arange(1, num + 1).reshape(shape)

    ds = xr.Dataset(
        {
            'tmin': xr.DataArray(
                tmin_values.astype('float32'),
                dims=('time', 'lat', 'lon') if not use_xy_dim else ('time', 'y', 'x'),
                name='tmin',
            ),
            'tmax': xr.DataArray(
                tmax_values.astype('float32'),
                dims=('time', 'lat', 'lon') if not use_xy_dim else ('time', 'y', 'x'),
                name='tmax',
            ),
            'time_bounds': time_bounds,
        },
        coords={
            'time': times,
            'lat': ('lat' if not use_xy_dim else ['y', 'x'], lats),
            'lon': ('lon' if not use_xy_dim else ['y', 'x'], lons),
        },
    )

    ds.tmin.encoding['_FillValue'] = np.float32(-9999999)
    ds.tmax.encoding['_FillValue'] = np.float32(-9999999)
    ds.time.attrs['bounds'] = 'time_bounds'
    ds.time.encoding['units'] = units
    ds.time.encoding['calendar'] = calendar

    return ds
