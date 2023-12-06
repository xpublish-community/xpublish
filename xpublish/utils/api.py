import json
from collections.abc import Mapping
from typing import (
    Any,
    Dict,
    List,
    Tuple,
    Union,
)

import xarray as xr
from fastapi import APIRouter
from fastapi.openapi.utils import get_openapi
from starlette.responses import JSONResponse as StarletteJSONResponse  # type: ignore

DATASET_ID_ATTR_KEY = '_xpublish_id'


def normalize_datasets(
    datasets: Union[xr.Dataset, Mapping[Any, xr.Dataset]]
) -> Dict[str, xr.Dataset]:
    """Normalize the given collection of datasets.

    This function converts all keys (dataset ids) to strings and adds the
    dataset ids to their corresponding dataset object as global attribute.
    This is so it can be easily retrieved within path operation functions.

    Args:
        datasets: A single xarray.Dataset object or a mapping with Dataset
            objects as values.

    Returns:
        A dictionary with dataset ids as keys and Dataset objects as values.
        If a single Dataset object is given, an empty dictionary is returned.

    Raises:
        TypeError: If objects other than xarray.Dataset are found.
    """
    error_msg = 'Can only publish a xarray.Dataset object or a mapping of Dataset objects'

    if isinstance(datasets, xr.Dataset):
        return {}
    elif isinstance(datasets, Mapping):
        if not all(isinstance(obj, xr.Dataset) for obj in datasets.values()):
            raise TypeError(error_msg)
        return {str(k): ds.assign_attrs({DATASET_ID_ATTR_KEY: k}) for k, ds in datasets.items()}
    else:
        raise TypeError(error_msg)


def normalize_app_routers(
    routers: List[Union[APIRouter, Tuple[APIRouter, Dict]]],
    prefix: str,
) -> List[Tuple[APIRouter, Dict]]:
    """Normalise the given list of (dataset-specific) API routers.

    This adds or prepends ``prefix`` to all router dictionaries.

    Args:
        routers: A list of APIRouter instances or (APIRouter, {...}) tuples.
        prefix: The prefix to add to all routers.

    Returns:
        A list of (APIRouter, {...}) tuples with the given prefix added.

    Raises:
        TypeError: If the routers argument is not a valid list of APIRouter
        instances, or (APIRouter, {...}) tuples.
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


def check_route_conflicts(routers: List[Tuple[APIRouter, Dict]]) -> None:
    """Check for route conflicts in the given list of routers.

    Args:
        routers: A list of (APIRouter, {...}) tuples.

    Raises:
        ValueError: If multiple routes are defined for the same path.
    """
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
    """Used to override the FastAPI application openapi specs when a single dataset is published.

    In this case, the "dataset_id" path parameter is not present in API
    endpoints and has to be removed manually.

    See:

    - https://fastapi.tiangolo.com/advanced/extending-openapi/
    - https://github.com/tiangolo/fastapi/issues/1594

    """

    def __init__(self, app) -> None:
        """Initialize the overrider."""
        self._app = app

    def openapi(self) -> dict:
        """Override the FastAPI application openapi specs."""
        if self._app.openapi_schema:
            return self._app.openapi_schema

        kwargs = {
            'title': self._app.title,
            'version': self._app.version,
            'description': self._app.description,
            'routes': self._app.routes,
            'tags': self._app.openapi_tags,
            'servers': self._app.servers,
        }

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


class JSONResponse(StarletteJSONResponse):
    """A JSON response that uses the same render kwargs as the JSONResponse class from Starlette."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize the JSON response."""
        self._render_kwargs = {
            'ensure_ascii': True,
            'allow_nan': True,
            'indent': None,
            'separators': (',', ':'),
        }
        self._render_kwargs.update(kwargs.pop('render_kwargs', {}))
        super().__init__(*args, **kwargs)

    def render(self, content: Any) -> bytes:
        """Render the JSON response."""
        return json.dumps(content, **self._render_kwargs).encode('utf-8')
