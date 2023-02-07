import json

import pytest

from xpublish import SingleDatasetRest
from xpublish.utils.zarr import create_zmetadata, jsonify_zmetadata

from .utils import TestMapper


def test_get_zmetadata_key(airtemp_ds):
    mapper = TestMapper(SingleDatasetRest(airtemp_ds).app)
    actual = json.loads(mapper['.zmetadata'].decode())
    expected = jsonify_zmetadata(airtemp_ds, create_zmetadata(airtemp_ds))
    assert json.dumps(actual, allow_nan=True) == json.dumps(expected, allow_nan=True)


def test_missing_key_raises_keyerror(airtemp_ds):
    mapper = TestMapper(SingleDatasetRest(airtemp_ds).app)
    with pytest.raises(KeyError):
        _ = mapper['notakey']
