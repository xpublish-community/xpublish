# Introduction

If you've read through [Why Xpublish](../why-xpublish.md) you'll know that Xpublish is a foundational building block for data servers. The real trick behind Xpublish is that it builds upon the Xarray datasets that the Python data community is used too.

To introduce new users to Xpublish, quickly serve a single dataset, and to allow for quick development, Xpublish includes an [Xarray accessor](https://docs.xarray.dev/en/stable/internals/extending-xarray.html).

## Server-Side

To begin, import Xpublish and open an Xarray {class}`~xarray.Dataset`:

```python
import xarray as xr
import xpublish

ds = xr.tutorial.open_dataset(
    "air_temperature",
    chunks=dict(lat=5, lon=5),
)
```

To publish the dataset, use the
{class}`~xpublish.SingleDatasetRest` class:

```python
rest = xpublish.SingleDatasetRest(ds)
```

Alternatively, you might want to use the {attr}`xarray.Dataset.rest` accessor
for more convenience:

```python
ds.rest
```

The same accessor is registered on {py:class}`xarray.DataTree` — `dt.rest`
works exactly like `ds.rest`. See the [DataTrees tutorial](./datatrees.md) for
how hierarchical data is served and navigated.

Optional customization of the underlying [FastAPI application](https://fastapi.tiangolo.com) or the server-side [cache](https://github.com/dask/cachey) is possible, e.g.,

```python
ds.rest(
    app_kws=dict(
        title="My Dataset",
        description="Dataset Description",
        openapi_url="/dataset.JSON",
    ),
    cache_kws=dict(available_bytes=1e9),
)
```

Serving the dataset then requires calling the
{meth}`~xpublish.Rest.serve` method on the {class}`~xpublish.Rest` instance or
the {attr}`xarray.Dataset.rest` accessor:

```python
rest.serve()

# or

ds.rest.serve()
```

{meth}`~xpublish.Rest.serve` passes any keyword arguments on to
{func}`uvicorn.run` (see [Uvicorn docs]).

### Default API routes

By default, the FastAPI application created with Xpublish provides the following
endpoints to get some information about the published dataset:

- `/`: returns xarray's HTML repr.
- `/keys`: returns a list of variable keys, i.e., those returned by {attr}`xarray.Dataset.variables`.
- `/info`: returns a JSON dictionary summary of a Dataset variables and attributes, similar to {meth}`xarray.Dataset.info`.
- `/dict`: returns a JSON dictionary of the full dataset.
- `/versions`: returns JSON dictionary of the versions of Python, Xarray and related libraries on the server side, similar to {func}`xarray.show_versions`.

```{admonition} Zarr access moved to xpublish-zarr
---
class: important
---
Previous versions of Xpublish shipped a built-in Zarr plugin exposing
`/zarr/.zmetadata` and `/zarr/{var}/{key}` endpoints. Starting with this
release the Zarr plugin lives in its own package,
[xpublish-zarr]. Install it separately (e.g.
`pip install xpublish-zarr`) and register it on the Rest app to restore
the previous Zarr-compatible endpoints.
```

Additional data access endpoints (such as Zarr-compatible access via
[xpublish-zarr]) can be added by installing or writing plugins.

### API Docs

Thanks to FastAPI and [Swagger UI], automatically generated
interactive documentation is available at the `/docs` URL.

This path can be overridden by setting the `docs_url` key in the `app_kws`
dictionary argument when initializing the rest accessor.

## Client-Side

Xpublish's endpoints can be queried programmatically with any HTTP client.
For example:

```python
import requests

response = requests.get("http://0.0.0.0:9000/info").json()
```

[swagger ui]: https://github.com/swagger-api/swagger-ui
[uvicorn docs]: https://www.uvicorn.org/deployment/#running-programmatically
[xpublish-zarr]: https://github.com/xpublish-community/xpublish-zarr
