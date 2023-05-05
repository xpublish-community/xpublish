# Using Plugins

```{warning}
Under construction.
For now see the [plugin user guide](../../user-guide/plugins.md)
```

Much of the power of Xpublish comes from it's [ecosystem](../../ecosystem/index) of plugins, which can quickly extend Xpublish with new capabilities.

Most Xpublish plugins use a the [Python entry points system](../../user-guide/plugins.md#entry-points) and have reasonable defaults set, which allows them to register themselves with Xpublish, and start responding to requests as soon as they are installed.

That makes new Xpublish functionality a `pip` or `conda install` away!

```{note}
For the server admins that just started worrying about new functionality being injected into their servers, the entire plugin loading process can be explicitly managed.

See the [plugin user guide](../../user-guide/plugins.md#entry-points) or [deployment guide](../../user-guide/deployment/index.md) for more details.
```
