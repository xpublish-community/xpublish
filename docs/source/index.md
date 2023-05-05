# Xpublish

**Useful links:** [Installation](getting-started/installation) | [Source Repository](https://github.com/xpublish-community/xpublish/) | [Issue Tracker](https://github.com/xpublish-community/xpublish/issues) | [Q&A Support](https://github.com/xpublish-community/xpublish/discussions/categories/q-a?discussions_q=category%3AQ%26A+) | [Slack Channel](./ecosystem/index.md#slack)

## Xpublish is

````{grid} 3

```{grid-item-card} A quick way to serve a single Xarray dataset over HTTP using FastAPI
:link: getting-started/tutorial/introduction

Get started with `ds.rest.serve()` to explore serving data with Xpublish
```

```{grid-item-card} An extendable core of a dataset server
:link: getting-started/why-xpublish

By building a server based around Xarray datasets, we can build on top of the rapid progress of Xarray and the greater PyData ecosystem.
```

```{grid-item-card} A community and ecosystem of plugins, servers, and their builders and users
:link: ecosystem/index

Explore the [Xpublish ecosystem](./ecosystem/index.md).
```

````

## I want to

- [Quickly serve a single dataset for my own use](getting-started/tutorial/introduction)
- Serve a collection of datasets with pre-configured server
- [Build plugins to serve datasets in new ways](getting-started/tutorial/dataset-router-plugin)
- [Connect to a new source of datasets](getting-started/tutorial/dataset-provider-plugin)
- [Discuss Xpublish with others](ecosystem/index.md#connect)

````{grid} 1 1 2 2
---
gutter: 2
---
```{grid-item-card} Getting started
:link: getting-started/index
:link-type: doc

New to _Xpublish_? Check out the getting started guides. They contain an introduction
to _Xpublish's_ main concepts.
```

```{grid-item-card} User guide
:link: user-guide/index
:link-type: doc

The user guide contains in-depth information on the key concepts of Xpublish
with useful background information and explanation.
```

```{grid-item-card} API Reference
:link: api
:link-type: doc

The reference guide contains a detailed description of the Xpublish API/
The reference describes how the methods work and which parameters can be used.
It assumes that you have an an understanding of the key concepts.
```

```{grid-item-card} Developer guide
:link: contributing
:link-type: doc

Saw a typo in the documentation? Want to improve existing functionalities?
The contributing guidelines will guide you through the process of improving Xpublish.
```

````

### Xpublish lets you easily publish Xarray Datasets via a REST API.

_You can run a short example application in a live session here:_ [![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/xpublish-community/xpublish/master)

On the server-side, one or more datasets can be published using the
{class}`xpublish.Rest` class or the {attr}`xarray.Dataset.rest` accessor, e.g.,

```python
ds.rest.serve(host="0.0.0.0", port=9000)
```

Those datasets can be accessed from various kinds of client applications, e.g.,
from within Python using Zarr and fsspec.

```python
import xarray as xr
import zarr
from fsspec.implementations.http import HTTPFileSystem

fs = HTTPFileSystem()
http_map = fs.get_mapper("http://0.0.0.0:9000/zarr/")

# open as a zarr group
zg = zarr.open_consolidated(http_map, mode="r")

# or open as another Xarray Dataset
ds = xr.open_zarr(http_map, consolidated=True)
```

Or to explore other access methods, open [http://0.0.0.0:9000/docs](http://0.0.0.0:9000/docs) in a browser.

```{toctree}
---
caption: Documentation Contents
hidden: true
maxdepth: 2
---
getting-started/index
user-guide/index
api
ecosystem/index
Contributing <contributing>
```

## Feedback

If you encounter any errors or problems with **Xpublish**, please open an issue
on [GitHub](http://github.com/xpublish-community/xpublish), or ask questions in [Github Discussions](https://github.com/xpublish-community/xpublish/discussions/categories/q-a?discussions_q=category%3AQ%26A+) or on our [Slack Channel](./ecosystem/index.md#slack).
