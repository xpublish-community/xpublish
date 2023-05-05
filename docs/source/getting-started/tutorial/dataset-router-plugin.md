# Creating a dataset router plugin

```{warning}
Under construction.
For now see the [plugin user guide](../../user-guide/plugins.rst)
```

Starting with the [dataset router we built](./dataset-router.md), we can transform it into a plugin.

```python
# existing router

myrouter = APIRouter()


@myrouter.get("/{var_name}/mean")
def get_mean(var_name: str, dataset: xr.Dataset = Depends(get_dataset)):
    if var_name not in dataset.variables:
        raise HTTPException(
            status_code=404, detail=f"Variable '{var_name}' not found in dataset"
        )

    return float(dataset[var_name].mean())
```

```python
# dataset router plugin
from xpublish import Dependencies, Plugin, hookimpl


class MeanPlugin(Plugin):
    name = "mean"

    dataset_router_prefix = ""
    dataset_router_tags = ["mean"]

    @hookimpl
    def dataset_router(self, deps: Dependencies):
        router = APIRouter(
            prefix=self.dataset_router_prefix, tags=list(self.dataset_router_tags)
        )

        @router.get("/{var_name}/mean")
        def get_mean(var_name: str, dataset=Depends(deps.dataset)):
            if var_name not in dataset.variables:
                raise HTTPException(
                    status_code=404,
                    detail=f"Variable '{var_name}' not found in dataset",
                )

            return float(dataset[var_name].mean())

        return router
```

When a plugin is defined it tends to be a bit longer than the router as defined directly, as some of those elements are what provides users the ability to configure the plugin.
Other parts are necessary for Xpublish to be able to find an appropriately load the plugin.

## Building blocks of a plugin

### Subclassing

A plugin starts by inheriting from the {py:class}`xpublish.plugins.hooks.Plugin` (exposed as `xpublish.Plugin`), and defining a name that the system should know it by.
`xpublish.Plugin` itself is a subclass of [`pydantic.BaseModel`](https://docs.pydantic.dev/latest/usage/models/) which allows quick configuration.

```{code-block} python
---
emphasize-lines: 4-5
---
from xpublish import Dependencies, Plugin, hookimpl


class MeanPlugin(Plugin):
    name = "mean"

    dataset_router_prefix= ''
    dataset_router_tags = ["mean"]
```

### Configurable attributes

Next the attributes are defined that a user or admin may wish to override.

```{code-block} python
---
emphasize-lines: 4-5
---
class MeanPlugin(Plugin):
    name = "mean"

    dataset_router_prefix= ''
    dataset_router_tags = ["mean"]

    @hookimpl
    def dataset_router(self, deps: Dependencies):
```

### Extension hooks

Then the plugin needs to tell Xpublish what it can do.

It does it with the `@hookimpl` decorator and specifically named methods,
in this case `dataset_router`.

These methods can take a set of arguments that Xpublish has defined (further explored in the [plugin user guide](../../user-guide/plugins.md) and [API docs](../../api.md)).

```{code-block} python
---
emphasize-lines: 7-8
---
class MeanPlugin(Plugin):
    name = "mean"

    dataset_router_prefix= ''
    dataset_router_tags = ["mean"]

    @hookimpl
    def dataset_router(self, deps: Dependencies):
        router = APIRouter(prefix=self.dataset_router_prefix, tags=list(self.dataset_router_tags))

        @router.get("/{var_name}/mean")
        def get_mean(var_name: str, dataset=Depends(deps.dataset)):
```

### Building the router

The router can now be transformed.
Most of it stays the same, though dependencies now instead use the ones passed to the method, and the router should be initialized with the prefix and tags.

```{code-block} python
---
emphasize-lines: 9-18, 20
---
class MeanPlugin(Plugin):
    name = "mean"

    dataset_router_prefix= ''
    dataset_router_tags = ["mean"]

    @hookimpl
    def dataset_router(self, deps: Dependencies):
        router = APIRouter(prefix=self.dataset_router_prefix, tags=list(self.dataset_router_tags))

        @router.get("/{var_name}/mean")
        def get_mean(var_name: str, dataset=Depends(deps.dataset)):
            if var_name not in dataset.variables:
                raise HTTPException(
                    status_code=404, detail=f"Variable '{var_name}' not found in dataset"
                )

            return float(dataset[var_name].mean())

        return router
```

Additionally the router needs to be returned from the method, so that Xpublish can access it.

### Registering the plugin

While the [entry points system](../../user-guide/plugins.md#entry-points) can be used for sharing plugins with others, for plugins that aren't going to be distributed, they can be registered directly.

```{code-block} python
---
emphasize-lines: 6
---
ds = xr.tutorial.open_dataset(
    "air_temperature",
    chunks=dict(lat=5, lon=5),
)

rest = ds.rest
rest.register_plugin(MeanPlugin())
rest.serve()
```

Now the same routes are available on your server, and it's possible to share your plugin with other Xpublish users.
