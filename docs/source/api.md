```{eval-rst}
.. currentmodule:: xpublish
```

# API reference

## Top-level Rest class

The {class}`~xpublish.Rest` class can be used for publishing a
{class}`xarray.Dataset` object or a collection of Dataset objects.

The main interfaces to Xpublish that many users may use.

```{eval-rst}
.. autosummary::
   :toctree: generated/

   Rest
   Rest.app
   Rest.cache
   Rest.plugins
   Rest.serve
   Rest.register_plugin
   Rest.dependencies
```

There are also a handful of methods that are more likely to be used
when subclassing `xpublish.Rest` to modify functionality, or are used
by plugin dependencies.

```{eval-rst}
.. autosummary::
   :toctree: generated/

   Rest.setup_datasets
   Rest.get_datasets_from_plugins
   Rest.get_dataset_from_plugins
   Rest.setup_plugins
   Rest.init_cache_kwargs
   Rest.init_app_kwargs
   Rest.plugin_routers
```

There is also a specialized version of {class}`xpublish.Rest` for use
when only a single dataset is being served, instead of a collection
of datasets.

```{eval-rst}
.. autosummary::
   :toctree: generated/

   SingleDatasetRest
   SingleDatasetRest.setup_datasets
```

For serving a single dataset the {class}`~xpublish.SingleDatasetRest` is used instead.

```{eval-rst}
.. autosummary::
   :toctree: generated/

   SingleDatasetRest
```

## Dataset.rest (xarray accessor)

This accessor extends {py:class}`xarray.Dataset` with the same interface than
{class}`~xpublish.SingleDatasetRest`. It is a convenient method for publishing one single
dataset. Proper use of this accessor should be like:

```
>>> import xarray as xr         # first import xarray
>>> import xpublish             # import xpublish (the dataset 'rest' accessor is registered)
>>> ds = xr.Dataset()           # create or load an xarray Dataset
>>> ds.rest(...)                # call the 'rest' accessor on the dataset
>>> ds.rest.<meth_or_prop>      # access to the methods and properties listed below
```

```{eval-rst}
.. currentmodule:: xarray
```

**Calling the accessor**

```{eval-rst}
.. autosummary::
   :toctree: generated/
   :template: autosummary/accessor_callable.rst

   Dataset.rest
```

**Properties**

```{eval-rst}
.. autosummary::
   :toctree: generated/
   :template: autosummary/accessor_attribute.rst

   Dataset.rest.app
   Dataset.rest.cache
```

**Methods**

```{eval-rst}
.. autosummary::
   :toctree: generated/
   :template: autosummary/accessor_method.rst

   Dataset.rest.serve
```

## FastAPI dependencies

The functions below are defined in module `xpublish.dependencies` and can
be used as [FastAPI dependencies](https://fastapi.tiangolo.com/tutorial/dependencies)
when creating custom API endpoints directly.

When creating routers with plugins, instead use `xpublish.Dependency` that will be
passed in to the `Plugin.app_router` or `Plugin.dataset_router` method.

```{eval-rst}
.. currentmodule:: xpublish.dependencies
```

```{eval-rst}
.. autosummary::
   :toctree: generated/

   get_dataset_ids
   get_dataset
   get_cache
   get_zvariables
   get_zmetadata
   get_plugins
   get_plugin_manager
```

## Plugins

Plugins are inherit from the {class}`~xpublish.Plugin` class, and implement various hooks.

```{eval-rst}
.. currentmodule:: xpublish
```

```{eval-rst}
.. autosummary::
   :toctree: generated/

   Plugin
   hookimpl
   hookspec
   Dependencies
   plugins.hooks.PluginSpec
   plugins.manage.find_default_plugins
   plugins.manage.load_default_plugins
   plugins.manage.configure_plugins
```
