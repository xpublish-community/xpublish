from collections.abc import Mapping
from typing import Dict, List, Tuple

import xarray as xr
from fastapi import APIRouter

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
