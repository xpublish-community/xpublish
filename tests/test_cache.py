import cachey
import pytest

from xpublish.utils.cache import CacheProtocol


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
