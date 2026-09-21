from collections.abc import Sequence
from typing import Any

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
    """Dataset metadata.

    Exposes both flat-dataset endpoints (operating on the root node of the
    underlying :py:class:`xarray.DataTree`) and group-aware variants that
    accept a ``{group_path:path}`` segment to navigate into the tree.
    Additional tree-shaped endpoints expose the DataTree directly.
    """

    name: str = 'dataset_info'

    dataset_router_prefix: str = ''
    dataset_router_tags: Sequence[str] = ['dataset_info']

    @hookimpl
    def dataset_router(self, deps: Dependencies) -> APIRouter:  # noqa: D102
        router = APIRouter(
            prefix=self.dataset_router_prefix,
            tags=list(self.dataset_router_tags),
        )

        def html_representation(
            dataset=Depends(deps.dataset),
        ) -> HTMLResponse:
            """Returns the xarray HTML representation of the dataset."""
            with xr.set_options(display_style='html'):
                return HTMLResponse(dataset._repr_html_())

        def list_keys(
            dataset=Depends(deps.dataset),
        ) -> list[str]:
            """List of the keys in a dataset."""
            return JSONResponse(list(dataset.variables))

        def to_dict(
            dataset=Depends(deps.dataset),
        ) -> dict:
            """The full dataset as a dictionary."""
            return JSONResponse(dataset.to_dict(data=False))

        def info(
            dataset=Depends(deps.dataset),
            cache=Depends(deps.cache),
        ) -> dict:
            """Dataset schema (close to the NCO-JSON schema)."""
            cache_key = dataset.attrs.get(DATASET_ID_ATTR_KEY, '') + '/' + 'info'
            info = cache.get(cache_key)

            if info is None:
                info = {
                    'dimensions': dict(dataset.sizes),
                    'variables': {
                        name: {
                            'type': var.dtype.name,
                            'dimensions': list(var.dims),
                            'attributes': _jsonable(dict(var.attrs)),
                        }
                        for name, var in dataset.variables.items()
                    },
                }

                global_attrs = dict(dataset.attrs)
                global_attrs.pop(DATASET_ID_ATTR_KEY, None)
                info['global_attributes'] = _jsonable(global_attrs)

                cache.put(cache_key, info, 99999)

            return JSONResponse(info)

        def tree_html(
            datatree: xr.DataTree = Depends(deps.datatree),
        ) -> HTMLResponse:
            """Returns the xarray HTML representation of the full DataTree."""
            with xr.set_options(display_style='html'):
                return HTMLResponse(datatree._repr_html_())

        def groups(
            datatree: xr.DataTree = Depends(deps.datatree),
        ) -> list[str]:
            """List of all group paths in the DataTree."""
            return JSONResponse(list(datatree.groups))

        # Bare endpoints (operate on the root node).
        router.get('/', name='html_representation')(html_representation)
        router.get('/keys', name='list_keys')(list_keys)
        router.get('/dict', name='to_dict')(to_dict)
        router.get('/info', name='info')(info)

        # Tree-shaped endpoints (expose the full DataTree directly).
        router.get('/tree', name='tree_html')(tree_html)
        router.get('/groups', name='groups')(groups)

        # Group-aware variants. The ``{group_path:path}`` path parameter is
        # consumed transparently by ``deps.dataset`` (see
        # ``Rest.get_dataset_from_plugins``) to return the dataset at the
        # requested node of the DataTree. Suffix routes must be registered
        # before the bare ``/groups/{group_path:path}`` route or FastAPI will
        # match the bare route first.
        router.get('/groups/{group_path:path}/keys', name='list_keys_group')(list_keys)
        router.get('/groups/{group_path:path}/dict', name='to_dict_group')(to_dict)
        router.get('/groups/{group_path:path}/info', name='info_group')(info)
        router.get('/groups/{group_path:path}', name='html_representation_group')(
            html_representation,
        )

        return router
