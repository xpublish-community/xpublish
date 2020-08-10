from collections.abc import Mapping
from typing import Dict, List, Tuple

import xarray as xr
from fastapi import APIRouter
from fastapi.openapi.utils import get_openapi

DATASET_ID_ATTR_KEY = '_xpublish_id'


def normalize_datasets(datasets) -> Dict[str, xr.Dataset]:
    """Normalize the given collection of datasets.

    - raise TypeError if objects other than xarray.Dataset are found
    - return an empty dictionary in the special case where a single dataset is given
    - convert all keys (dataset ids) to strings
    - add dataset ids to their corresponding dataset object as global attribute
      (so that it can be easily retrieved within path operation functions).

    """
    error_msg = 'Can only publish a xarray.Dataset object or a mapping of Dataset objects'

    if isinstance(datasets, xr.Dataset):
        return {}
    elif isinstance(datasets, Mapping):
        if not all([isinstance(obj, xr.Dataset) for obj in datasets.values()]):
            raise TypeError(error_msg)
        return {str(k): ds.assign_attrs({DATASET_ID_ATTR_KEY: k}) for k, ds in datasets.items()}
    else:
        raise TypeError(error_msg)


def normalize_app_routers(routers: list, prefix: str) -> List[Tuple[APIRouter, Dict]]:
    """Normalise the given list of (dataset-specific) API routers.

    Add or prepend ``prefix`` to all routers.

    """
    new_routers = []

    for rt in routers:
        if isinstance(rt, APIRouter):
            new_routers.append((rt, {'prefix': prefix}))
        elif isinstance(rt, tuple) and isinstance(rt[0], APIRouter) and len(rt) == 2:
            rt_kwargs = rt[1]
            rt_kwargs['prefix'] = prefix + rt_kwargs.get('prefix', '')
            new_routers.append((rt[0], rt_kwargs))
        else:
            raise TypeError(
                'Invalid type/format for routers argument, please provide either an APIRouter '
                'instance or a (APIRouter, {...}) tuple.'
            )

    return new_routers


def check_route_conflicts(routers):

    paths = []

    for router, kws in routers:
        prefix = kws.get('prefix', '')
        paths += [prefix + r.path for r in router.routes]

    seen = set()
    duplicates = []

    for p in paths:
        if p in seen:
            duplicates.append(p)
        else:
            seen.add(p)

    if len(duplicates):
        raise ValueError(f'Found multiple routes defined for the following paths: {duplicates}')


class SingleDatasetOpenAPIOverrider:
    """Used to override the FastAPI application openapi specs when a single
    dataset is published.

    In this case, the "dataset_id" path parameter is not present in API
    endpoints and has to be removed manually.

    See:

    - https://fastapi.tiangolo.com/advanced/extending-openapi/
    - https://github.com/tiangolo/fastapi/issues/1594

    """

    def __init__(self, app):
        self._app = app

    def openapi(self, *args):

        if self._app.openapi_schema:
            return self._app.openapi_schema

        kwargs = dict(
            title=self._app.title,
            version=self._app.version,
            description=self._app.description,
            routes=self._app.routes,
        )

        # TODO: remove when required fastapi min version >= 0.56.0
        openapi_prefix = getattr(self._app, 'openapi_prefix', None)
        if openapi_prefix is not None:
            kwargs.update(openapi_prefix=self._app.openapi_prefix)

        # TODO: remove 'if' when required fastapi min version >= 0.57.0
        tags = getattr(self._app, 'openapi_tags', None)
        if tags is not None:
            kwargs['tags'] = tags

        # TODO: remove 'if' when required fastapi min version >= 0.58.0
        servers = getattr(self._app, 'servers', None)
        if servers is not None:
            kwargs['servers'] = servers

        # TODO: remove when required fastapi min version >= 0.59.0
        if len(args):
            kwargs.update(openapi_prefix=args[0])

        openapi_schema = get_openapi(**kwargs)

        for path in openapi_schema.get('paths', {}).values():
            for http_method in path.values():
                params = http_method.get('parameters')

                if params is not None:
                    for i, p in enumerate(params):
                        if p.get('name') == 'dataset_id':
                            params.pop(i)

        self._app.openapi_schema = openapi_schema

        return self._app.openapi_schema
