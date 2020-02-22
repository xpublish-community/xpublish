import io

import pytest
import xarray as xr
from starlette.testclient import TestClient

import xpublish  # noqa: F401


@pytest.fixture(scope='module')
def airtemp_ds():
    ds = xr.tutorial.open_dataset('air_temperature')
    return ds


@pytest.fixture(scope='module')
def airtemp_app(airtemp_ds):
    client = TestClient(airtemp_ds.rest.app)
    yield client


def test_keys(airtemp_ds, airtemp_app):
    response = airtemp_app.get('/keys')
    assert response.status_code == 200
    assert response.json() == list(airtemp_ds.variables)


def test_info(airtemp_ds, airtemp_app):
    response = airtemp_app.get('/info')
    assert response.status_code == 200

    with io.StringIO() as buffer:
        airtemp_ds.info(buf=buffer)
        info = buffer.getvalue()

    assert info == response.json()


def test_repr(airtemp_ds, airtemp_app):
    response = airtemp_app.get('/')
    assert response.status_code == 200


def test_zmetadata(airtemp_ds, airtemp_app):
    response = airtemp_app.get('/.zmetadata')
    assert response.status_code == 200
    assert response.json() == airtemp_ds.rest.zmetadata_json()


def test_bad_key(airtemp_app):
    response = airtemp_app.get('/notakey')
    assert response.status_code == 404


def test_get_chunk(airtemp_ds, airtemp_app):
    response = airtemp_app.get('/air/0.0.0')
    assert response.status_code == 200
