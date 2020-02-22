import xarray as xr

import xpublish  # noqa: F401

if __name__ == "__main__":
    ds = xr.tutorial.open_dataset(
        "air_temperature", chunks=dict(lat=5, lon=5), decode_cf=False
    )
    print(ds)

    ds.rest.serve()
