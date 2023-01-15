from typing import List

import xarray as xr
from fastapi import APIRouter, Depends
from starlette.responses import HTMLResponse
from zarr.storage import attrs_key

from ..dependencies import get_zmetadata, get_zvariables
from ..plugin import Plugin, hookimpl


class DatasetInfoPlugin(Plugin):
    name = 'dataset_info'

    dataset_router_prefix: str = ''
    dataset_router_tags: List[str] = []

    @hookimpl
    def dataset_router(self):
        router = APIRouter()

        router.prefix = self.dataset_router_prefix
        router.tags = self.dataset_router_tags

        @router.get('/')
        def html_representation(
            dataset=Depends(self.dependencies.dataset),
        ):
            """Returns a HTML representation of the dataset."""

            with xr.set_options(display_style='html'):
                return HTMLResponse(dataset._repr_html_())

        @router.get('/keys')
        def list_keys(
            dataset=Depends(self.dependencies.dataset),
        ):
            return list(dataset.variables)

        @router.get('/dict')
        def to_dict(
            dataset=Depends(self.dependencies.dataset),
        ):
            return dataset.to_dict(data=False)

        @router.get('/info')
        def info(
            dataset=Depends(self.dependencies.dataset),
            cache=Depends(self.dependencies.cache),
        ):
            """Dataset schema (close to the NCO-JSON schema)."""

            zvariables = get_zvariables(dataset, cache)
            zmetadata = get_zmetadata(dataset, cache, zvariables)

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

        return router
