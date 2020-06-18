import xarray as xr
from fastapi import APIRouter, Depends
from starlette.responses import HTMLResponse
from zarr.storage import attrs_key

from ..dependencies import get_dataset, get_zmetadata, get_zvariables

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


@base_router.get('/info')
def info(
    dataset: xr.Dataset = Depends(get_dataset),
    zvariables: dict = Depends(get_zvariables),
    zmetadata: dict = Depends(get_zmetadata),
):
    """Dataset schema (close to the NCO-JSON schema)."""

    info = {}
    info['dimensions'] = dict(dataset.dims.items())
    info['variables'] = {}

    meta = zmetadata['metadata']

    for name, var in zvariables.items():
        attrs = meta[f'{name}/{attrs_key}']
        attrs.pop('_ARRAY_DIMENSIONS')
        info['variables'][name] = {
            'type': var.data.dtype.name,
            'dimensions': list(var.dims),
            'attributes': attrs,
        }

    info['global_attributes'] = meta[attrs_key]

    return info
