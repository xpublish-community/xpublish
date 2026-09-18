import collections
import contextlib
import logging
import pickle
import sys
from concurrent.futures import ThreadPoolExecutor

import cachetools
import numpy as np
import pytest
from starlette.testclient import TestClient

from xpublish import Rest
from xpublish.utils.cache import (
    CACHE_BYTES_ENV,
    CacheProtocol,
    CacheyCache,
    LockedMapping,
    SerializedMapping,
    lru_bytes_cache,
    lru_bytes_store,
    nbytes,
)


class RecordingLock:
    """A context manager that counts how many times it was entered."""

    def __init__(self):
        self.entered = 0

    def __enter__(self):
        self.entered += 1
        return self

    def __exit__(self, *args):
        return False


class CountingDict(dict):
    """A dict that records how many times each key was written."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.writes = collections.Counter()

    def __setitem__(self, key, value):
        self.writes[key] += 1
        super().__setitem__(key, value)


class OnlyGetPutCache:
    """A minimal CacheProtocol implementation with no store xpublish knows about."""

    def __init__(self):
        self.store = {}

    def get(self, key, default=None):
        """Return the cached value, or the default."""
        return self.store.get(key, default)

    def put(self, key, value, cost, nbytes=None):
        """Cache a value, ignoring the cost and size hints."""
        self.store[key] = value


def test_lru_bytes_cache_satisfies_protocol():
    assert isinstance(lru_bytes_cache(1), CacheProtocol)


def test_object_without_put_is_not_a_cache():
    class OnlyGet:
        def get(self, key, default=None):
            return default

    assert not isinstance(OnlyGet(), CacheProtocol)


def test_object_with_get_and_put_is_a_cache():
    class Custom:
        def get(self, key, default=None):
            return default

        def put(self, key, value, cost, nbytes=None):
            pass

    assert isinstance(Custom(), CacheProtocol)


def test_protocol_cannot_be_instantiated():
    with pytest.raises(TypeError):
        CacheProtocol()


def test_dict_store_round_trip():
    cache = CacheyCache({})

    cache.put('key', 'value', 1.0)

    assert cache.get('key') == 'value'


def test_miss_returns_default():
    cache = CacheyCache({})

    assert cache.get('missing') is None
    assert cache.get('missing', 'fallback') == 'fallback'


def test_store_with_broken_get_still_misses_cleanly():
    class NoGetDict(dict):
        def get(self, key, default=None):
            raise AssertionError('CacheyCache must not call mapping.get()')

    cache = CacheyCache(NoGetDict())

    assert cache.get('missing') is None

    cache.put('key', 'value', 1.0)
    assert cache.get('key') == 'value'


def test_oversize_put_is_dropped_silently():
    cache = lru_bytes_cache(10)

    cache.put('big', b'x' * 100, 1.0)

    assert cache.get('big') is None
    assert len(cache) == 0


def test_min_cost_gating():
    cache = CacheyCache({}, min_cost=0.5)

    cache.put('cheap', 'value', 0.1)
    assert cache.get('cheap') is None

    cache.put('pricey', 'value', 0.9)
    assert cache.get('pricey') == 'value'


def test_max_nbytes_gating():
    cache = CacheyCache({}, max_nbytes=4)

    cache.put('big', b'abcdefgh', 1.0)
    assert cache.get('big') is None

    cache.put('small', b'ab', 1.0)
    assert cache.get('small') == b'ab'


def test_hit_and_miss_callbacks():
    hits = []
    misses = []
    cache = CacheyCache({}, hit=hits.append, miss=misses.append)

    assert cache.get('key') is None
    assert misses == ['key']
    assert hits == []

    cache.put('key', 'value', 1.0)
    assert cache.get('key') == 'value'
    assert hits == ['key']
    assert misses == ['key']


def test_put_without_nbytes_uses_the_helper():
    store = {}
    cache = CacheyCache(store)

    cache.put('bytes', b'abc', 1.0)
    assert store['bytes'][1] == 3

    array = np.ones(10, dtype='i4')
    cache.put('array', array, 1.0)
    assert store['array'][1] == array.nbytes


def test_put_with_explicit_nbytes():
    store = {}
    cache = CacheyCache(store)

    cache.put('key', b'abc', 1.0, nbytes=1234)

    assert store['key'][1] == 1234


def test_nbytes_helper():
    assert nbytes(b'abc') == 3
    assert nbytes(bytearray(b'abcd')) == 4
    assert nbytes('hello') == 5
    assert nbytes(np.ones(5, dtype='i4')) == 20

    assert nbytes(['ab', 'cd']) >= 4
    assert nbytes(['ab', 'cd']) > nbytes([])
    assert nbytes({'a': 'bcd'}) >= 4
    assert nbytes((1, 2, 3)) > nbytes(())
    assert nbytes({'a', 'bb'}) > nbytes(set())

    assert nbytes(object()) == sys.getsizeof(object())


def test_nbytes_helper_pandas():
    pd = pytest.importorskip('pandas')

    series = pd.Series(['a string', 'another string'] * 10)

    assert nbytes(series) > 0


def test_serialized_mapping_round_trip():
    store = {}
    mapping = SerializedMapping(store)

    array = np.arange(5)
    mapping['bytes'] = b'raw'
    mapping['array'] = array
    mapping['dict'] = {'a': 1}

    assert mapping['bytes'] == b'raw'
    np.testing.assert_array_equal(mapping['array'], array)
    assert mapping['dict'] == {'a': 1}

    assert all(isinstance(value, bytes) for value in store.values())
    assert pickle.loads(store['bytes']) == b'raw'

    assert len(mapping) == 3
    assert set(mapping) == {'bytes', 'array', 'dict'}

    del mapping['bytes']
    assert 'bytes' not in mapping
    assert len(mapping) == 2


def test_serialized_mapping_backs_a_cache():
    store = {}
    cache = CacheyCache(SerializedMapping(store))

    cache.put('key', {'a': 1}, 1.0)

    assert cache.get('key') == {'a': 1}
    assert isinstance(store['key'], bytes)


def test_lock_is_acquired_by_get_and_put():
    lock = RecordingLock()
    cache = CacheyCache({}, lock=lock)

    cache.put('key', 'value', 1.0)
    assert lock.entered == 1

    cache.get('key')
    assert lock.entered == 2


def test_lock_false_disables_locking():
    cache = CacheyCache({}, lock=False)

    assert isinstance(cache._lock, contextlib.nullcontext)

    cache.put('key', 'value', 1.0)
    assert cache.get('key') == 'value'


def test_lru_bytes_cache_evicts_oldest():
    cache = lru_bytes_cache(10)

    cache.put('a', b'aaaa', 1.0)
    cache.put('b', b'bbbb', 1.0)
    cache.put('c', b'cccc', 1.0)

    assert cache.get('a') is None
    assert cache.get('b') == b'bbbb'
    assert cache.get('c') == b'cccc'
    assert cache.mapping.currsize == 8
    assert cache.mapping.maxsize == 10


def test_retire_clear_contains_and_len():
    cache = CacheyCache({})

    cache.put('a', 1, 1.0)
    cache.put('b', 2, 1.0)

    assert 'a' in cache
    assert 'z' not in cache
    assert len(cache) == 2

    cache.retire('a')
    assert 'a' not in cache
    assert len(cache) == 1

    # retiring a missing key is a no-op
    cache.retire('a')

    cache.clear()
    assert len(cache) == 0


def test_mapping_property_exposes_the_raw_store():
    store = {}
    cache = CacheyCache(store)

    assert cache.mapping is store


def test_concurrent_access_keeps_the_store_consistent():
    cache = lru_bytes_cache(1000)

    def worker(thread_id):
        for i in range(200):
            key = f'{thread_id}-{i % 25}'
            cache.put(key, b'x' * 16, 1.0)
            cache.get(key)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(worker, range(8)))

    mapping = cache.mapping
    assert mapping.currsize <= mapping.maxsize
    assert mapping.currsize == sum(value[1] for value in mapping.values())


def test_locked_mapping_round_trip():
    mapping = LockedMapping({})

    mapping['key'] = 'value'
    assert mapping['key'] == 'value'
    assert 'key' in mapping
    assert len(mapping) == 1

    del mapping['key']
    assert 'key' not in mapping
    assert len(mapping) == 0


def test_locked_mapping_key_error_on_miss():
    mapping = LockedMapping({})

    with pytest.raises(KeyError):
        mapping['missing']


def test_locked_mapping_forwards_attributes_from_the_inner_store():
    inner = cachetools.LRUCache(maxsize=10, getsizeof=lambda item: item[1])
    mapping = LockedMapping(inner)

    assert mapping.maxsize == 10

    mapping['a'] = ('x', 4)
    assert mapping.currsize == 4


def test_locked_mapping_guards_against_recursion_before_init():
    mapping = LockedMapping.__new__(LockedMapping)

    with pytest.raises(AttributeError):
        _ = mapping.maxsize


def test_locked_mapping_acquires_the_lock():
    lock = RecordingLock()
    mapping = LockedMapping({}, lock=lock)

    mapping['key'] = 'value'
    assert lock.entered == 1

    assert mapping['key'] == 'value'
    assert lock.entered == 2

    assert 'key' in mapping
    assert lock.entered == 3

    assert len(mapping) == 1
    assert lock.entered == 4

    del mapping['key']
    assert lock.entered == 5


def test_locked_mapping_iter_is_a_snapshot_safe_to_mutate_during():
    mapping = LockedMapping({'a': 1, 'b': 2, 'c': 3})

    seen = []
    for key in mapping:
        seen.append(key)
        del mapping[key]

    assert set(seen) == {'a', 'b', 'c'}
    assert len(mapping) == 0


def test_locked_mapping_oversize_value_error_propagates():
    inner = cachetools.LRUCache(maxsize=10, getsizeof=lambda item: item[1])
    mapping = LockedMapping(inner)

    with pytest.raises(ValueError):
        mapping['big'] = ('x', 100)


def test_cacheycache_swallows_the_locked_mappings_oversize_error():
    cache = CacheyCache(lru_bytes_store(10))

    cache.put('big', b'x' * 100, 1.0)

    assert cache.get('big') is None
    assert len(cache) == 0


def test_cacheycache_shares_the_locked_mappings_lock():
    mapping = LockedMapping({})
    cache = CacheyCache(mapping)

    assert cache._lock is mapping.lock


def test_lru_bytes_cache_builds_a_locked_mapping():
    assert isinstance(lru_bytes_cache(10).mapping, LockedMapping)


def test_locked_mapping_concurrent_access_stays_consistent():
    store = lru_bytes_store(1000)
    cache = CacheyCache(store)

    def worker(thread_id):
        for i in range(200):
            key = f'{thread_id}-{i % 25}'
            if thread_id % 2 == 0:
                store[key] = (b'x' * 16, 16)
            else:
                cache.put(key, b'x' * 16, 1.0)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(worker, range(8)))

    assert store.currsize <= store.maxsize
    assert store.currsize == sum(value[1] for value in store.mapping.values())


def test_cache_kwarg_accepts_a_mapping(airtemp_ds):
    store = {}
    rest = Rest({'airtemp': airtemp_ds}, cache=store)

    client = TestClient(rest.app)
    assert client.get('/datasets/airtemp/info').status_code == 200

    assert 'airtemp/info' in store
    assert isinstance(rest.cache, CacheyCache)
    assert rest.cache_store is store


def test_cache_kwarg_accepts_a_cache_protocol(airtemp_ds):
    custom = OnlyGetPutCache()
    rest = Rest({'airtemp': airtemp_ds}, cache=custom)

    assert rest.cache is custom
    assert rest.dependencies().cache() is custom

    assert isinstance(rest.cache_store, LockedMapping)
    assert rest.cache_store is rest.cache_store
    assert rest.cache_store is not custom
    assert rest.dependencies().cache_store() is rest.cache_store

    client = TestClient(rest.app)
    assert client.get('/datasets/airtemp/info').status_code == 200
    assert 'airtemp/info' in custom.store


def test_cache_kwarg_rejects_other_objects(airtemp_ds):
    rest = Rest({'airtemp': airtemp_ds}, cache=object())

    with pytest.raises(TypeError, match='CacheProtocol'):
        _ = rest.cache


def test_cache_and_cache_kws_are_mutually_exclusive(airtemp_ds):
    with pytest.raises(ValueError, match='cache_kws'):
        Rest({'airtemp': airtemp_ds}, cache={}, cache_kws={'available_bytes': 999})


def test_cache_store_dependency_matches_the_default_cache(airtemp_ds):
    rest = Rest({'airtemp': airtemp_ds})

    assert rest.dependencies().cache_store() is rest.cache.mapping


def test_cache_kwarg_via_the_accessor(airtemp_ds):
    store = cachetools.LRUCache(maxsize=1e6, getsizeof=lambda item: item[1])
    accessor = airtemp_ds.copy().rest(cache=store)

    assert accessor.cache.mapping is store

    client = TestClient(accessor.app)
    assert client.get('/info').status_code == 200
    assert '/info' in store


def test_cache_kwarg_with_a_mapping_ignores_the_env_var(airtemp_ds, monkeypatch, caplog):
    monkeypatch.setenv(CACHE_BYTES_ENV, '12345')
    store = {}

    with caplog.at_level(logging.WARNING, logger='xpublish.rest'):
        rest = Rest({'airtemp': airtemp_ds}, cache=store)

    assert CACHE_BYTES_ENV in caplog.text
    assert rest.cache.mapping is store


def test_cache_kwarg_with_a_protocol_object_sizes_the_fallback_store_from_the_env_var(
    airtemp_ds, monkeypatch, caplog
):
    monkeypatch.setenv(CACHE_BYTES_ENV, '12345')
    custom = OnlyGetPutCache()

    with caplog.at_level(logging.INFO, logger='xpublish.rest'):
        rest = Rest({'airtemp': airtemp_ds}, cache=custom)

    assert rest.cache_store.maxsize == 12345
    assert CACHE_BYTES_ENV in caplog.text


def test_cache_kwarg_with_a_protocol_object_and_a_bad_env_value_raises(airtemp_ds, monkeypatch):
    monkeypatch.setenv(CACHE_BYTES_ENV, 'not-a-number')

    with pytest.raises(ValueError, match=CACHE_BYTES_ENV):
        Rest({'airtemp': airtemp_ds}, cache=OnlyGetPutCache())


def test_two_apps_can_share_one_store(airtemp_ds):
    store = CountingDict()

    for _ in range(2):
        rest = Rest({'airtemp': airtemp_ds}, cache=store)
        client = TestClient(rest.app)
        assert client.get('/datasets/airtemp/info').status_code == 200

    assert store.writes['airtemp/info'] == 1
