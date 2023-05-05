import xarray as xr
from dask.distributed import Client

import xpublish  # noqa: F401

if __name__ == '__main__':
    client = Client(n_workers=4, dashboard_address=8787)
    print(client.cluster)
    print(client.cluster.dashboard_link)

    ds = xr.tutorial.open_dataset('air_temperature', chunks={'lat': 5, 'lon': 5}, decode_cf=False)
    print(ds)

    for _k, da in ds.variables.items():
        da.encoding['compressor'] = None

    app = ds.rest.app

    from starlette.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=['*'],
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )
    ds.rest._app = app

    ds.rest.serve()
