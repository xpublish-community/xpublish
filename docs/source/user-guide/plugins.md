# Plugins

```{versionadded} 0.3.0
Plugins were released in [0.3.0](https://github.com/xpublish-community/xpublish/releases/tag/0.3.0).
```

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
    name: str = "hello_world"
```

At the minimum, a plugin needs to specify a `name` attribute with a type annotation. For example, `name: str = my_plugin_name`.

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
    name: str = "hello_world"

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
implementations ({py:meth}`xpublish.plugins.hooks.PluginSpec.get_datasets`),
or the first non-`None` response ({py:meth}`xpublish.plugins.hooks.PluginSpec.get_datatree`).

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
It only does this if plugins **are not** provided as a keyword argument.

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
    name: str = "dataset-attrs"

    @hookimpl
    def dataset_router(self, deps: Dependencies):
        router = APIRouter()

        @router.get("/attrs")
        def get_attrs(ds=Depends(deps.dataset)):
            return ds.attrs

        return router
```

{py:class}`xpublish.Dependencies` has several other types of dependency functions that
it includes — notably {py:meth}`xpublish.Dependencies.datatree`, which returns
the full {py:class}`xarray.DataTree` for the resolved dataset id.

#### Hierarchical data and the `{group_path:path}` URL convention

Internally, Xpublish stores every published object as an {py:class}`xarray.DataTree`
(a bare {py:class}`xarray.Dataset` is wrapped in a single-node tree). Routes can
opt in to per-node navigation by including a `{group_path:path}` segment in their
path. When present, both {py:meth}`Dependencies.dataset` and
{py:meth}`Dependencies.datatree` read it automatically:

```python
from fastapi import APIRouter, Depends
from xpublish import Plugin, Dependencies, hookimpl


class GroupAware(Plugin):
    name: str = "group-aware"

    @hookimpl
    def dataset_router(self, deps: Dependencies):
        router = APIRouter()

        # Root-only: serves the dataset at the root node.
        @router.get("/attrs")
        def root_attrs(ds=Depends(deps.dataset)):
            return ds.attrs

        # Group-aware: ``{group_path:path}`` is optional/empty for root.
        # ``deps.dataset`` returns the Dataset at that node.
        @router.get("/groups/{group_path:path}/attrs")
        def group_attrs(ds=Depends(deps.dataset)):
            return ds.attrs

        # Or operate on the full subtree directly.
        @router.get("/tree")
        def tree(dt=Depends(deps.datatree)):
            return dt.groups

        return router
```

Plugins that don't include `{group_path:path}` will only ever see the root
dataset — that's the back-compat path, so flat-dataset plugins keep working
unchanged when a DataTree is published.

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
    name: str = "dataset-info"

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
    name: str = "plugin_info"

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

In order for a plugin to provide datasets it needs to implement
{py:meth}`xpublish.plugins.hooks.PluginSpec.get_datasets`
and {py:meth}`xpublish.plugins.hooks.PluginSpec.get_datatree`.

The first should return a list of all dataset ids that the plugin knows about.

The second is provided a `dataset_id` and a `group` path. The plugin should return
an {py:class}`xarray.DataTree` if it knows about the requested dataset/group, otherwise
`None` so that Xpublish continues looking to the next plugin or the directly-registered
datasets. The returned tree's **root** corresponds to the requested `group`.

````{important}
**Pluggy gotcha:** [Pluggy](https://pluggy.readthedocs.io/) does **not** forward
arguments that have a default value in the hookimpl signature. Always declare
`group` as a positional parameter (no default) on your `get_datatree`
implementation, or it will silently receive an empty string regardless of the URL.

```python
# ✅ Right — `group` is positional
@hookimpl
def get_datatree(self, dataset_id: str, group: str):
    ...


# ❌ Wrong — pluggy drops `group`, you'll only ever see the root
@hookimpl
def get_datatree(self, dataset_id: str, group: str = ""):
    ...
```

Pass an empty `group` to mean "the root of the tree".
````

### Example: simple (eager) provider

A plugin that publishes the Xarray tutorial `air_temperature` dataset as a single-node
tree:

```python
import xarray as xr
from xpublish import Plugin, hookimpl


class TutorialDataset(Plugin):
    name: str = "xarray-tutorial-dataset"

    @hookimpl
    def get_datasets(self):
        return ["air"]

    @hookimpl
    def get_datatree(self, dataset_id: str, group: str):
        if dataset_id != "air":
            return None
        if group:
            # We only serve a flat dataset; no sub-groups exist.
            return None
        return xr.DataTree(dataset=xr.tutorial.open_dataset("air_temperature"))
```

### Example: lazy-by-group provider

For backends like Zarr v3 or Icechunk where opening the full tree is expensive,
implement `get_datatree` so it opens only the requested group and wraps it in
a single-node tree:

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

This keeps the provider efficient — the request only ever opens the single group
being viewed.

### Legacy `get_dataset` hook (deprecated)

```{warning}
{py:meth}`xpublish.plugins.hooks.PluginSpec.get_dataset` is **deprecated** and
emits a {py:class}`DeprecationWarning` when registered. The returned Dataset is
wrapped in a single-node DataTree, so only the root group is reachable through
it. Migrate to `get_datatree` to expose hierarchical data.
```

## Hook Spec Plugins

Plugins can also provide new hook specifications that other plugins can then implement.
This allows Xpublish to support things that we haven't even thought of yet.

These return a class of hookspecs from {py:meth}`xpublish.plugins.hooks.PluginSpec.register_hookspec`.

```

```
