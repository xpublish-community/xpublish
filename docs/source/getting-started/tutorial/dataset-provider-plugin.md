# Building a dataset provider plugin

So far, we've been eagerly loading datasets for Xpublish to serve, but this tends not to scale well between memory needs and slow startup. Xpublish plugins can also be __Dataset Providers__ and handle loading of datasets on request.

This also allows organizations to quickly be able to adapt Xpublish to work in their own environment, rather than needing Xpublish to explicitly support it.

```{literalinclude} dataset-provider-plugin.py
```

With this plugin, Xpublish can serve the same datasets as we explictly defined and loaded in [serving multiple datasets](./serving-multiple-datasets.md), as well as any others supported by [`xr.tutorial`](https://github.com/pydata/xarray/blob/main/xarray/tutorial.py)

The plugin implements {py:meth}`xpublish.plugins.hooks.PluginSpec.get_datatree`,
which receives both `dataset_id` and a `group` path so it can serve hierarchical
data. The simpler {py:meth}`~xpublish.plugins.hooks.PluginSpec.get_dataset` hook
is also first-class — pick it for providers that only ever serve flat datasets.
See the [DataTrees tutorial](./datatrees.md) for the lazy-by-group pattern used
by Zarr/Icechunk-backed providers.

```{note}
For more details on building dataset provider plugins, please see the [plugin user guide](../../user-guide/plugins.md#dataset-provider-plugins)
```
