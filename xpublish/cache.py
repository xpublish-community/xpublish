"""A cache for datasets being served."""
import xarray as xr
from cachey import Cache


@xr.register_dataset_accessor('_rest_cache')
class RestCacheAccessor:

    def __init__(self, xarray_obj):
        self._obj = xarray_obj
        self._cache_kws = {'available_bytes': 1e6}
        self._cache = None
        self._initialized = False

    def __call__(self, cache_kws=None):
        if self._initialized:
            raise RuntimeError('This accessor has already been initialized')
        self._initialized = True

        # update kwargs
        if cache_kws is not None:
            self._cache_kws.update(cache_kws)
        return self

    @property
    def cache(self):
        """ Cache Property """
        if self._cache is None:
            self._cache = Cache(**self._cache_kws)
        return self._cache
