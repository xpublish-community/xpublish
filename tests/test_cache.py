import contextlib
import pickle
import sys
from concurrent.futures import ThreadPoolExecutor

import cachey
import numpy as np
import pytest

from xpublish.utils.cache import (
    CacheProtocol,
    CacheyCache,
    SerializedMapping,
    lru_bytes_cache,
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


def test_cachey_cache_satisfies_protocol():
    assert isinstance(cachey.Cache(available_bytes=1), CacheProtocol)


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


def test_cachey_cache_satisfies_the_protocol():
    assert isinstance(lru_bytes_cache(1000), CacheProtocol)


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
