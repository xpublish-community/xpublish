import json

import pytest

from xpublish import Rest
from xpublish.utils.zarr import create_zmetadata, jsonify_zmetadata

from .utils import TestMapper


def test_get_zmetadata_key(airtemp_ds):
    mapper = TestMapper(Rest(airtemp_ds).app)
    actual = json.loads(mapper['.zmetadata'].decode())
    expected = jsonify_zmetadata(airtemp_ds, create_zmetadata(airtemp_ds))
    assert actual == expected


def test_missing_key_raises_keyerror(airtemp_ds):
    mapper = TestMapper(Rest(airtemp_ds).app)
    with pytest.raises(KeyError):
        _ = mapper['notakey']
