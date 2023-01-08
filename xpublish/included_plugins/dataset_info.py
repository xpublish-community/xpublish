import xarray as xr
from fastapi import Depends
from pydantic import Field
from starlette.responses import HTMLResponse
from zarr.storage import attrs_key

from ..dependencies import get_zmetadata, get_zvariables
from ..plugin import Plugin, Router


class DatasetInfoRouter(Router):
    """API entry-points providing basic information about the dataset(s)."""

    prefix = ''

    def register(self):
        @self._router.get('/')
        def html_representation(
            dataset=Depends(self.deps.dataset),
        ):
            """Returns a HTML representation of the dataset."""

            with xr.set_options(display_style='html'):
                return HTMLResponse(dataset._repr_html_())

        @self._router.get('/keys')
        def list_keys(
            dataset=Depends(self.deps.dataset),
        ):
            return list(dataset.variables)

        @self._router.get('/dict')
        def to_dict(
            dataset=Depends(self.deps.dataset),
        ):
            return dataset.to_dict(data=False)

        @self._router.get('/info')
        def info(
            dataset=Depends(self.deps.dataset),
            cache=Depends(self.deps.cache),
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


class DatasetInfoPlugin(Plugin):
    name = 'dataset_info'

    dataset_router: DatasetInfoRouter = Field(default_factory=DatasetInfoRouter)
