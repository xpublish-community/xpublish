import pytest
import xarray as xr
from starlette.testclient import TestClient

import xpublish  # noqa: F401


@pytest.fixture(scope='function')
def airtemp_ds():
    ds = xr.tutorial.open_dataset('air_temperature')
    return ds


@pytest.fixture(scope='function')
def airtemp_app(airtemp_ds):
    app_kws = dict(
        title='My Dataset',
        description='Dataset Description',
        version='1.0.0',
        openapi_url='/dataset.json',
        docs_url='/data-docs',
    )
    client = TestClient(airtemp_ds.rest(app_kws=app_kws).app)
    yield client


def test_rest_config(airtemp_ds):
    airtemp_ds.rest(cache_kws={'available_bytes': 999})
    assert airtemp_ds.rest.cache.available_bytes == 999


def test_init_app(airtemp_ds):
    airtemp_ds.rest(
        app_kws=dict(
            title='My Dataset',
            description='Dataset Description',
            version='1.0.0',
            openapi_url='/dataset.json',
            docs_url='/data-docs',
        )
    )
    client = TestClient(airtemp_ds.rest.app)
    assert airtemp_ds.rest.app.title == 'My Dataset'
    assert airtemp_ds.rest.app.description == 'Dataset Description'
    assert airtemp_ds.rest.app.version == '1.0.0'

    response = client.get('/dataset.json')
    assert response.status_code == 200

    response = client.get('/data-docs')
    assert response.status_code == 200


def test_keys(airtemp_ds, airtemp_app):
    response = airtemp_app.get('/keys')
    assert response.status_code == 200
    assert response.json() == list(airtemp_ds.variables)


def test_info(airtemp_ds, airtemp_app):
    response = airtemp_app.get('/info')
    assert response.status_code == 200
    json_response = response.json()
    assert json_response['dimensions'] == airtemp_ds.dims
    assert list(json_response['variables'].keys()) == list(airtemp_ds.variables.keys())


def test_versions(airtemp_app):
    response = airtemp_app.get('/versions')
    assert response.status_code == 200
    assert response.json()['xarray'] == xr.__version__


def test_repr(airtemp_ds, airtemp_app):
    response = airtemp_app.get('/')
    assert response.status_code == 200


def test_zmetadata(airtemp_ds, airtemp_app):
    response = airtemp_app.get('/.zmetadata')
    assert response.status_code == 200
    assert response.json() == airtemp_ds._rest_zarr.zmetadata_json()


def test_bad_key(airtemp_app):
    response = airtemp_app.get('/notakey')
    assert response.status_code == 404


def test_zarray(airtemp_app):
    response = airtemp_app.get('/air/.zarray')
    assert response.status_code == 200


def test_zattrs(airtemp_app):
    response = airtemp_app.get('/air/.zattrs')
    assert response.status_code == 200
    response = airtemp_app.get('/.zattrs')
    assert response.status_code == 200


def test_get_chunk(airtemp_app):
    response = airtemp_app.get('/air/0.0.0')
    assert response.status_code == 200


def test_array_group_raises_404(airtemp_app):
    response = airtemp_app.get('/air/.zgroup')
    assert response.status_code == 404


def test_cache(airtemp_ds):
    rest = airtemp_ds.rest(cache_kws={'available_bytes': 1e9})
    assert rest.cache.available_bytes == 1e9

    client = TestClient(rest.app)

    response1 = client.get('/air/0.0.0')
    assert response1.status_code == 200
    assert 'air/0.0.0' in airtemp_ds.rest.cache

    # test that we can retrieve
    response2 = client.get('/air/0.0.0')
    assert response2.status_code == 200
    assert response1.content == response2.content
