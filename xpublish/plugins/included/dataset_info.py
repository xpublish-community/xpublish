from typing import Any, Sequence

import numpy as np
import xarray as xr
from fastapi import APIRouter, Depends
from starlette.responses import HTMLResponse  # type: ignore

from xpublish.utils.api import DATASET_ID_ATTR_KEY, JSONResponse

from .. import Dependencies, Plugin, hookimpl


def _jsonable(value: Any) -> Any:
    """Convert numpy/array-like values into JSON-serializable Python types."""
    if isinstance(value, np.ndarray):
        return [_jsonable(v) for v in value.tolist()]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    return value


class DatasetInfoPlugin(Plugin):
    """Dataset metadata."""

    name: str = 'dataset_info'

    dataset_router_prefix: str = ''
    dataset_router_tags: Sequence[str] = ['dataset_info']

    @hookimpl
    def dataset_router(self, deps: Dependencies) -> APIRouter:  # noqa: D102
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
            """List of the keys in a dataset."""
            return JSONResponse(list(dataset.variables))

        @router.get('/dict')
        def to_dict(
            dataset=Depends(deps.dataset),
        ) -> dict:
            """The full dataset as a dictionary."""
            return JSONResponse(dataset.to_dict(data=False))

        @router.get('/info')
        def info(
            dataset=Depends(deps.dataset),
        ) -> dict:
            """Dataset schema (close to the NCO-JSON schema)."""
            info: dict = {}
            info['dimensions'] = dict(dataset.dims.items())
            info['variables'] = {}

            for name, var in dataset.variables.items():
                info['variables'][name] = {
                    'type': var.dtype.name,
                    'dimensions': list(var.dims),
                    'attributes': _jsonable(dict(var.attrs)),
                }

            global_attrs = dict(dataset.attrs)
            global_attrs.pop(DATASET_ID_ATTR_KEY, None)
            info['global_attributes'] = _jsonable(global_attrs)

            return JSONResponse(info)

        return router
