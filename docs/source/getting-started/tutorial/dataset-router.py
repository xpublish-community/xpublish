import xarray as xr
from fastapi import APIRouter, Depends, HTTPException

from xpublish.dependencies import get_dataset

ds = xr.tutorial.open_dataset(
    'air_temperature',
    chunks={'lat': 5, 'lon': 5},
)

myrouter = APIRouter()


@myrouter.get('/{var_name}/mean')
def get_mean(var_name: str, dataset: xr.Dataset = Depends(get_dataset)):
    if var_name not in dataset.variables:
        raise HTTPException(status_code=404, detail=f"Variable '{var_name}' not found in dataset")

    return float(dataset[var_name].mean())


rest = ds.rest(routers=[myrouter])

rest.serve()
