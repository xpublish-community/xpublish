import json

import pytest
from fastapi.testclient import TestClient
from zarr.core.buffer import default_buffer_prototype

from xpublish import SingleDatasetRest
from xpublish.utils.zarr import create_zmetadata, jsonify_zmetadata

from .utils import TestStore


async def test_get_zmetadata_key(airtemp_ds):
    client = TestClient(SingleDatasetRest(airtemp_ds).app)
    store = TestStore(client)
    payload = await store.get('.zmetadata', default_buffer_prototype())
    actual = json.loads(payload.to_bytes().decode())
    expected = jsonify_zmetadata(airtemp_ds, create_zmetadata(airtemp_ds))
    assert json.dumps(actual, allow_nan=True) == json.dumps(expected, allow_nan=True)


async def test_missing_key_raises_keyerror(airtemp_ds):
    client = TestClient(SingleDatasetRest(airtemp_ds).app)
    store = TestStore(client)
    with pytest.raises(KeyError):
        _ = await store.get('notakey', default_buffer_prototype())
