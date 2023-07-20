from typing import Sequence

import xarray as xr
from fastapi import APIRouter, Depends
from starlette.responses import HTMLResponse  # type: ignore
from zarr.storage import attrs_key  # type: ignore

from xpublish.utils.api import JSONResponse

from ...dependencies import get_zmetadata, get_zvariables
from .. import Dependencies, Plugin, hookimpl


class DatasetInfoPlugin(Plugin):
    """Dataset metadata"""

    name: str = 'dataset_info'

    dataset_router_prefix: str = ''
    dataset_router_tags: Sequence[str] = ['dataset_info']

    @hookimpl
    def dataset_router(self, deps: Dependencies) -> APIRouter:
        router = APIRouter(
            prefix=self.dataset_router_prefix,
            tags=list(self.dataset_router_tags),
        )

        @router.get('/')
        def html_representation(
            dataset=Depends(deps.dataset),
        ) -> HTMLResponse:
            """Returns the xarray HTML representation of the dataset."""

            with xr.set_options(display_style='html'):
                return HTMLResponse(dataset._repr_html_())

        @router.get('/keys')
        def list_keys(
            dataset=Depends(deps.dataset),
        ) -> list[str]:
            """List of the keys in a dataset"""

            return JSONResponse(list(dataset.variables))

        @router.get('/dict')
        def to_dict(
            dataset=Depends(deps.dataset),
        ) -> dict:
            """The full dataset as a dictionary"""
            return JSONResponse(dataset.to_dict(data=False))

        @router.get('/info')
        def info(
            dataset=Depends(deps.dataset),
            cache=Depends(deps.cache),
        ) -> dict:
            """Dataset schema (close to the NCO-JSON schema)."""

            zvariables = get_zvariables(dataset, cache)
            zmetadata = get_zmetadata(dataset, cache, zvariables)

            info = {}
            info['dimensions'] = dict(dataset.dims.items())
            info['variables'] = {}

            meta = zmetadata['metadata']

            for name, var in zvariables.items():
                attrs = meta[f'{name}/{attrs_key}'].copy()
                attrs.pop('_ARRAY_DIMENSIONS')

                info['variables'][name] = {
                    'type': var.data.dtype.name,
                    'dimensions': list(var.dims),
                    'attributes': attrs,
                }

            info['global_attributes'] = meta[attrs_key]

            return JSONResponse(info)

        return router
