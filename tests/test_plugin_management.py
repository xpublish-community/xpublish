from starlette.testclient import TestClient

from xpublish import Rest
from xpublish.plugins import manage


def test_exclude_plugins():
    found_plugins = manage.find_default_plugins(exclude_plugins=['zarr'])

    assert 'zarr' not in found_plugins
    assert 'info' in found_plugins


def test_configure_plugins(airtemp_ds):
    info_prefix = '/meta'
    zarr_prefix = '/zarr'
    config = {
        'info': {'dataset_router_prefix': info_prefix},
        'zarr': {'dataset_router_prefix': zarr_prefix},
    }
    found_plugins = manage.find_default_plugins()

    configured_plugins = manage.configure_plugins(found_plugins, config)

    assert configured_plugins['info'].dataset_router_prefix == info_prefix
    assert configured_plugins['zarr'].dataset_router_prefix == zarr_prefix

    rest = Rest({'airtemp': airtemp_ds}, plugins=configured_plugins)
    app = rest.app
    client = TestClient(app)

    info_response = client.get('/datasets/airtemp/meta/info')
    json_response = info_response.json()
    assert json_response['dimensions'] == airtemp_ds.dims
    assert list(json_response['variables'].keys()) == list(airtemp_ds.variables.keys())
