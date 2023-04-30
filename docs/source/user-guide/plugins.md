# Plugins

While {py:class}`fastapi.APIRouter` can get you started building new endpoints
for datasets quickly, the real extendability of Xpublish comes from it's plugin system.

By using a plugin system, Xpublish becomes incredibly adaptable, and hopefully
easier to develop for also. Individual plugins and their functionality can
evolve independently, there are clear boundaries between types of functionality,
which allows easier reasoning about code.

There are a few main varieties of plugins that Xpublish supports, but those
provide a lot of flexibility, and can enable whole new categories of plugins
and functionality.

- [Dataset router](#dataset-router-plugins)
- [App router](#app-router-plugins)
- [Dataset provider](#dataset-provider-plugins)
- [Hook spec](#hook-spec-plugins)

Plugins work by implementing specific methods to support a variety of usage,
and marking the implementations with a decorator. A plugin can also implement
methods for multiple varieties, which may be useful for things like dynamic
data providers.

```{warning}
Plugins are new to Xpublish, so we're learning how everything works best together.

If you have any questions, please ask in [Github Discussions](https://github.com/xpublish-community/xpublish/discussions)
(and feel free to tag `@abkfenris` for help with the plugin system).
```

## Functionality

Plugins are built as [Pydantic models](https://docs.pydantic.dev/usage/models/)
and descend from {py:class}`xpublish.plugins.hooks.Plugin`.
This allows there to be a common way of configuring plugins and their functionality.

```{code-block} python
---
emphasize-lines: 5
---
from xpublish import Plugin


class HelloWorldPlugin(Plugin):
    name = "hello_world"
```

At the minimum, a plugin needs to specify a `name` attribute.

### Marking implementation methods

We'll go deeper into the specific methods below, what they have in common is that any
method that a plugin is hoping to expose to the rest of Xpublish needs to be marked
with a `@hookimpl` decorator.

```{code-block} python
---
emphasize-lines: 7
---
from xpublish import Plugin, hookimpl
from fastapi import APIRouter

class HelloWorldPlugin(Plugin):
    name = "hello_world"

    @hookimpl
    def app_router(self):
        router = APIRouter()

        @router.get("/hello")
        def get_hello():
            return "world"

        return router
```

For the plugin system, Xpublish is using [pluggy](https://pluggy.readthedocs.io/en/latest/).
Pluggy was developed to support [pytest](https://docs.pytest.org/en/latest/how-to/plugins.html),
but it now is used by several other projects including [Tox](https://tox.wiki/en/latest/plugins.html),
[Datasette](https://docs.datasette.io/en/latest/plugins.html),
and [Conda](https://docs.conda.io/projects/conda/en/latest/dev-guide/plugins/index.html), among others.

Pluggy implements plugins as a system of hooks, each one is a distinct way for Xpublish
to communicate with plugins.
Each hook has both reference specifications, and plugin provided implementations.

Most of the specifications are provided by Xpublish and are methods on
{py:class}`xpublish.plugins.hooks.PluginSpec` that are marked with `@hookspec`.

Plugins can then re-implement these methods with all or a subset of the arguments,
which are then marked with `@hookimpl`
to tell Pluggy to make them accessible to Xpublish (and other plugins).

```{note}
Over time Xpublish will most likely end up expanding the number of arugments passed
into most hook methods.

Currently we're starting with a minimum set of arguments as we can always expand,
but currently it is much harder to reduce the number of arguments.

If there is a new argument that you would like your plugin hooks to have,
please raise an [issue](https://github.com/xpublish-community/xpublish/issues)
to discuss including it in a future version.
```

In the specification, Xpublish defines if it's supposed to get responses from all
implementations ({py:meth}`xpublish.plugins.hooks.PluginSpec.get_dataset_ids`),
or the first non-`None` response ({py:meth}`xpublish.plugins.hooks.PluginSpec.get_dataset`).

Pluggy also provides a lot more advanced functionality that we aren't going to go
into at this point, but could allow for creative things like dataset middleware.

### Loading Local Plugins

For plugins that you are not distributing, they can either be loaded directly via the
{py:class}`xpublish.Rest` initializer, or they can use
{py:meth}`xpublish.Rest.register_plugin` to load afterwards.

```python
from xpublish import Rest

rest = Rest(datasets, plugins={"hello-world": HelloWorldPlugin()})
```

```python
from xpublish import Rest

rest = Rest(datasets)
rest.register_plugin(HelloWorldPlugin())
```

```{caution}
When plugins are provided directly to the {py:class}`xpublish.Rest` initializer
as keyword arguments, it prevents Xpublish from automatically loading other plugins
that are installed.

For more details of the automatic plugin loading system,
see \[entry points\] below.
```

### Entry Points

When you install a plugin library, the library takes advantage of the
[entry point system](https://setuptools.pypa.io/en/latest/userguide/entry_point.html).

This allows {py:class}`xpublish.Rest` to automatically find and use plugins.
It only does this if plugins **are not** provided as an keyword argument.

{py:class}`xpublish.Rest` uses {py:func}`plugins.manage.load_default_plugins` to
load plugins from entry points.
It can be used directly and be set to disable specific plugins from being loaded,
or {py:func}`plugins.manage.find_default_plugins` and {py:func}`plugins.manage.configure_plugins`,
can be used to further tweak loading plugins from entrypoints.

To completely disable loading of plugins from entry points pass an empty dictionary to
`xpublish.Rest(datasets, plugins={})`.

#### Example Entry Point

Using [xpublish-edr](https://github.com/gulfofmaine/xpublish-edr/) as an example.

The plugin is named `CfEdrPlugin` and is located in `xpublish_edr/plugin.py`.

In `pyproject.toml` that then is added to the `[project.entry-points."xpublish.plugin"]` table.

```toml
[project.entry-points."xpublish.plugin"]
cf_edr = "xpublish_edr.plugin:CfEdrPlugin"
```

### Dependencies

To allow plugins to be more adaptable, they should use
{py:meth}`xpublish.Dependencies.dataset` rather than directly
importing {py:func}`xpublish.dependencies.get_dataset`.

To facilitate this, {py:class}`xpublish.Dependencies` is passed into
router hook methods.

```python
from fastapi import APIRouter, Depends
from xpublish import Plugin, Dependencies, hookimpl


class DatasetAttrs(Plugin):
    name = "dataset-attrs"

    @hookimpl
    def dataset_router(self, deps: Dependencies):
        router = APIRouter()

        @router.get("/attrs")
        def get_attrs(ds=Depends(deps.dataset)):
            return ds.attrs

        return router
```

{py:class}`xpublish.Dependencies` has several other types of dependency functions that
it includes.

## Dataset Router Plugins

Dataset router plugins are the next step from passing routers into
{py:class}`xpublish.Rest`.

By implementing {py:meth}`xpublish.plugins.hooks.PluginSpec.dataset_router`
a developer can add new routes that respond below `/datasets/<dataset_id>/`.

Most dataset routers will have a prefix on their paths, and apply tags.
To make this reasonably standard, those should be specified as `dataset_router_prefix`
and `dataset_router_tags` on the plugin allowing them to be reasonably overridden.

Adapted from [xpublish/plugins/included/dataset_info.py](https://github.com/xpublish-community/xpublish/blob/main/xpublish/plugins/included/dataset_info.py)

```python
from fastapi import APIRouter, Depends
from xpublish import Plugin, Dependencies, hookimpl


class DatasetInfoPlugin(Plugin):
    name = "dataset-info"

    dataset_router_prefix = "/info"
    dataset_router_tags = ["info"]

    @hookimpl
    def dataset_router(self, deps: Dependencies):
        router = APIRouter(
            prefix=self.dataset_router_prefix, tags=self.dataset_router_tags
        )

        @router.get("/keys")
        def list_keys(dataset=Depends(deps.dataset)):
            return dataset.variables

        return router
```

This plugin will respond to `/datasets/<dataset_id>/info/keys` with a list of the keys in the dataset.

## App Router Plugins

App routers allow new top level routes to be provided by implementing
{py:meth}`xpublish.plugins.hooks.PluginSpec.app_router`.

Similar to dataset routers, these should have a prefix (`app_router_prefix`) and tags (`app_router_tags`) that can be user overridable.

```python
from fastapi import APIRouter, Depends
from xpublish import Plugin, Dependencies, hookimpl


class PluginInfo(Plugin):
    name = "plugin_info"

    app_router_prefix = "/info"
    app_router_tags = ["info"]

    @hookimpl
    def app_router(self, deps: Dependencies):
        router = APIRouter(prefix=self.app_router_prefix, tags=self.app_router_tags)

        @router.get("/plugins")
        def plugins(plugins: Dict[str, Plugin] = Depends(deps.plugins)):
            return {name: type(plugin) for name, plugin in plugins.items}

        return router
```

This will return a dictionary of plugin names, and types at `/info/plugins`.

## Dataset Provider Plugins

While Xpublish can have datasets passed in to {py:class}`xpublish.Rest` on intialization,
plugins can provide datasets (and they actually have priority over those passed in directly).

In order for a plugin to provide datasets it needs to implemenent
{py:meth}`xpublish.plugins.hooks.PluginSpec.get_datasets`
and {py:meth}`xpublish.plugins.hooks.PluginSpec.get_dataset` methods.

The first should return a list of all datasets that a plugin knows about.

The second is provided a `dataset_id`.
The plugin should return a dataset if it knows about the dataset corresponding to the id,
otherwise it should return None, so that Xpublish knows to continue looking to the next
plugin or the passed in dictionary of datasets.

A plugin that provides the Xarray tutorial `air_temperature` dataset.

```python
from xpublish import Plugin, hookimpl


class TutorialDataset(Plugin):
    name = "xarray-tutorial-dataset"

    @hookimpl
    def get_datasets(self):
        return ["air"]

    @hookimpl
    def get_dataset(self, dataset_id: str):
        if dataset_id == "air":
            return xr.tutorial.open_dataset("air_temperature")

        return None
```

## Hook Spec Plugins

Plugins can also provide new hook specifications that other plugins can then implement.
This allows Xpublish to support things that we haven't even thought of yet.

These return a class of hookspecs from {py:meth}`xpublish.plugins.hooks.PluginSpec.register_hookspec`.
