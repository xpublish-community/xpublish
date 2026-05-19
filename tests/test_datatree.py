"""Tests for DataTree support in xpublish.

Covers:
  * Passing :class:`xarray.DataTree` objects to ``Rest`` and ``SingleDatasetRest``.
  * The ``get_datatree`` provider hook (and lazy-by-group providers).
  * Group navigation via the ``{group_path:path}`` URL segment.
  * Backwards compat for the deprecated ``get_dataset`` provider hook.
  * The ``.rest`` accessor on DataTrees.
"""

from __future__ import annotations

from typing import Optional

import pytest
import xarray as xr
from starlette.testclient import TestClient

from xpublish import Plugin, Rest, SingleDatasetRest, hookimpl


@pytest.fixture(scope='function')
def simple_tree() -> xr.DataTree:
    """A small DataTree:

        /          (no vars)
        /a         (x[0..2])
        /a/b       (y[0..1])
        /c         (z[0..3])
    """
    root = xr.DataTree(name='root')
    root['a'] = xr.DataTree(dataset=xr.Dataset({'x': ('i', [1, 2, 3])}))
    root['a/b'] = xr.DataTree(dataset=xr.Dataset({'y': ('j', [10.0, 20.0])}))
    root['c'] = xr.DataTree(dataset=xr.Dataset({'z': ('k', [0, 1, 2, 3])}))
    return root


@pytest.fixture(scope='function')
def root_ds() -> xr.Dataset:
    return xr.Dataset({'var': ('x', [1, 2, 3])})


# ---------------------------------------------------------------------------
# Rest / SingleDatasetRest accept DataTrees
# ---------------------------------------------------------------------------


def test_rest_accepts_datatree(simple_tree):
    rest = Rest({'tree': simple_tree})
    client = TestClient(rest.app)

    response = client.get('/datasets')
    assert response.status_code == 200
    assert response.json() == ['tree']


def test_rest_accepts_mixed_dataset_and_datatree(simple_tree, root_ds):
    rest = Rest({'tree': simple_tree, 'flat': root_ds})
    client = TestClient(rest.app)

    # Flat dataset is reachable at root
    r = client.get('/datasets/flat/keys')
    assert r.status_code == 200
    assert r.json() == ['var']

    # Tree's root is empty
    r = client.get('/datasets/tree/keys')
    assert r.status_code == 200
    assert r.json() == []


def test_rest_rejects_bare_datatree():
    with pytest.raises(TypeError, match='no longer directly handles'):
        Rest(xr.DataTree(dataset=xr.Dataset({'x': ('i', [1])})))


# ---------------------------------------------------------------------------
# /tree and /groups endpoints (tree-aware extensions to dataset_info)
# ---------------------------------------------------------------------------


def test_groups_endpoint(simple_tree):
    rest = Rest({'tree': simple_tree})
    client = TestClient(rest.app)

    r = client.get('/datasets/tree/groups')
    assert r.status_code == 200
    assert set(r.json()) == {'/', '/a', '/a/b', '/c'}


def test_tree_html_endpoint(simple_tree):
    rest = Rest({'tree': simple_tree})
    client = TestClient(rest.app)

    r = client.get('/datasets/tree/tree')
    assert r.status_code == 200
    # HTML-ish response with DataTree's repr
    assert 'DataTree' in r.text or 'datatree' in r.text.lower()


# ---------------------------------------------------------------------------
# Group navigation via /groups/{group_path:path}/...
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    'group_path,expected_keys',
    [
        ('a', ['x']),
        ('a/b', ['y']),
        ('c', ['z']),
    ],
)
def test_group_keys(simple_tree, group_path, expected_keys):
    rest = Rest({'tree': simple_tree})
    client = TestClient(rest.app)

    r = client.get(f'/datasets/tree/groups/{group_path}/keys')
    assert r.status_code == 200
    assert r.json() == expected_keys


def test_group_html_no_trailing_slash(simple_tree):
    rest = Rest({'tree': simple_tree})
    client = TestClient(rest.app)

    r = client.get('/datasets/tree/groups/a')
    assert r.status_code == 200


def test_missing_group_returns_404(simple_tree):
    rest = Rest({'tree': simple_tree})
    client = TestClient(rest.app)

    r = client.get('/datasets/tree/groups/does_not_exist/keys')
    assert r.status_code == 404


def test_root_dataset_via_unprefixed_route_is_root(simple_tree):
    """The pre-existing /keys endpoint must keep returning the root dataset."""
    rest = Rest({'tree': simple_tree})
    client = TestClient(rest.app)

    r = client.get('/datasets/tree/keys')
    assert r.status_code == 200
    assert r.json() == []  # root has no variables in our fixture


# ---------------------------------------------------------------------------
# get_datatree provider hook
# ---------------------------------------------------------------------------


def test_get_datatree_provider(simple_tree):
    class TreePlugin(Plugin):
        name: str = 'tree-provider'

        @hookimpl
        def get_datasets(self):
            return ['provided']

        @hookimpl
        def get_datatree(
            self, dataset_id: str, group: str,
        ) -> Optional[xr.DataTree]:
            if dataset_id != 'provided':
                return None
            return simple_tree[group] if group else simple_tree

    rest = Rest({})
    rest.register_plugin(TreePlugin())
    client = TestClient(rest.app)

    # Root
    r = client.get('/datasets/provided/keys')
    assert r.status_code == 200
    assert r.json() == []

    # Sub-group
    r = client.get('/datasets/provided/groups/a/keys')
    assert r.status_code == 200
    assert r.json() == ['x']

    r = client.get('/datasets/provided/groups/a/b/keys')
    assert r.status_code == 200
    assert r.json() == ['y']


def test_lazy_get_datatree_provider():
    """A booth-style provider that opens only the requested node."""
    nodes = {
        '': xr.Dataset({'root_var': ('r', [0, 0])}),
        'a': xr.Dataset({'x': ('i', [1, 2, 3])}),
        'a/b': xr.Dataset({'y': ('j', [10.0, 20.0])}),
    }

    class LazyPlugin(Plugin):
        name: str = 'lazy'
        call_count: int = 0

        @hookimpl
        def get_datasets(self):
            return ['lazy']

        @hookimpl
        def get_datatree(
            self, dataset_id: str, group: str,
        ) -> Optional[xr.DataTree]:
            if dataset_id != 'lazy':
                return None
            self.call_count += 1
            ds = nodes.get(group)
            if ds is None:
                return None
            return xr.DataTree(dataset=ds)

    plugin = LazyPlugin()
    rest = Rest({})
    rest.register_plugin(plugin)
    client = TestClient(rest.app)

    r = client.get('/datasets/lazy/keys')
    assert r.status_code == 200
    assert r.json() == ['root_var']

    r = client.get('/datasets/lazy/groups/a/keys')
    assert r.status_code == 200
    assert r.json() == ['x']

    r = client.get('/datasets/lazy/groups/a/b/keys')
    assert r.status_code == 200
    assert r.json() == ['y']

    # Lazy provider returns None for unknown groups -> 404
    r = client.get('/datasets/lazy/groups/does_not_exist/keys')
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Legacy get_dataset provider hook still works (deprecated path)
# ---------------------------------------------------------------------------


def test_legacy_get_dataset_provider_wrapped_into_single_node_tree(root_ds):
    class LegacyPlugin(Plugin):
        name: str = 'legacy'

        @hookimpl
        def get_datasets(self):
            return ['legacy']

        @hookimpl
        def get_dataset(self, dataset_id: str):
            if dataset_id == 'legacy':
                return root_ds
            return None

    rest = Rest({})
    rest.register_plugin(LegacyPlugin())
    client = TestClient(rest.app)

    r = client.get('/datasets/legacy/keys')
    assert r.status_code == 200
    assert r.json() == ['var']

    # /groups should report a single-node tree
    r = client.get('/datasets/legacy/groups')
    assert r.status_code == 200
    assert r.json() == ['/']

    # Asking for a sub-group on a legacy provider is a 404
    r = client.get('/datasets/legacy/groups/anything/keys')
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# SingleDatasetRest with a DataTree
# ---------------------------------------------------------------------------


def test_single_datatree_rest(simple_tree):
    rest = SingleDatasetRest(simple_tree)
    client = TestClient(rest.app)

    # Root keys (empty for our fixture)
    r = client.get('/keys')
    assert r.status_code == 200
    assert r.json() == []

    # Sub-group via the group_path route
    r = client.get('/groups/a/keys')
    assert r.status_code == 200
    assert r.json() == ['x']

    # The full tree
    r = client.get('/groups')
    assert r.status_code == 200
    assert set(r.json()) == {'/', '/a', '/a/b', '/c'}


def test_datatree_accessor(simple_tree):
    """The .rest accessor on a DataTree should expose a working app."""
    client = TestClient(simple_tree.rest.app)

    r = client.get('/groups/a/keys')
    assert r.status_code == 200
    assert r.json() == ['x']
