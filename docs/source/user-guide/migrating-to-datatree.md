# Upgrading to the DataTree API

Xpublish now treats {py:class}`xarray.DataTree` as its core data primitive. A
bare {py:class}`xarray.Dataset` is wrapped in a single-node tree internally,
so **existing flat-dataset deployments and plugins keep working unchanged**.
Nothing is deprecated. The notes below cover the new capabilities you can opt
into.

## For server administrators

This upgrade is transparent. Existing URLs, plugin loading, and configuration
all behave the same. There are two new things you may want to surface:

1. **Hierarchical datasets** can now be published directly. Pass an
   {py:class}`xarray.DataTree` (or any mix of trees and Datasets) to the same
   APIs you already use:

   ```python
   import xarray as xr
   import xpublish

   dt = xr.open_datatree("...")
   xpublish.Rest({"my-tree": dt}).serve(host="0.0.0.0", port=9000)
   # or, on a single tree:
   dt.rest.serve(host="0.0.0.0", port=9000)
   ```

2. **New built-in endpoints** on the `dataset_info` plugin (prefix
   `/datasets/<dataset_id>`):

   | URL                   | Returns                                  |
   | --------------------- | ---------------------------------------- |
   | `/tree`               | HTML repr of the full DataTree           |
   | `/groups`             | JSON list of every group path            |
   | `/groups/<path>`      | HTML repr of the node at `<path>`        |
   | `/groups/<path>/keys` | Variable keys at `<path>`                |
   | `/groups/<path>/dict` | Schema dict at `<path>` (no data)        |
   | `/groups/<path>/info` | Detailed schema info at `<path>`         |

   For flat datasets, `/groups` returns `["/"]` and `/groups/<path>/...`
   returns 404.

## For plugin authors

Existing plugins do not need to change. The new provider hook
{py:meth}`~xpublish.plugins.hooks.PluginSpec.get_datatree` is added
**alongside** {py:meth}`~xpublish.plugins.hooks.PluginSpec.get_dataset` — pick
whichever fits your data. `get_datatree` is consulted first, so a plugin can
implement both.

Use `get_datatree` when you want to:

- Expose multiple groups in a hierarchical dataset, or
- Lazily open one group at a time (Zarr/Icechunk-style backends).

```python
@hookimpl
def get_datatree(self, dataset_id: str, group: str):
    if dataset_id != "my-data":
        return None
    return xr.DataTree(dataset=open_my_group(dataset_id, group))
```

To make a route group-aware, add a `{group_path:path}` segment to its path.
`Depends(deps.dataset)` and the new `Depends(deps.datatree)` then resolve
automatically to the requested node:

```python
@router.get("/groups/{group_path:path}/attrs")
def group_attrs(ds=Depends(deps.dataset)):
    return ds.attrs
```

```{important}
[Pluggy](https://pluggy.readthedocs.io/) does **not** forward hookimpl
arguments that have a default value. Declare `group` as positional (no
default), or it will silently always be `""`:

    def get_datatree(self, dataset_id: str, group: str):  # ✅
    def get_datatree(self, dataset_id: str, group: str = ""):  # ❌
```

See [Serving DataTrees](../getting-started/tutorial/datatrees.md) and the
[Plugins user guide](./plugins.md) for the lazy-by-group pattern, route
ordering caveats, and `deps.datatree` examples.

## For application embedders

If your code instantiates {py:class}`xpublish.Rest` or
{py:class}`xpublish.SingleDatasetRest` directly, the type signatures have
widened — Datasets, DataTrees, or any mix are accepted. Internal storage is
now uniformly {py:class}`xarray.DataTree`, so `self._datasets[id]` returns a
tree; access the root via `tree.dataset`.
