# ruff: noqa: D101, D102
import logging
import time
import warnings

import cachetools
import numpy as np
import pytest
import xarray as xr

from xpublish import LockedMapping, Plugin, Rest, hookimpl, nbytes


def make_rest(plugins=None):
    return Rest({}, plugins=plugins if plugins is not None else {})


def test_nbytes():
    assert nbytes(b'abcd') == 4
    assert nbytes('héllo') == len('héllo'.encode())
    assert nbytes(np.zeros(10)) == 80
    assert nbytes({'a': np.zeros(10)}) > 80
    assert nbytes([np.zeros(10), np.zeros(10)]) > 160
    assert nbytes(object()) > 0


def test_locked_mapping():
    inner = cachetools.LRUCache(maxsize=2)
    locked = LockedMapping(inner)
    locked['a'] = 1
    locked['b'] = 2
    assert locked['a'] == 1
    assert 'a' in locked
    assert len(locked) == 2
    assert sorted(locked) == ['a', 'b']
    assert locked.maxsize == 2
    assert locked.mapping is inner
    del locked['a']
    assert 'a' not in locked
    with pytest.raises(AttributeError):
        getattr(locked, '_nope')  # noqa: B009


def test_fallback_is_memoized():
    rest = make_rest()
    a = rest._get_cache('lru', 'ns', maxsize=4)
    b = rest._get_cache('lru', 'ns', maxsize=4)
    assert a is b
    assert isinstance(a, LockedMapping)
    assert isinstance(a.mapping, cachetools.LRUCache)


def test_lru_and_ttl_with_same_namespace_are_separate():
    rest = make_rest()
    lru = rest._get_cache('lru', 'ns', maxsize=4)
    ttl = rest._get_cache('ttl', 'ns', maxsize=4, ttl=10)
    assert lru is not ttl
    assert isinstance(ttl.mapping, cachetools.TTLCache)
    lru['k'] = 1
    assert 'k' not in ttl


def test_different_namespaces_are_isolated():
    rest = make_rest()
    a = rest._get_cache('lru', 'a', maxsize=4)
    b = rest._get_cache('lru', 'b', maxsize=4)
    a['k'] = 1
    assert 'k' not in b


def test_param_mismatch_warns_and_first_wins(caplog):
    rest = make_rest()
    first = rest._get_cache('lru', 'ns', maxsize=4)
    with caplog.at_level(logging.WARNING):
        second = rest._get_cache('lru', 'ns', maxsize=8)
    assert second is first
    assert first.maxsize == 4
    assert 'ns' in caplog.text


def test_getsizeof_is_used():
    rest = make_rest()
    cache = rest._get_cache('lru', 'sized', maxsize=100, getsizeof=nbytes)
    cache['small'] = b'x' * 60
    cache['other'] = b'x' * 60
    assert 'small' not in cache
    assert 'other' in cache


def test_ttl_expiry(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(time, 'monotonic', lambda: now[0])
    rest = make_rest()
    cache = rest._get_cache('ttl', 'ns', maxsize=4, ttl=10)
    cache['k'] = 1
    now[0] += 5
    assert cache['k'] == 1
    now[0] += 6
    assert 'k' not in cache


class DictProvider(Plugin):
    name: str = 'dict_provider'
    decline: bool = False

    @hookimpl
    def get_lru_cache(self, namespace, maxsize, getsizeof):
        if self.decline:
            return None
        return {'provider': 'lru', 'namespace': namespace, 'maxsize': maxsize}

    @hookimpl
    def get_ttl_cache(self, namespace, maxsize, ttl, getsizeof):
        if self.decline:
            return None
        return {'provider': 'ttl', 'namespace': namespace, 'ttl': ttl}


def test_provider_wins():
    rest = make_rest({'p': DictProvider()})
    lru = rest._get_cache('lru', 'ns', maxsize=4, getsizeof=None)
    ttl = rest._get_cache('ttl', 'ns', maxsize=4, ttl=7, getsizeof=None)
    assert lru == {'provider': 'lru', 'namespace': 'ns', 'maxsize': 4}
    assert ttl == {'provider': 'ttl', 'namespace': 'ns', 'ttl': 7}


def test_provider_declining_falls_through():
    rest = make_rest({'p': DictProvider(decline=True)})
    cache = rest._get_cache('lru', 'ns', maxsize=4, getsizeof=None)
    assert isinstance(cache, LockedMapping)
    assert rest._get_cache('lru', 'ns', maxsize=4, getsizeof=None) is cache


# deps wiring


def test_dependencies_defaults_work_outside_rest():
    from xpublish import Dependencies

    deps = Dependencies()
    lru = deps.get_lru_cache('ns', maxsize=2)
    ttl = deps.get_ttl_cache('ns', maxsize=2, ttl=1)
    lru['a'] = 1
    ttl['a'] = 1
    assert lru['a'] == 1
    assert ttl['a'] == 1
    # unshared
    assert deps.get_lru_cache('ns', maxsize=2) is not lru


def test_rest_dependencies_hand_out_memoized_caches():
    rest = make_rest()
    deps = rest.dependencies()
    assert deps.get_lru_cache('ns', maxsize=3) is deps.get_lru_cache('ns', maxsize=3)
    assert deps.get_lru_cache('ns', maxsize=3) is rest.dependencies().get_lru_cache('ns', maxsize=3)
    ttl = deps.get_ttl_cache('ns', maxsize=3, ttl=5)
    assert ttl is not deps.get_lru_cache('ns', maxsize=3)
    assert ttl.mapping.ttl == 5


def test_default_arguments():
    deps = make_rest().dependencies()
    assert deps.get_lru_cache('d').maxsize == 128
    ttl = deps.get_ttl_cache('d')
    assert ttl.maxsize == 128
    assert ttl.ttl == 600


class CachingPlugin(Plugin):
    name: str = 'caching'
    namespace: str = 'caching'
    cache_name: str = 'mine'

    @hookimpl
    def dataset_router(self, deps):
        from fastapi import APIRouter

        cache = deps.get_lru_cache(self.namespace, maxsize=10)
        router = APIRouter()

        @router.get('/hit')
        def hit() -> dict:
            cache['n'] = cache.get('n', 0) + 1
            return {'n': cache['n']}

        return router


class OtherCachingPlugin(CachingPlugin):
    name: str = 'other'

    @hookimpl
    def dataset_router(self, deps):
        from fastapi import APIRouter

        cache = deps.get_lru_cache(self.namespace, maxsize=10)
        router = APIRouter()

        @router.get('/peek')
        def peek() -> dict:
            return {'n': cache.get('n', 0)}

        return router


def test_plugins_share_a_namespace():
    from fastapi.testclient import TestClient

    rest = Rest(
        {'ds': xr.Dataset()},
        plugins={'a': CachingPlugin(), 'b': OtherCachingPlugin()},
    )
    client = TestClient(rest.app)
    client.get('/datasets/ds/hit')
    assert client.get('/datasets/ds/hit').json() == {'n': 2}
    assert client.get('/datasets/ds/peek').json() == {'n': 2}


def test_plugins_with_different_namespaces_are_isolated():
    from fastapi.testclient import TestClient

    rest = Rest(
        {'ds': xr.Dataset()},
        plugins={'a': CachingPlugin(), 'b': OtherCachingPlugin(namespace='other')},
    )
    client = TestClient(rest.app)
    client.get('/datasets/ds/hit')
    assert client.get('/datasets/ds/peek').json() == {'n': 0}


# legacy deps.cache


def test_legacy_cache_warns_once(fresh_legacy_warning):
    rest = make_rest()
    with pytest.warns(DeprecationWarning, match='get_lru_cache'):
        cache = rest.cache
    assert rest.cache is cache
    with warnings.catch_warnings():
        warnings.simplefilter('error')
        assert make_rest().cache is not None


def test_legacy_cache_get_put(fresh_legacy_warning):
    rest = make_rest()
    with pytest.warns(DeprecationWarning):
        cache = rest.cache
    assert cache.get('k') is None
    assert cache.get('k', 'dflt') == 'dflt'
    cache.put('k', 'v', 123)
    assert cache.get('k') == 'v'
    # lives in the shared 'xpublish' LRU namespace
    assert (
        rest._get_cache('lru', 'xpublish', maxsize=cache.available_bytes, getsizeof=nbytes)['k']
        == 'v'
    )


def test_legacy_cache_honors_available_bytes_and_drops_large(fresh_legacy_warning):
    rest = Rest({}, plugins={}, cache_kws={'available_bytes': 100})
    with pytest.warns(DeprecationWarning):
        cache = rest.cache
    assert cache.available_bytes == 100
    cache.put('big', b'x' * 1000, 1)
    assert cache.get('big') is None
    cache.put('small', b'x' * 10, 1)
    assert cache.get('small') == b'x' * 10


def test_legacy_cache_ignores_other_kws_with_warning(fresh_legacy_warning, caplog):
    with caplog.at_level(logging.WARNING):
        rest = Rest({}, plugins={}, cache_kws={'available_bytes': 100, 'cost_threshold': 5})
    assert 'cost_threshold' in caplog.text
    with pytest.warns(DeprecationWarning):
        assert rest.cache.available_bytes == 100
