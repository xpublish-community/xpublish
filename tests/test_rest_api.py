import json

import pytest
import uvicorn
import xarray as xr
from fastapi import APIRouter, Depends
from starlette.testclient import TestClient

import xpublish  # noqa: F401
from xpublish import Plugin, Rest, SingleDatasetRest, hookimpl, hookspec
from xpublish.dependencies import get_dataset
from xpublish.utils.zarr import create_zmetadata, jsonify_zmetadata


@pytest.fixture(scope='function')
def airtemp_rest(airtemp_ds):
    app_kws = {
        'title': 'My Dataset',
        'description': 'Dataset Description',
        'version': '1.0.0',
        'openapi_url': '/dataset.json',
        'docs_url': '/data-docs',
    }

    return SingleDatasetRest(airtemp_ds, app_kws=app_kws)


@pytest.fixture(scope='function')
def airtemp_app_client(airtemp_rest):
    client = TestClient(airtemp_rest.app)
    yield client


@pytest.fixture(scope='function')
def ds_dict():
    return {
        'ds1': xr.Dataset({'var': ('x', [1, 2, 3])}),
        'ds2': xr.Dataset({'var': ('x', [4, 5, 6])}),
    }


@pytest.fixture(scope='function')
def ds_dict_rest(ds_dict):
    return Rest(ds_dict)


@pytest.fixture(scope='function')
def ds_dict_app_client(ds_dict_rest):
    client = TestClient(ds_dict_rest.app)
    yield client


@pytest.fixture(scope='function')
def dims_router():
    router = APIRouter()

    @router.get('/dims')
    def get_dims(dataset: xr.Dataset = Depends(get_dataset)):
        return dataset.dims

    return router


@pytest.fixture(scope='function')
def dataset_plugin(airtemp_ds):
    class AirtempPlugin(Plugin):
        name = 'airtemp'

        @hookimpl
        def get_dataset(self, dataset_id: str):
            if dataset_id == 'airtemp':
                return airtemp_ds

        @hookimpl
        def get_datasets(self):
            return ['airtemp']

    return AirtempPlugin()


@pytest.fixture(scope='function')
def hook_spec_plugin():
    class TestHookSpec:
        @hookspec(firstresult=True)
        def hello(self):
            pass

    class HookSpecPlugin(Plugin):
        name = 'hook_spec'

        @hookimpl
        def register_hookspec(self):
            return TestHookSpec

    return HookSpecPlugin()


@pytest.fixture(scope='function')
def hook_implementation_plugin():
    class HookImplementationPlugin(Plugin):
        name = 'hook_implementation'

        @hookimpl
        def hello(self):
            return 'world'

    return HookImplementationPlugin()


def test_init_cache_kws(airtemp_ds):
    rest = Rest({'airtemp': airtemp_ds}, cache_kws={'available_bytes': 999})
    assert rest.cache.available_bytes == 999


def test_init_app_kws(airtemp_ds):
    rest = Rest(
        {'airtemp': airtemp_ds},
        app_kws={
            'title': 'My Dataset',
            'description': 'Dataset Description',
            'version': '1.0.0',
            'openapi_url': '/dataset.json',
            'docs_url': '/data-docs',
        },
    )

    assert rest.app.title == 'My Dataset'
    assert rest.app.description == 'Dataset Description'
    assert rest.app.version == '1.0.0'

    client = TestClient(rest.app)

    response = client.get('/dataset.json')
    assert response.status_code == 200

    response = client.get('/data-docs')
    assert response.status_code == 200


@pytest.mark.parametrize('datasets', ['not_a_dataset_obj', {'ds': 'not_a_dataset_obj'}])
def test_init_dataset_type_error(datasets):
    with pytest.raises(TypeError, match='Can only publish.*Dataset objects'):
        Rest(datasets)


@pytest.mark.parametrize('router_kws,path', [(None, '/dims'), ({'prefix': '/foo'}, '/foo/dims')])
def test_custom_app_routers(airtemp_ds, dims_router, router_kws, path):
    if router_kws is None:
        routers = [dims_router]
    else:
        routers = [(dims_router, router_kws)]

    rest = SingleDatasetRest(airtemp_ds, routers=routers, plugins={})
    client = TestClient(rest.app)

    response = client.get(path)
    assert response.status_code == 200
    assert response.json() == airtemp_ds.dims

    # test default routers not present
    response = client.get('/')
    assert response.status_code == 404


def test_custom_app_routers_error(airtemp_ds):
    with pytest.raises(TypeError, match='Invalid type/format.*'):
        Rest({'airtemp': airtemp_ds}, routers=['not_a_router'])


def test_custom_app_routers_conflict(airtemp_ds):
    router1 = APIRouter()

    @router1.get('/path')
    def func1():
        pass

    router2 = APIRouter()

    @router2.get('/same/path')
    def func2():
        pass

    with pytest.raises(ValueError, match='Found multiple routes.*'):
        Rest({'airtemp': airtemp_ds}, routers=[(router1, {'prefix': '/same'}), router2])


def test_custom_dataset_plugin(airtemp_ds, dataset_plugin):
    rest = Rest({})
    rest.register_plugin(dataset_plugin)

    client = TestClient(rest.app)

    datasets_response = client.get('/datasets')
    assert 'airtemp' in datasets_response.json()

    info_response = client.get('/datasets/airtemp/info')
    json_response = info_response.json()
    assert json_response['dimensions'] == airtemp_ds.dims
    assert list(json_response['variables'].keys()) == list(airtemp_ds.variables.keys())


def test_custom_plugin_hooks_register(hook_spec_plugin, hook_implementation_plugin):
    rest = Rest({})
    rest.register_plugin(hook_implementation_plugin)
    rest.register_plugin(hook_spec_plugin)

    assert 'world' == rest.pm.hook.hello()


def test_custom_plugin_hooks_init(hook_spec_plugin, hook_implementation_plugin):
    rest = Rest(
        {},
        plugins={'hook_implementation': hook_implementation_plugin, 'hook_spec': hook_spec_plugin},
    )

    assert 'world' == rest.pm.hook.hello()


def test_custom_plugin_not_initialized():
    class TestPlugin(Plugin):
        pass

    rest = Rest({})
    with pytest.raises(AttributeError):
        rest.register_plugin(TestPlugin)


def test_keys(airtemp_ds, airtemp_app_client):
    response = airtemp_app_client.get('/keys')
    assert response.status_code == 200
    assert response.json() == list(airtemp_ds.variables)


def test_info(airtemp_ds, airtemp_app_client):
    response = airtemp_app_client.get('/info')
    assert response.status_code == 200
    json_response = response.json()
    assert json_response['dimensions'] == airtemp_ds.dims
    assert list(json_response['variables'].keys()) == list(airtemp_ds.variables.keys())

    # Second request, to make sure the cached data wasn't changed
    response = airtemp_app_client.get('/info')
    assert response.status_code == 200
    json_response = response.json()
    assert json_response['dimensions'] == airtemp_ds.dims
    assert list(json_response['variables'].keys()) == list(airtemp_ds.variables.keys())


def test_dict(airtemp_ds, airtemp_app_client):
    response = airtemp_app_client.get('/dict')
    assert response.status_code == 200
    actual = response.json()
    expected = airtemp_ds.to_dict(data=False)
    # can't compare actual and expected directly because json converts tuples to lists
    assert actual['coords'].keys() == expected['coords'].keys()


def test_versions(airtemp_app_client):
    response = airtemp_app_client.get('/versions')
    assert response.status_code == 200
    assert response.json()['xarray'] == xr.__version__


def test_plugin_versions(airtemp_app_client):
    response = airtemp_app_client.get('/plugins')
    assert response.status_code == 200

    plugins = response.json()

    assert plugins['dataset_info']['version'] == xpublish.__version__


def test_plugins_loaded(airtemp_app_client):
    response = airtemp_app_client.get('/plugins')
    assert response.status_code == 200

    plugins = response.json()

    assert 'dataset_info' in plugins
    assert 'module_version' in plugins
    assert 'plugin_info' in plugins
    assert 'zarr' in plugins


def test_repr(airtemp_ds, airtemp_app_client):
    response = airtemp_app_client.get('/')
    assert response.status_code == 200


def test_zmetadata(airtemp_ds, airtemp_app_client):
    response = airtemp_app_client.get('/zarr/.zmetadata')
    assert response.status_code == 200
    assert json.dumps(response.json()) == json.dumps(
        jsonify_zmetadata(airtemp_ds, create_zmetadata(airtemp_ds))
    )


def test_bad_key(airtemp_app_client):
    response = airtemp_app_client.get('/zarr/notakey')
    assert response.status_code == 404


def test_zgroup(airtemp_app_client):
    response = airtemp_app_client.get('/zarr/.zgroup')
    assert response.status_code == 200


def test_zarray(airtemp_app_client):
    response = airtemp_app_client.get('/zarr/air/.zarray')
    assert response.status_code == 200


def test_zattrs(airtemp_app_client):
    response = airtemp_app_client.get('/zarr/air/.zattrs')
    assert response.status_code == 200
    response = airtemp_app_client.get('/zarr/.zattrs')
    assert response.status_code == 200


def test_get_chunk(airtemp_app_client):
    response = airtemp_app_client.get('/zarr/air/0.0.0')
    assert response.status_code == 200


def test_array_group_raises_404(airtemp_app_client):
    response = airtemp_app_client.get('/zarr/air/.zgroup')
    assert response.status_code == 404


def test_cache(airtemp_ds):
    rest = SingleDatasetRest(airtemp_ds, cache_kws={'available_bytes': 1e9})
    assert rest.cache.available_bytes == 1e9

    client = TestClient(rest.app)

    response1 = client.get('/zarr/air/0.0.0')
    assert response1.status_code == 200
    assert '/air/0.0.0' in rest.cache

    # test that we can retrieve
    response2 = client.get('/zarr/air/0.0.0')
    assert response2.status_code == 200
    assert response1.content == response2.content


def test_rest_accessor(airtemp_ds):
    client = TestClient(airtemp_ds.rest.app)

    # FastAPI default URL for generated docs
    response = client.get('/docs')
    assert response.status_code == 200


def test_rest_accessor_kws(airtemp_ds):
    airtemp_ds.rest(
        app_kws={'docs_url': '/data-docs'},
        cache_kws={'available_bytes': 1e9},
    )

    assert airtemp_ds.rest.cache.available_bytes == 1e9

    client = TestClient(airtemp_ds.rest.app)

    response = client.get('/data-docs')
    assert response.status_code == 200


def test_rest_accessor_single_dataset(airtemp_ds):
    client = TestClient(airtemp_ds.rest.app)

    response = client.get('/datasets')
    assert response.status_code == 404


def test_ds_dict_keys(ds_dict, ds_dict_app_client):
    response = ds_dict_app_client.get('/datasets')
    assert response.status_code == 200
    assert response.json() == list(ds_dict)

    response = ds_dict_app_client.get('/datasets/zarr/not_in_dict')
    assert response.status_code == 404


def test_ds_dict_cache(ds_dict):
    rest = Rest(ds_dict, cache_kws={'available_bytes': 1e9})

    client = TestClient(rest.app)

    response1 = client.get('/datasets/ds1/zarr/var/0')
    assert response1.status_code == 200
    assert 'ds1/var/0' in rest.cache

    response2 = client.get('/datasets/ds2/info')
    assert response2.status_code == 200
    assert 'ds2/zvariables' in rest.cache
    assert 'ds2/.zmetadata' in rest.cache


def test_single_dataset_openapi_override(airtemp_rest):
    openapi_schema = airtemp_rest.app.openapi()

    with pytest.raises(KeyError):
        # "dataset_id" parameter should be absent in all paths
        # parameters is no longer generated when plugins use passed in deps
        #  and get_dataset is replaced
        assert len(openapi_schema['paths']['/']['get']['parameters']) == 0

    with pytest.raises(KeyError):
        # test cached value
        # parameters is no longer generated when plugins use passed in deps
        #  and get_dataset is replaced
        openapi_schema = airtemp_rest.app.openapi()
        assert len(openapi_schema['paths']['/']['get']['parameters']) == 0


def test_serve(airtemp_rest, mocker):
    kwargs = {'host': '0.0.0.0', 'log_level': 'debug', 'port': 9000}
    mocker.patch('uvicorn.run')
    airtemp_rest.serve(**kwargs)
    uvicorn.run.assert_called_once_with(airtemp_rest.app, **kwargs)


def test_accessor_serve(airtemp_ds, mocker):
    kwargs = {'host': '0.0.0.0', 'log_level': 'debug', 'port': 9000}
    mocker.patch('uvicorn.run')
    airtemp_ds.rest.serve(**kwargs)
    uvicorn.run.assert_called_once_with(airtemp_ds.rest.app, **kwargs)
