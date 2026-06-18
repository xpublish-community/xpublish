import json
from collections.abc import Iterator, Mapping
from typing import Any

import xarray as xr
from fastapi import APIRouter
from fastapi.openapi.utils import get_openapi
from starlette.responses import JSONResponse as StarletteJSONResponse  # type: ignore

DATASET_ID_ATTR_KEY = '_xpublish_id'


def normalize_datasets(
    datasets: xr.Dataset | xr.DataTree | Mapping[Any, xr.Dataset | xr.DataTree],
) -> dict[str, xr.DataTree]:
    """Normalize the given collection of datasets or DataTrees.

    Internally xpublish stores everything as a :py:class:`xarray.DataTree`.
    Bare :py:class:`xarray.Dataset` values are wrapped in a single-node
    DataTree so the rest of the code can operate uniformly.

    Keys (dataset ids) are converted to strings and the dataset id is
    stored as a global attribute on the (root) dataset so it can be
    retrieved within path operation functions.

    Args:
        datasets: A single Dataset/DataTree or a mapping with Dataset
            or DataTree objects as values.

    Returns:
        A dictionary with dataset ids as keys and DataTree objects as values.
        If a single Dataset/DataTree is given, an empty dictionary is
        returned.

    Raises:
        TypeError: If objects other than xarray.Dataset/DataTree are found.
    """
    error_msg = (
        'Can only publish a xarray.Dataset/DataTree object or a mapping of Dataset/DataTree objects'
    )

    if isinstance(datasets, (xr.Dataset, xr.DataTree)):
        return {}
    if not isinstance(datasets, Mapping):
        raise TypeError(error_msg)

    if not all(isinstance(obj, (xr.Dataset, xr.DataTree)) for obj in datasets.values()):
        raise TypeError(error_msg)

    normalized: dict[str, xr.DataTree] = {}
    for k, obj in datasets.items():
        key = str(k)
        tree = obj if isinstance(obj, xr.DataTree) else xr.DataTree(dataset=obj)
        root_ds = tree.dataset
        if root_ds.attrs.get(DATASET_ID_ATTR_KEY) != key:
            tree.dataset = root_ds.assign_attrs({DATASET_ID_ATTR_KEY: key})
        normalized[key] = tree

    return normalized


def normalize_app_routers(
    routers: list[APIRouter | tuple[APIRouter, dict]],
    prefix: str,
) -> list[tuple[APIRouter, dict]]:
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


def _iter_route_paths(routes: list[Any], prefix: str) -> Iterator[tuple[str, Any]]:
    """Yield ``(path, methods)`` for every leaf route under ``routes``.

    Routes added via :meth:`fastapi.APIRouter.include_router` are not always
    flattened into the parent's route list. On Starlette >= 1.0 the nested
    router is kept as an ``_IncludedRouter`` entry that exposes neither
    ``.path`` nor ``.methods``; its routes (and the prefix it was mounted at)
    live on ``original_router`` and ``include_context``. Recurse into those so
    conflict detection sees the same paths the running app will serve.
    """
    for r in routes:
        if hasattr(r, 'path'):
            yield prefix + r.path, getattr(r, 'methods', None)
            continue

        included = getattr(r, 'original_router', None)
        context = getattr(r, 'include_context', None)
        if included is not None and context is not None:
            sub_prefix = prefix + getattr(context, 'prefix', '')
            yield from _iter_route_paths(included.routes, sub_prefix)


def check_route_conflicts(routers: list[tuple[APIRouter, dict[str, Any]]]) -> None:
    """Check for route conflicts in the given list of routers.

    Args:
        routers: A list of (APIRouter, {...}) tuples.

    Raises:
        ValueError: If multiple routes are defined for the same path and HTTP
            method. The same path with disjoint methods (e.g. a GET and a POST
            query endpoint) is legitimate routing and is allowed.
    """
    seen = set()
    duplicates = []

    for router, kws in routers:
        prefix = kws.get('prefix', '')
        for path, route_methods in _iter_route_paths(router.routes, prefix):
            # Routes without methods (e.g. a Mount) collide on path alone.
            methods = route_methods or {None}
            for method in methods:
                key = (path, method)
                if key in seen:
                    duplicates.append(path if method is None else f'{method} {path}')
                else:
                    seen.add(key)

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
