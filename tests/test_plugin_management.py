import pytest
from starlette.testclient import TestClient

from xpublish import Rest
from xpublish.plugins import manage


def test_exclude_plugins():
    found_plugins = manage.find_default_plugins(exclude_plugins=['zarr'])

    assert 'zarr' not in found_plugins
    assert 'dataset_info' in found_plugins


def test_configure_plugins(airtemp_ds):
    info_prefix = '/meta'
    zarr_prefix = '/zarr'
    config = {
        'dataset_info': {'dataset_router_prefix': info_prefix},
        'zarr': {'dataset_router_prefix': zarr_prefix},
    }
    found_plugins = manage.find_default_plugins()

    configured_plugins = manage.configure_plugins(found_plugins, config)

    assert configured_plugins['dataset_info'].dataset_router_prefix == info_prefix
    assert configured_plugins['zarr'].dataset_router_prefix == zarr_prefix

    rest = Rest({'airtemp': airtemp_ds}, plugins=configured_plugins)
    app = rest.app
    client = TestClient(app)

    info_response = client.get('/datasets/airtemp/meta/info')
    json_response = info_response.json()
    assert json_response['dimensions'] == airtemp_ds.dims
    assert list(json_response['variables'].keys()) == list(airtemp_ds.variables.keys())


def test_overwrite_plugins(airtemp_ds):
    from xpublish.plugins.included.dataset_info import DatasetInfoPlugin

    # Test discoverable plugins
    info = DatasetInfoPlugin()
    rest = Rest({'airtemp': airtemp_ds}, plugins={'dataset_info': info})

    # Registering a duplicate plugin name will fail
    same_name = DatasetInfoPlugin(name='dataset_info', dataset_router_prefix='/newinfo')
    with pytest.raises(ValueError):
        rest.register_plugin(same_name)

    # Register with overwrite
    rest.register_plugin(same_name, overwrite=True)

    # Change the name of the plugin
    new_name = DatasetInfoPlugin(name='meta', dataset_router_prefix='/newmeta')
    rest.register_plugin(new_name)

    # Registering a duplicate plugin name will fail
    new_prefix = DatasetInfoPlugin(name='meta', dataset_router_prefix='/meta')
    with pytest.raises(ValueError):
        rest.register_plugin(new_prefix)

    app = rest.app
    client = TestClient(app)

    # /info (default) plugin shouldn't respond... it's gone
    assert client.get('/datasets/airtemp/info').status_code == 404
    # /newmeta plugin should respond correctly
    assert client.get('/datasets/airtemp/newmeta').status_code == 200
    # /meta was never registered
    assert client.get('/datasets/airtemp/meta').status_code == 404
    # /newinfo plugin should respond correctly
    info_response = client.get('/datasets/airtemp/newinfo/info')
    json_response = info_response.json()
    assert json_response['dimensions'] == airtemp_ds.dims
    assert list(json_response['variables'].keys()) == list(airtemp_ds.variables.keys())
