# Caching

Xpublish orchastrates caching for plugins, allowing them to share a remote cache or fall back to a built in `cachetools` implementations.

A cache is a namespaced {py:class}`collections.abc.MutableMapping` with LRU or time-based eviction, usable directly or with `@cachetools.cached(...)`.

## Requesting a cache

Call `deps.get_lru_cache` or `deps.get_ttl_cache` from a plugin hook. The
namespace is required; plugins normally pass their own `name`.

```python
import xpublish
from xpublish import Plugin, hookimpl


class Meshes(Plugin):
    name: str = "meshes"

    @hookimpl
    def dataset_router(self, deps):
        # LRU limited to 1 GiB of values
        mesh_cache = deps.get_lru_cache(
            self.name, maxsize=2**30, getsizeof=xpublish.nbytes
        )
        # entries expire after five minutes
        crs_cache = deps.get_ttl_cache("proj", maxsize=64, ttl=300)
        ...
```

- `deps.get_lru_cache(namespace, maxsize=128, *, getsizeof=None)`
- `deps.get_ttl_cache(namespace, maxsize=128, ttl=600, *, getsizeof=None)`

These are plain callables, rather than FastAPI dependencies: call them while building
the router, not through `Depends(...)`. Calls are memoized per
`(kind, namespace)`, so repeated calls return the same cache. Asking again
with different parameters logs a warning and returns the existing cache.

Plugins can pass the same namespace to share a cache. By default each cache is a thread-safe
({py:class}`xpublish.LockedMapping`) `cachetools` cache local to the process.

```{note}
Providers (below) may serialize values and may ignore `maxsize` and
`getsizeof`. Portable plugins should cache picklable values and not depend on
exact eviction.
```

## Using a cache

Request the cache once in the router hook, then close over it in your
endpoints.

<details><summary>The examples below all use the same imports:</summary>

```python
import threading

import cachetools
import xarray as xr
from fastapi import APIRouter, Depends

import xpublish
from xpublish import Dependencies, Plugin, hookimpl
from xpublish.utils.api import DATASET_ID_ATTR_KEY
```

</details>

### Look-aside caching per dataset

Check the cache, compute on a miss, then store the result.

Include the dataset ID in the key from `dataset.attrs[DATASET_ID_ATTR_KEY]` so that the caches are invalidated by dataset changes.

```python
class Summary(Plugin):
    name: str = "summary"

    @hookimpl
    def dataset_router(self, deps: Dependencies):
        router = APIRouter(prefix="/summary")
        # up to 64 MiB of results
        cache = deps.get_lru_cache(
            self.name, maxsize=2**26, getsizeof=xpublish.nbytes
        )

        @router.get("/{variable}")
        def summary(variable: str, dataset: xr.Dataset = Depends(deps.dataset)):
            key = f"{dataset.attrs[DATASET_ID_ATTR_KEY]}/{variable}"
            result = cache.get(key)
            if result is None:
                da = dataset[variable]
                result = {"min": float(da.min()), "max": float(da.max())}
                try:
                    cache[key] = result
                except ValueError:
                    pass  # larger than maxsize; serve it uncached
            return result

        return router
```

### Decorating a function with `cachetools.cached`

The caches work with `cachetools`' decorators. Each read and write is
already thread-safe. Passing a `lock` as well stops concurrent requests from
computing the same value twice.

```python
class Stats(Plugin):
    name: str = "stats"

    @hookimpl
    def dataset_router(self, deps: Dependencies):
        router = APIRouter(prefix="/stats")
        cache = deps.get_lru_cache(self.name, maxsize=256)

        @cachetools.cached(
            cache,
            key=lambda dataset, variable: f"{dataset.attrs[DATASET_ID_ATTR_KEY]}/{variable}/mean",
            lock=threading.Lock(),
        )
        def mean(dataset: xr.Dataset, dataset_id: str, variable: str) -> float:
            return float(dataset[variable].mean())

        @router.get("/{variable}/mean")
        def get_mean(variable: str, dataset: xr.Dataset = Depends(deps.dataset)):
            return {"mean": mean(dataset, variable)}

        return router
```

Prefer string keys, like the `key=` function above. Remote providers usually
turn keys into strings, so the default `cachetools` tuple keys may not
round-trip.

### Expiring values with a TTL cache

Use `get_ttl_cache` for values that go stale, such as responses from a remote
catalog or metadata service.

```python
import httpx


class RemoteCatalog(Plugin):
    name: str = "remote_catalog"

    @hookimpl
    def app_router(self, deps: Dependencies):
        router = APIRouter(prefix="/remote")
        # refetch at most every five minutes
        cache = deps.get_ttl_cache(self.name, maxsize=32, ttl=300)

        @cachetools.cached(cache)
        def fetch(url: str) -> dict:
            return httpx.get(url).json()

        @router.get("/")
        def get_remote(url: str):
            return fetch(url)

        return router
```

### Sharing a cache between plugins

Plugins that request the same kind of cache under the same namespace get the
same instance. Agree on the namespace and its parameters, because the first
request decides `maxsize`, `ttl` and `getsizeof`:

```python
# in plugin A and in plugin B
transformers = deps.get_ttl_cache("pyproj_transformers", maxsize=64, ttl=3600)
```

LRU and TTL caches never collide, even under the same namespace.

### Testing

Outside a `Rest` app, the default `Dependencies()` returns a fresh, unshared
cache on every call, so router hooks still work in unit tests. To inspect the
cache an app is using, request it again from `Rest.dependencies()` with the same
parameters:

```python
rest = xpublish.Rest({"air": ds}, plugins={"summary": Summary()})
client = TestClient(rest.app)
client.get("/datasets/air/summary/air")

cache = rest.dependencies().get_lru_cache(
    "summary", maxsize=2**26, getsizeof=xpublish.nbytes
)
assert "air/air" in cache
```

## Writing a cache provider

A plugin can back caches with something else, for example Redis, by
implementing the `get_lru_cache` and `get_ttl_cache` hooks. They are
`firstresult` hooks: return a mutable mapping, or `None` to decline, in which
case the next provider and finally the built-in local cache is used. A
provider owns its own memoization.

```python
class MyProvider(Plugin):
    name: str = "my_provider"

    @hookimpl
    def get_lru_cache(self, namespace, maxsize, getsizeof):
        return my_mapping_for(namespace)

    @hookimpl
    def get_ttl_cache(self, namespace, maxsize, ttl, getsizeof):
        return my_mapping_for(namespace, ttl=ttl)
```

See the `xpublish-redis-cache` plugin for a complete example.

## Migrating from `deps.cache`

`deps.cache` and `Rest.cache` (a cachey-style `get(key)` / `put(key, value, cost)`
interface) are deprecated and emit a `DeprecationWarning`. They are now backed
by the `xpublish` LRU namespace and ignore `cost`. Replace them with:

```python
cache = deps.get_lru_cache(self.name, maxsize=2**24, getsizeof=xpublish.nbytes)
value = cache.get(key)
if value is None:
    value = compute()
    cache[key] = value
```

`cachetools` raises `ValueError` for a single value larger than `maxsize`;
catch it if the value may not fit. `cache_kws={'available_bytes': ...}` is still
honored for the legacy cache; other keys are ignored.
