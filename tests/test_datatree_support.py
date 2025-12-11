import pytest
import xarray as xr
from fastapi import APIRouter, Depends, HTTPException
from starlette.testclient import TestClient

from xpublish import Plugin, Rest, hookimpl
from xpublish.dependencies import get_datatree, get_datatree_ids


@pytest.fixture
def simple_datatree():
    return xr.DataTree(xr.Dataset({'a': ('x', [1, 2, 3])}), name='simple')


@pytest.fixture
def second_datatree():
    return xr.DataTree(xr.Dataset({'b': ('x', [4])}), name='second')


def _make_tree(name: str = 'tree'):
    """Helper datatree with predictable data for router tests."""
    return xr.DataTree(xr.Dataset({'a': ('x', [1])}), name=name)


class DatatreeRouterPlugin(Plugin):
    """Test plugin that exposes custom routes on DataTree resources."""

    name: str = 'datatree_router_plugin'

    @hookimpl
    def datatree_router(self, deps):
        """Return a router that exercises datatree-specific hooks."""
        router = APIRouter(prefix='/custom')

        @router.get('/echo-id')
        def echo_id(tree=Depends(deps.datatree)):
            return {'name': tree.name}

        @router.get('/double')
        def double_value(tree=Depends(get_datatree)):
            return {'double': float(tree.to_dataset()['a'].item() * 2)}

        return router


def test_datasets_only_leave_datatree_registry_empty(airtemp_ds):
    rest = Rest({'airtemp': airtemp_ds})
    deps = rest.dependencies()

    assert deps.datatree_ids() == []

    with pytest.raises(HTTPException) as excinfo:
        deps.datatree('missing')

    assert excinfo.value.status_code == 404


def test_datatrees_only_are_accessible(simple_datatree):
    rest = Rest({}, datatrees={'tree': simple_datatree}, plugins={})
    deps = rest.dependencies()

    assert deps.datatree_ids() == ['tree']
    assert deps.datatree('tree') is simple_datatree


def test_mixed_collections_expose_both_types(airtemp_ds, simple_datatree):
    rest = Rest({'air': airtemp_ds}, datatrees={'tree': simple_datatree}, plugins={})
    deps = rest.dependencies()

    assert 'air' in deps.dataset_ids()
    assert 'tree' in deps.datatree_ids()
    resolved = deps.dataset('air')
    assert resolved.equals(airtemp_ds)
    assert resolved.attrs.get('_xpublish_id') == 'air'
    assert deps.datatree('tree') is simple_datatree


def test_conflicting_ids_between_dataset_and_datatree_raise(airtemp_ds, simple_datatree):
    with pytest.raises(ValueError):
        Rest({'shared': airtemp_ds}, datatrees={'shared': simple_datatree}, plugins={})


def test_plugin_datatrees_resolve_and_are_exposed_via_dependencies(simple_datatree):
    plugin_tree = xr.DataTree(xr.Dataset({'plugin_var': ('x', [0])}), name='plugin_tree')

    class DataTreePlugin(Plugin):
        name: str = 'datatree_plugin'

        @hookimpl
        def get_datatrees(self):
            return ['plugin-tree']

        @hookimpl
        def get_datatree(self, datatree_id: str):
            if datatree_id == 'plugin-tree':
                return plugin_tree

        @hookimpl
        def app_router(self, deps):
            router = APIRouter(prefix='/datatrees')

            @router.get('/ids')
            def list_ids(ids=Depends(get_datatree_ids)):
                return ids

            @router.get('/{datatree_id}/vars')
            def list_vars(tree=Depends(get_datatree)):
                return list(tree.to_dataset().data_vars)

            return router

    rest = Rest({}, datatrees={'local': simple_datatree}, plugins={'datatree_plugin': DataTreePlugin()})
    client = TestClient(rest.app)

    ids_response = client.get('/datatrees/ids')
    assert ids_response.status_code == 200
    assert set(ids_response.json()) == {'local', 'plugin-tree'}

    vars_response = client.get('/datatrees/plugin-tree/vars')
    assert vars_response.status_code == 200
    assert vars_response.json() == ['plugin_var']


def test_datatree_dependency_returns_404_for_missing_tree(simple_datatree):
    rest = Rest({}, datatrees={'tree': simple_datatree}, plugins={})
    deps = rest.dependencies()

    with pytest.raises(HTTPException) as excinfo:
        deps.datatree('does-not-exist')

    assert excinfo.value.status_code == 404


def test_datatree_router_is_mounted_under_datatree_prefix():
    tree = _make_tree()
    rest = Rest(
        {},
        datatrees={'pyramid': tree},
        plugins={'dt_router': DatatreeRouterPlugin()},
    )
    client = TestClient(rest.app)

    response = client.get('/datatrees/pyramid/custom/echo-id')
    assert response.status_code == 200
    assert response.json() == {'name': 'tree'}


def test_dataset_routes_remain_unchanged_with_datatree_router(airtemp_ds):
    tree = _make_tree()
    rest = Rest(
        {'air': airtemp_ds},
        datatrees={'pyramid': tree},
        plugins={'dt_router': DatatreeRouterPlugin()},
    )
    client = TestClient(rest.app)

    # dataset listing route still reachable
    response = client.get('/datasets')
    assert response.status_code == 200
    assert 'air' in response.json()

    # datatree route reachable via datatree prefix
    dt_response = client.get('/datatrees/pyramid/custom/double')
    assert dt_response.status_code == 200
    assert dt_response.json() == {'double': 2.0}
