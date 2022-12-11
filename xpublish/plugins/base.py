from dataclasses import dataclass, field
from typing import List

import xarray as xr
from fastapi import Depends
from starlette.responses import HTMLResponse
from zarr.storage import attrs_key

from ..dependencies import get_zmetadata, get_zvariables
from .factory import XpublishPluginFactory


@dataclass
class BasePlugin(XpublishPluginFactory):
    """API entry-points providing basic information about the dataset(s)."""

    dataset_router_prefix: str = ''
    dataset_router_tags: List[str] = field(default_factory=lambda: ['info'])

    def register_routes(self):
        @self.dataset_router.get('/')
        def html_representation(
            dataset=Depends(self.dataset_dependency),
        ):
            """Returns a HTML representation of the dataset."""

            with xr.set_options(display_style='html'):
                return HTMLResponse(dataset._repr_html_())

        @self.dataset_router.get('/keys')
        def list_keys(
            dataset=Depends(self.dataset_dependency),
        ):
            return list(dataset.variables)

        @self.dataset_router.get('/dict')
        def to_dict(
            dataset=Depends(self.dataset_dependency),
        ):
            return dataset.to_dict(data=False)

        @self.dataset_router.get('/info')
        def info(
            dataset=Depends(self.dataset_dependency),
            cache=Depends(self.cache_dependency),
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
