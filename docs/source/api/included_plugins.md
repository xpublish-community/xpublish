# Included Plugins

Xpublish includes a set of built in plugins with associated endpoints.

```{eval-rst}
.. currentmodule:: xpublish
```

## Dataset Info

The dataset info plugin provides a handful of default ways to display datasets
and their metadata. Endpoints come in two flavors:

- **Root endpoints** — `/`, `/keys`, `/dict`, `/info` — operate on the root node
  of the underlying {py:class}`xarray.DataTree`. For a flat dataset this is just
  the dataset itself; for a DataTree it is the root group.
- **Group-aware endpoints** — `/groups/{group_path:path}/`,
  `/groups/{group_path:path}/keys`, `/groups/{group_path:path}/dict`, and
  `/groups/{group_path:path}/info` — return the same information for the node at
  the given group path in the tree.

In addition, two tree-shaped endpoints expose the DataTree directly:

- `/tree` — HTML representation of the full DataTree.
- `/groups` — JSON list of every group path in the tree (e.g. `["/", "/a", "/a/b"]`).

```{eval-rst}
.. autosummary::
   :toctree: generated/

   plugins.included.dataset_info.DatasetInfoPlugin

.. openapi:: ./openapi.json
   :paths:
    /datasets/{dataset_id}/
    /datasets/{dataset_id}/keys
    /datasets/{dataset_id}/dict
    /datasets/{dataset_id}/info
    /datasets/{dataset_id}/tree
    /datasets/{dataset_id}/groups
    /datasets/{dataset_id}/groups/{group_path}
    /datasets/{dataset_id}/groups/{group_path}/keys
    /datasets/{dataset_id}/groups/{group_path}/dict
    /datasets/{dataset_id}/groups/{group_path}/info
```

## Module Version

The module version plugin returns the versions of key libraries powering the Xpublish server.

```{eval-rst}
.. autosummary::
   :toctree: generated/

   plugins.included.module_version.ModuleVersionPlugin

.. openapi:: ./openapi.json
   :include:
    /versions
```

## Plugin Info

Similarly the versions of the plugins currently enabled on the Xpublish server.

```{eval-rst}
.. autosummary::
   :toctree: generated/

   plugins.included.plugin_info.PluginInfoPlugin

.. openapi:: ./openapi.json
   :include:
    /plugins
```

## Zarr

The Zarr plugin provides consolidated Zarr v2 access to the loaded datasets.

```{eval-rst}
.. autosummary::
   :toctree: generated/

   plugins.included.zarr.ZarrPlugin

.. openapi:: ./openapi.json
   :include:
    /datasets/{dataset_id}/zarr/*
```
