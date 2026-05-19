# Serving DataTrees

Xpublish treats {py:class}`xarray.DataTree` as its core data primitive. A bare
{py:class}`xarray.Dataset` is just a one-node tree under the hood, so everything
you've learned so far about serving Datasets applies unchanged when you switch
to trees.

## Serving a single DataTree

You can publish a `DataTree` directly with {class}`~xpublish.SingleDatasetRest`
or the `.rest` accessor — the API is identical to the Dataset case:

```python
import xarray as xr
import xpublish

dt = xr.DataTree(name="root")
dt["a"] = xr.DataTree(dataset=xr.Dataset({"x": ("i", [1, 2, 3])}))
dt["a/b"] = xr.DataTree(dataset=xr.Dataset({"y": ("j", [10.0, 20.0])}))

rest = xpublish.SingleDatasetRest(dt)
# or, equivalently:
dt.rest.serve()
```

## Serving a collection of trees (and datasets)

{class}`~xpublish.Rest` accepts a mapping whose values can be either
`Dataset` or `DataTree` objects in any combination:

```python
rest = xpublish.Rest(
    {
        "flat": xr.Dataset({"var": ("x", [1, 2, 3])}),
        "tree": dt,
    }
)
rest.serve()
```

The flat dataset is wrapped in a single-node tree internally, so it shows up
in the `/groups` listing as just `["/"]`.

## Navigating groups via the URL

Per-dataset routes can include an optional `{group_path:path}` segment to
navigate into a node of the tree. The included `dataset_info` plugin uses this
convention to expose group-aware variants of its endpoints:

| URL                              | What it returns                      |
| -------------------------------- | ------------------------------------ |
| `/datasets/tree/`                | HTML repr of the root node           |
| `/datasets/tree/keys`            | Variable keys at the root            |
| `/datasets/tree/groups`          | List of every group path in the tree |
| `/datasets/tree/tree`            | HTML repr of the full DataTree       |
| `/datasets/tree/groups/a/keys`   | Variable keys at the `/a` node       |
| `/datasets/tree/groups/a/b/info` | Schema info at the `/a/b` node       |

Group paths can be arbitrarily nested — the `{group_path:path}` parameter
matches across slashes. An unknown group returns a `404`.

## Dataset provider plugins for trees

The provider hook for plugins is
{py:meth}`xpublish.plugins.hooks.PluginSpec.get_datatree`. It receives both the
`dataset_id` and the requested `group` path, and returns the
{py:class}`xarray.DataTree` rooted at that group (or `None` to pass to the next
plugin). The returned tree's root corresponds to the requested group.

```{important}
``group`` must be declared as a **positional** parameter (no default) on your
hookimpl. [Pluggy](https://pluggy.readthedocs.io/) does not forward arguments
that have defaults, so a signature like ``def get_datatree(self, dataset_id, group="")``
will silently receive an empty string regardless of the URL. See the
[plugin user guide](../../user-guide/plugins.md#dataset-provider-plugins) for
details.
```

### The lazy-by-group pattern

For backends where loading the whole tree is expensive (Zarr v3, Icechunk,
remote object stores), implement `get_datatree` so it opens *only* the
requested group and wraps it in a single-node tree:

```python
import xarray as xr
from xpublish import Plugin, hookimpl


class IcechunkProvider(Plugin):
    name: str = "icechunk"

    @hookimpl
    def get_datasets(self):
        return list(self._known_repos)

    @hookimpl
    def get_datatree(self, dataset_id: str, group: str):
        store = self._store_for(dataset_id)
        if store is None:
            return None
        ds = xr.open_zarr(store, group=group or None, consolidated=False)
        return xr.DataTree(dataset=ds)
```

Each request opens just the one group being viewed, so cost stays proportional
to what's actually queried.

## Migrating from `get_dataset`

The older {py:meth}`xpublish.plugins.hooks.PluginSpec.get_dataset` hook is still
honored but emits a {py:class}`DeprecationWarning`. The Dataset it returns is
wrapped in a single-node DataTree, so only the root group is reachable through
it. Migrate to `get_datatree` to expose hierarchical data — the rename is
mechanical:

```python
# Before
@hookimpl
def get_dataset(self, dataset_id: str):
    return xr.tutorial.open_dataset(dataset_id)


# After
@hookimpl
def get_datatree(self, dataset_id: str, group: str):
    if group:
        return None  # we only serve a flat dataset
    return xr.DataTree(dataset=xr.tutorial.open_dataset(dataset_id))
```
