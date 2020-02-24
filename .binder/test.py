import xarray as xr
from dask.distributed import Client

import xpublish  # noqa: F401

if __name__ == "__main__":

    client = Client(n_workers=4, dashboard_address=8787)
    print(client.cluster)
    print(client.cluster.dashboard_link)

    ds = xr.tutorial.open_dataset("air_temperature", chunks=dict(lat=5, lon=5), decode_cf=False)
    print(ds)

    ds.rest.serve()
