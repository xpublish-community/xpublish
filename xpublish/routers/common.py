"""
Dataset-independent API routes.

"""
from fastapi import APIRouter, Depends

from ..dependencies import get_dataset_ids

dataset_collection_router = APIRouter()


@dataset_collection_router.get('/datasets')
def get_dataset_collection_keys(ids: list = Depends(get_dataset_ids)) -> list[str]:
    """Return all the currently known Dataset IDs"""
    return ids
