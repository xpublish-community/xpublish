# Included Plugins

Xpublish includes a set of built in plugins with associated endpoints.

```{eval-rst}
.. currentmodule:: xpublish
```

## Dataset Info

```{eval-rst}
.. autosummary::
   :toctree: generated/

   plugins.included.dataset_info.DatasetInfoPlugin

.. openapi:: ./openapi.json
   :include:
    /datasets/{dataset_id}/keys
    /datasets/{dataset_id}/dict
    /datasets/{dataset_id}/info
```

## Module Version

```{eval-rst}
.. autosummary::
   :toctree: generated/

   plugins.included.module_version.ModuleVersionPlugin

.. openapi:: ./openapi.json
   :include:
    /versions
```

## Plugin Info

```{eval-rst}
.. autosummary::
   :toctree: generated/

   plugins.included.plugin_info.PluginInfoPlugin

.. openapi:: ./openapi.json
   :include:
    /plugins
```

## Zarr

```{eval-rst}
.. autosummary::
   :toctree: generated/

   plugins.included.zarr.ZarrPlugin

.. openapi:: ./openapi.json
   :include:
    /datasets/{dataset_id}/zarr/*
```
