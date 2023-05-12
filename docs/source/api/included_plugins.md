# Included Plugins

Xpublish includes a set of built in plugins with associated endpoints.

```{eval-rst}
.. currentmodule:: xpublish
```

## Dataset Info

The dataset info plugin provides a handful of default ways to display datasets and their metadata.

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
