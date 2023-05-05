# Creating a dataset router plugin

Starting with the [dataset router we built](./dataset-router.md), we can transform it into a plugin.

Xpublish supports several different types of plugins, so we will build a [dataset router plugin](../../user-guide/plugins.md#dataset-provider-plugins).

```{literalinclude} dataset-router.py
---
lines: 12-23
caption: Existing router
---
```

```{literalinclude} dataset-router-plugin.py
```

When a plugin is defined it tends to be a bit longer than the router as defined directly, as some of those elements are what provides users the ability to configure the plugin.
Other parts are necessary for Xpublish to be able to find an appropriately load the plugin.

## Building blocks of a plugin

### Subclassing

A plugin starts by inheriting from the {py:class}`xpublish.plugins.hooks.Plugin` (exposed as `xpublish.Plugin`), and defining a name that the system should know it by.
`xpublish.Plugin` itself is a subclass of [`pydantic.BaseModel`](https://docs.pydantic.dev/latest/usage/models/) which allows quick configuration.

```{literalinclude} dataset-router-plugin.py
---
lines: 4-11
emphasize-lines: 4-5
---
```

### Configurable attributes

Next the attributes are defined that a user or admin may wish to override.

```{literalinclude} dataset-router-plugin.py
---
lines: 7-14
emphasize-lines: 4-5
---
```

### Extension hooks

Then the plugin needs to tell Xpublish what it can do.

It does it with the `@hookimpl` decorator and specifically named methods,
in this case `dataset_router`.

These methods can take a set of arguments that Xpublish has defined (further explored in the [plugin user guide](../../user-guide/plugins.md) and [API docs](../../api.md)).

```{literalinclude} dataset-router-plugin.py
---
lines: 7-18
emphasize-lines: 7-8
---
```

### Building the router

The router can now be transformed.
Most of it stays the same, though dependencies now instead use the ones passed to the method, and the router should be initialized with the prefix and tags.

```{literalinclude} dataset-router-plugin.py
---
lines: 7-27
emphasize-lines: 9-19, 21
---
```

Additionally the router needs to be returned from the method, so that Xpublish can access it.

### Registering the plugin

While the [entry points system](../../user-guide/plugins.md#entry-points) can be used for sharing plugins with others, for plugins that aren't going to be distributed, they can be registered directly.

```{literalinclude} dataset-router-plugin.py
---
lines: 30-37
emphasize-lines: 7
---
```

Now the same routes are available on your server, and it's possible to share your plugin with other Xpublish users.

```{note}
For more details see the [plugin user guide](../../user-guide/plugins.md#dataset-router-plugins)
```
