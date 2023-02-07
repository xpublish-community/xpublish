import json
from typing import Any, Sequence

import xarray as xr
from fastapi import APIRouter, Depends
from starlette.responses import HTMLResponse, JSONResponse  # type: ignore
from zarr.storage import attrs_key  # type: ignore

from ...dependencies import get_zmetadata, get_zvariables
from .. import Dependencies, Plugin, hookimpl


class JsonInfoResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=True,
            indent=None,
            separators=(',', ':'),
        ).encode('utf-8')


class DatasetInfoPlugin(Plugin):
    name = 'dataset_info'

    dataset_router_prefix: str = ''
    dataset_router_tags: Sequence[str] = []

    @hookimpl
    def dataset_router(self, deps: Dependencies):
        router = APIRouter(prefix=self.dataset_router_prefix, tags=list(self.dataset_router_tags))

        @router.get('/')
        def html_representation(
            dataset=Depends(deps.dataset),
        ):
            """Returns a HTML representation of the dataset."""

            with xr.set_options(display_style='html'):
                return HTMLResponse(dataset._repr_html_())

        @router.get('/keys')
        def list_keys(
            dataset=Depends(deps.dataset),
        ):
            return list(dataset.variables)

        @router.get('/dict')
        def to_dict(
            dataset=Depends(deps.dataset),
        ):
            return dataset.to_dict(data=False)

        @router.get('/info')
        def info(
            dataset=Depends(deps.dataset),
            cache=Depends(deps.cache),
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

            return JsonInfoResponse(info)

        return router
