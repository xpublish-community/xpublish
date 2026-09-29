# Caching

Xpublish's caching system is built on top of [cachetools](https://cachetools.readthedocs.io/en/latest/) allowing an extendable shared cache to be adapted by different plugins. It is
a small, in-process, least-recently-used cache by default, but it can be
pointed at a shared store such as [redis](https://zx80.github.io/cachetools-utils/DOCUMENTATION/#rediscache).

## How plugins use the cache

Plugins reach the cache through {py:meth}`xpublish.Dependencies.cache`, allowing the application to override it.

```python
from fastapi import APIRouter, Depends
from xpublish import Dependencies, Plugin, hookimpl
from xpublish.utils.api import DATASET_ID_ATTR_KEY
from xpublish.utils.cache import CostTimer


class MeanPlugin(Plugin):
    name: str = "mean"

    @hookimpl
    def dataset_router(self, deps: Dependencies):
        router = APIRouter()

        @router.get("/mean/{var}")
        def mean(var: str, ds=Depends(deps.dataset), cache=Depends(deps.cache)):
            cache_key = f"{ds.attrs.get(DATASET_ID_ATTR_KEY, '')}/mean/{var}"

            result = cache.get(cache_key)
            if result is None:
                with CostTimer() as ct:
                    result = float(ds[var].mean())

                cache.put(cache_key, result, ct.time)

            return result

        return router
```

A few conventions are worth following:

- **Namespace your keys with the dataset id.** Every dataset served by an
  application shares one cache, so prefix keys with
  `ds.attrs[DATASET_ID_ATTR_KEY]` (the built-in `/info` route uses
  `<dataset_id>/info`). Include anything else that changes the result, such as
  a group path or query parameters. While Xpublish by default will set `DATASET_ID_ATTR_KEY` to the `<dataset_id>` in the URL, dataset provider plugins can explicitly set the ID. This allows dataset provider plugins to expire a dataset's caches by generating a new `DATASET_ID_ATTR_KEY` when a dataset is updated.
- **Time the work with {py:class}`xpublish.utils.cache.CostTimer`.** The
  elapsed time is a reasonable `cost` to pass to `put`.
- **Always handle a miss.** A cache is free to drop or refuse any value. It may
  be evicted to stay inside its budget, be too large to ever fit, or have
  expired. `get` returning `None` right after a `put` is normal, so never treat
  the cache as storage.

The core {py:class}`xpublish.CacheProtocol` API is tiny:

```python
cache.get(key, default=None)
cache.put(key, value, cost, nbytes=None)
```

`nbytes` is optional; when it is not given, xpublish measures the value itself.
Pass it when you already know the size (it saves a walk over large containers).

## Configuring the cache size

The default cache holds 1 MB of values and evicts the least recently used
ones to stay inside that budget.

The `XPUBLISH_CACHE_BYTES` environment variable resizes that default cache
without changing code, which is handy for tuning a deployment:

```console
$ XPUBLISH_CACHE_BYTES=1e8 python serve.py
```

To size it in code instead, pass `cache=`:

```python
rest = xpublish.Rest(datasets, cache=xpublish.lru_bytes_store(1e8))
```

`XPUBLISH_CACHE_BYTES` does not apply when `cache=` is given: xpublish then
has no store of its own left to size, and logs that the variable is being
ignored.

To change the cache in any other way, supply your own store.

```{deprecated} 0.6.0
`cache_kws={"available_bytes": ...}` still works but emits a `FutureWarning`.
Use `cache=xpublish.lru_bytes_store(available_bytes)` or
`XPUBLISH_CACHE_BYTES` instead.
```

## Supplying your own store

`cache=` takes a {py:class}`collections.abc.MutableMapping` to keep values
in. It is mutually exclusive with `cache_kws`.

A mapping is wrapped in {py:class}`xpublish.CacheyCache`, which stores values
as {py:class}`xpublish.CacheEntry` instances carrying their measured size.
{py:func}`xpublish.entry_size` reads that size back off a `CacheEntry`, and
measures anything else with `nbytes`, so a `cachetools` cache should be built
with `getsizeof=entry_size`:

```python
import cachetools
import xpublish
from xpublish import LockedMapping, entry_size

cache = LockedMapping(cachetools.LRUCache(maxsize=1e8, getsizeof=entry_size))
rest = xpublish.Rest(datasets, cache=cache)
```

Other `cachetools` policies work the same way. A `TTLCache` expires entries
after a fixed time, which is useful when the underlying data is updated in
place:

```python
cache = LockedMapping(cachetools.TTLCache(maxsize=1e8, ttl=300, getsizeof=entry_size))
rest = xpublish.Rest(datasets, cache=cache)
```

The accessor takes the same keyword:

```python
ds.rest(cache=cache)
```

```{warning}
Mappings passed via `cache=` are used exactly as given. FastAPI runs sync
endpoints in a thread pool, and `cachetools` caches (like most mappings) are
not thread-safe, so wrap the store in {py:class}`xpublish.LockedMapping`, as
above, before passing it — {py:class}`xpublish.CacheyCache` then shares its
lock rather than adding a second one. [CacheToolsUtils'
`LockedCache`](https://zx80.github.io/cachetools-utils/DOCUMENTATION/#lockedcache)
also works.
```

### Cost-aware eviction

{py:class}`xpublish.CacheEntry` carries the `cost` passed to `put` alongside
the measured size, so a custom `cachetools` cache can score evictions by cost
per byte instead of by recency. A raw value written directly to the store
(rather than through {py:class}`xpublish.CacheyCache`) carries no cost, since
it never passed through `put`.

```python
import cachetools
from xpublish import CacheEntry, CacheyCache, LockedMapping, entry_size


class CostAwareCache(cachetools.Cache):
    """Evicts the entry with the lowest cost per byte."""

    def popitem(self):
        def cost_per_byte(key):
            entry = self[key]
            cost = entry.cost if isinstance(entry, CacheEntry) else 0
            size = entry.nbytes if isinstance(entry, CacheEntry) else entry_size(entry)
            return cost / max(size, 1)

        key = min(self, key=cost_per_byte)
        return key, self.pop(key)


cache = LockedMapping(CostAwareCache(maxsize=1e8, getsizeof=entry_size))
rest = xpublish.Rest(datasets, cache=cache)
```

This is how to get cachey-like cost-scored eviction back: pass a real `cost`
to `put` (for instance from {py:class}`xpublish.utils.cache.CostTimer`), and
let a `CacheEntry`-aware `popitem` make eviction decisions from it.

### Sharing a cache between processes

For a store shared by several workers, wrap a network cache in
{py:class}`xpublish.SerializedMapping`.

Cached values are arbitrary Python
objects, so they have to be serialized on the way into a byte store, and the
Redis wrapper has to be told to hand back raw bytes:

```python
import cachetools
import redis
from CacheToolsUtils import PrefixedRedisCache, TwoLevelCache
from xpublish import LockedMapping, SerializedMapping, entry_size

local = LockedMapping(cachetools.LRUCache(maxsize=1e8, getsizeof=entry_size))
shared = SerializedMapping(
    PrefixedRedisCache(redis.Redis(...), "xpublish:", ttl=300, raw=True)
)

rest = xpublish.Rest(datasets, cache=TwoLevelCache(local, shared, resilient=True))
```

Neither [CacheToolsUtils](https://pypi.org/project/CacheToolsUtils/) nor
[redis](https://pypi.org/project/redis/) is an xpublish dependency; install
them yourself if you want this. `resilient=True` keeps the application serving
from the local cache if Redis becomes unreachable.

## Cache provider plugins

A plugin can supply the store instead, through the
{py:meth}`xpublish.plugins.hooks.PluginSpec.get_cache` hook. This is how a
deployment-specific plugin can give every xpublish application in an
organization the same Redis-backed cache without each one configuring it:

```python
import cachetools
import redis
from CacheToolsUtils import PrefixedRedisCache, TwoLevelCache
from xpublish import LockedMapping, SerializedMapping, Plugin, entry_size, hookimpl


class RedisCachePlugin(Plugin):
    name: str = "redis-cache"

    @hookimpl
    def get_cache(self, available_bytes: float):
        local = LockedMapping(
            cachetools.LRUCache(maxsize=available_bytes, getsizeof=entry_size)
        )
        shared = SerializedMapping(
            PrefixedRedisCache(redis.Redis(...), "xpublish:", ttl=300, raw=True)
        )
        two_level = TwoLevelCache(local, shared, resilient=True)
        return two_level
```

The hook receives the resolved cache size, including any
`XPUBLISH_CACHE_BYTES` override, so a provider can honour the configured size.

Returning `None` defers to the next plugin, and then to the default cache. An
explicit `cache=` takes priority over a plugin.

```{warning}
Mappings returned from `get_cache` are used exactly as given, with the same
thread-safety caveat as `cache=`: wrap the store in
{py:class}`xpublish.LockedMapping` (or CacheToolsUtils' `LockedCache`) before
returning it, for example
`return LockedMapping(cachetools.TTLCache(maxsize=available_bytes, ttl=300, getsizeof=entry_size))`.
```

## Layering your own policy

{py:meth}`xpublish.Dependencies.cache_store` hands a plugin the raw mapping
behind the application cache, for plugins that want their own policy over the
shared store.

Wrapping the store in a `PrefixedCache` keeps a plugin's keys from
colliding with other plugins. There are two ways to use the prefixed view.

**Route 1: cost-aware, with `get`/`put`.** Wrap it in
{py:class}`xpublish.CacheyCache` when you want to time the work and pass that
cost along, or when you want misses handled explicitly:

```python
from CacheToolsUtils import PrefixedCache
from xpublish import CacheyCache
from xpublish.utils.cache import CostTimer


@hookimpl
def dataset_router(self, deps: Dependencies):
    router = APIRouter()

    @router.get("/tiles/{z}/{x}/{y}")
    def tile(z: int, x: int, y: int, store=Depends(deps.cache_store)):
        tile_cache = CacheyCache(PrefixedCache(store, "tiles:"))

        tile_data = tile_cache.get(f"{z}/{x}/{y}")
        if tile_data is None:
            with CostTimer() as ct:
                tile_data = render_tile(z, x, y)

            tile_cache.put(f"{z}/{x}/{y}", tile_data, ct.time)

        return tile_data

    return router
```

**Route 2: a plain `cachetools` decorator.** The stores xpublish builds accept
raw values directly — they are sized with `nbytes` rather than needing the
`CacheyCache`/`CacheEntry` convention — so `cachetools.cached` can decorate
the render function itself:

```python
import cachetools
from CacheToolsUtils import PrefixedCache


@hookimpl
def dataset_router(self, deps: Dependencies):
    router = APIRouter()

    @router.get("/tiles/{z}/{x}/{y}")
    def tile(z: int, x: int, y: int, store=Depends(deps.cache_store)):
        prefixed = PrefixedCache(store, "tiles:")

        @cachetools.cached(prefixed, key=lambda z, x, y: f"{z}/{x}/{y}")
        def render(z: int, x: int, y: int):
            return render_tile(z, x, y)

        return render(z, x, y)

    return router
```

Always pass `key=` here. `cachetools`' default key is built from the call
arguments alone, so two decorated functions called with the same arguments
share an entry in the store. It also isn't a string, which a Redis-backed
store needs. `LockedMapping` already serializes access to the underlying
store, so `cached` needs no `lock=`.

In both routes the work happens outside the lock, so two concurrent misses for
the same tile may both compute it. The second write just overwrites the first.

Stores xpublish builds, including the default cache's store, are sized with
{py:func}`xpublish.entry_size`, so they accept both routes' entries: the
{py:class}`xpublish.CacheEntry` instances {py:class}`xpublish.CacheyCache`
writes, and raw values written by anything else. If you build your own store
with a custom `getsizeof`, it must handle both cases too.

`cache_store` is always the store behind `deps.cache`, and stores that
xpublish builds are thread-safe.

## Caching and multiple workers

The default cache lives in one process. Running several uvicorn workers gives
each its own cache, so the same request can be computed once per worker and the
total memory used is the configured size times the number of workers. That is
usually fine, but if it is not:

- Give every worker the same shared store (the Redis example above). Eviction
  is then the store's job — set Redis' `maxmemory` and an eviction policy, and
  use a TTL, rather than expecting xpublish to manage the size.
- Or put the caching in front of the application instead.

An HTTP cache — a CDN, a reverse proxy such as nginx or Varnish, or a browser
honouring the `Cache-Control` headers your routes set — avoids the work
entirely for repeated requests and is often the cheapest win. At the other end,
the storage layer has its own caching: a cloud-backed Zarr store read through
`fsspec` can be given a caching filesystem, and a well-chunked dataset reduces
how much has to be read in the first place. The xpublish cache sits between the
two and is best used for results that are expensive to compute and small to
keep.

## Migrating from cachey

Earlier releases of xpublish used a `cachey.Cache`. The replacement is a
`cachetools` LRU cache with the same `get`/`put` interface, so plugins do not
need to change. Three things did:

- **Eviction is by bytes and recency, not by score.** Cachey kept whatever
  scored best on a cost/size/recency heuristic; the default cache now simply
  evicts the least recently used values to stay within `available_bytes`. The
  `cost` argument to `put` is still accepted and is still worth passing (a
  custom store may use it), but the default cache ignores it. See
  [Cost-aware eviction](#cost-aware-eviction) above for how to get
  cachey-like cost-scored eviction back.
- **Cachey-only `cache_kws` raise `TypeError`.** Options such as `halflife`,
  `nbytes` and `limit` no longer exist. `available_bytes` is the only one left;
  use `cache=` for anything more specific. `cache_kws` itself is now
  deprecated — see [Configuring the cache size](#configuring-the-cache-size)
  above.
- **{py:class}`xpublish.CacheProtocol` replaces `cachey.Cache` in annotations.**
  Plugins that used to annotate a cache parameter as `cachey.Cache` should use
  {py:class}`xpublish.CacheProtocol` instead.
