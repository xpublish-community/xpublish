import xarray as xr
from fastapi import APIRouter, Depends
from starlette.responses import HTMLResponse


def get_dataset():
    """FastAPI dependency for accessing a xarray dataset object.

    Use this callable as dependency in any FastAPI path operation
    function where you need access to the xarray Dataset being served.

    This dummy dependency will be overridden when creating the FastAPI
    application.

    """
    return None


base_router = APIRouter()


@base_router.get('/')
def html_representation(dataset: xr.Dataset = Depends(get_dataset)):
    """Returns a HTML representation of the dataset."""

    with xr.set_options(display_style='html'):
        return HTMLResponse(dataset._repr_html_())


@base_router.get('/keys')
def list_keys(dataset: xr.Dataset = Depends(get_dataset)):
    return list(dataset.variables)


@base_router.get('/dict')
def to_dict(dataset: xr.Dataset = Depends(get_dataset)):
    return dataset.to_dict(data=False)
