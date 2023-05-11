# Why Xpublish

Xarray provides an intuitive API on top of a foundational data model, labeled arrays and datasets.
This API and data model has formed the basis for a large and growing ecosystem of tools.

Xpublish stands on the shoulders of Xarray and the greater PyData ecosystem enabling both new and old users, interactions, and clients.
Xpublish does this by using Xarray datasets as the core data interchange format within the server, and surrounding that with an ecosystem of plugins.

```{warning} Hold on to your hats, we're about to say Xpublish a lot
<div style='position:relative; padding-bottom:calc(75.00% + 44px)'><iframe src='https://gfycat.com/ifr/ShadowyHoarseInganue' frameborder='0' scrolling='no' width='100%' height='100%' style='position:absolute;top:0;left:0;' allowfullscreen></iframe></div><p> <a href="https://gfycat.com/shadowyhoarseinganue">via Gfycat</a></p>
```

## An extendable core

`xpublish` (the library) on it's own is designed to be relatively small and lightweight. It mainly defines plugin extension points, based around the internal exchange of Xarray datasets. It also defines a standard way to configure plugins, and how to load them.

It additionally provides an Xarray dataset accessor that allows for quickly serving a dataset, and a nice introduction path for creating new dataset based routers.

## A collection of plugins

Xpublish really starts coming into it's own with the plugin ecosystem.

Because `xpublish` the library has a relatively small API surface, but depends on familiar Xarray datasets, it becomes much easier to quickly develop large classes of plugins. Additionally by keeping most of the internet and storage facing elements of Xpublish out of the `xpublish` library, plugins can develop independently and at their own rate.

## An ecosystem of servers

Eventually, for many users they may never know that they are using Xpublish. Instead it will be the foundational building block of a family of data servers. Different communities may have different desires out of their servers and thus combine Xpublish with different sets of plugins.

A 'neurological community Xpublish server' may look very different from the needs of a 'meteorological community Xpublish server' but they may include some of the same plugins. Each community may distribute their servers in different ways with different ways of configuring them.

An additional power of Xpublish is for the server admins. When a community decides on a specific 'Xpublish server distribution', but the distributions opinions of how data should be stored don't match the environment, the admin can add or replace the distributions data provider plugins to adapt to their own infrastructure.

```{admonition} For more background
Check out [Alex's manifesto](https://github.com/xpublish-community/xpublish/discussions/139) that kicked off this phase of development.
```
