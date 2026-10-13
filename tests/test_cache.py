# ruff: noqa: D101, D102
import logging
import time

import cachetools
import numpy as np
import pytest

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
